"""
QuantumHead Inference Server for spike2
========================================
Loads trained QuantumHead weights and serves avatar generation.
Designed to run alongside the existing TTS server on spike2.

Endpoints:
  POST /quantumhead/generate       - Audio + image → video
  POST /quantumhead/upload-weights - Upload trained model weights
  GET  /quantumhead/status         - Model status
  POST /quantumhead/pull-weights   - Pull weights from cloud/URL

Usage:
  python quantumhead_server.py --port 8100
  
Or integrate into existing server.py via:
  from quantumhead_server import create_quantumhead_router
  app.include_router(create_quantumhead_router())
"""

import os
import io
import json
import time
import uuid
import shutil
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# ============================================================
# CONFIG
# ============================================================
WEIGHTS_DIR = os.environ.get("QH_WEIGHTS_DIR", "/root/quantumhead/weights")
OUTPUT_DIR = os.environ.get("QH_OUTPUT_DIR", "/root/quantumhead/output")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
IMAGE_SIZE = 512
UV_SIZE = 256
FPS = 25

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("quantumhead")


# ============================================================
# MODEL DEFINITIONS (must match training notebook)
# ============================================================

class ConvBlock(torch.nn.Module):
    def __init__(self, in_ch, out_ch, upsample=False):
        super().__init__()
        self.conv = torch.nn.Conv2d(in_ch, out_ch, 3, padding=1)
        self.norm = torch.nn.InstanceNorm2d(out_ch)
        self.act = torch.nn.LeakyReLU(0.2)
        self.upsample = upsample

    def forward(self, x):
        if self.upsample:
            x = F.interpolate(x, scale_factor=2, mode="bilinear", align_corners=False)
        return self.act(self.norm(self.conv(x)))


class NeutralDecoder(torch.nn.Module):
    def __init__(self, z_dim=512, num_scales=8):
        super().__init__()
        self.fc = torch.nn.Linear(z_dim, 256 * 4 * 4)
        channels = [256, 256, 128, 128, 64, 64, 32, 16]
        self.blocks = torch.nn.ModuleList()
        for i in range(num_scales):
            in_ch = 256 if i == 0 else channels[i - 1]
            self.blocks.append(
                torch.nn.Sequential(
                    torch.nn.ConvTranspose2d(in_ch, channels[i], 4, 2, 1),
                    torch.nn.LeakyReLU(0.2),
                )
            )

    def forward(self, z_id):
        x = self.fc(z_id).view(-1, 256, 4, 4)
        bias_maps = []
        for block in self.blocks:
            x = block(x)
            bias_maps.append(x)
        return bias_maps


class GuideMeshDecoder(torch.nn.Module):
    def __init__(self, z_id_dim=512, z_exp_dim=256, n_vertices=7306):
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(z_id_dim + z_exp_dim, 1024),
            torch.nn.LeakyReLU(0.2),
            torch.nn.Linear(1024, 2048),
            torch.nn.LeakyReLU(0.2),
            torch.nn.Linear(2048, n_vertices * 3),
        )
        self.n_vertices = n_vertices

    def forward(self, z_id, z_exp):
        z = torch.cat([z_id, z_exp], dim=-1)
        offsets = self.net(z).view(-1, self.n_vertices, 3)
        return offsets


class GaussianAvatarDecoder(torch.nn.Module):
    def __init__(self, z_id_dim=512, z_exp_dim=256, uv_size=256):
        super().__init__()
        self.uv_size = uv_size

        self.fc_vi = torch.nn.Linear(z_id_dim + z_exp_dim, 256 * 8 * 8)
        vi_channels = [256, 128, 128, 64, 64, 32, 16, 11]
        self.vi_blocks = torch.nn.ModuleList()
        for i, out_ch in enumerate(vi_channels):
            in_ch = 256 if i == 0 else vi_channels[i - 1]
            self.vi_blocks.append(
                torch.nn.Sequential(
                    torch.nn.ConvTranspose2d(in_ch, out_ch, 4, 2, 1),
                    torch.nn.LeakyReLU(0.2)
                    if i < len(vi_channels) - 1
                    else torch.nn.Identity(),
                )
            )

        self.fc_rgb = torch.nn.Linear(z_id_dim + z_exp_dim + 3, 256 * 8 * 8)
        rgb_channels = [256, 128, 128, 64, 64, 32, 16, 3]
        self.rgb_blocks = torch.nn.ModuleList()
        for i, out_ch in enumerate(rgb_channels):
            in_ch = 256 if i == 0 else rgb_channels[i - 1]
            self.rgb_blocks.append(
                torch.nn.Sequential(
                    torch.nn.ConvTranspose2d(in_ch, out_ch, 4, 2, 1),
                    torch.nn.LeakyReLU(0.2)
                    if i < len(rgb_channels) - 1
                    else torch.nn.Sigmoid(),
                )
            )

    def forward(self, z_id, z_exp, view_dir=None, bias_maps=None):
        B = z_id.shape[0]
        z = torch.cat([z_id, z_exp], dim=-1)

        x_vi = self.fc_vi(z).view(B, 256, 8, 8)
        for i, block in enumerate(self.vi_blocks):
            x_vi = block(x_vi)
            if bias_maps is not None and i < len(bias_maps):
                bm = bias_maps[i]
                if bm.shape[2:] == x_vi.shape[2:] and bm.shape[1] == x_vi.shape[1]:
                    x_vi = x_vi + bm

        x_vi = F.interpolate(
            x_vi, size=(self.uv_size, self.uv_size), mode="bilinear", align_corners=False
        )

        if view_dir is None:
            view_dir = torch.zeros(B, 3, device=z.device)
        z_rgb = torch.cat([z, view_dir], dim=-1)
        x_rgb = self.fc_rgb(z_rgb).view(B, 256, 8, 8)
        for i, block in enumerate(self.rgb_blocks):
            x_rgb = block(x_rgb)
            if bias_maps is not None and i < len(bias_maps):
                bm = bias_maps[i]
                if bm.shape[2:] == x_rgb.shape[2:] and bm.shape[1] == x_rgb.shape[1]:
                    x_rgb = x_rgb + bm

        x_rgb = F.interpolate(
            x_rgb, size=(self.uv_size, self.uv_size), mode="bilinear", align_corners=False
        )

        return torch.cat([x_vi, x_rgb], dim=1)


class ExpressionEncoder(torch.nn.Module):
    def __init__(self, z_dim=256):
        super().__init__()
        channels = [32, 32, 64, 64, 128, 128, 256, 256]
        layers = []
        in_ch = 6
        for out_ch in channels:
            layers.extend(
                [
                    torch.nn.Conv2d(in_ch, out_ch, 3, padding=1),
                    torch.nn.LeakyReLU(0.2),
                    torch.nn.AvgPool2d(2),
                ]
            )
            in_ch = out_ch
        self.encoder = torch.nn.Sequential(*layers)
        self.fc_mu = torch.nn.Linear(256 * 2 * 2, z_dim)
        self.fc_logvar = torch.nn.Linear(256 * 2 * 2, z_dim)

    def forward(self, delta_tex, delta_geo):
        x = torch.cat([delta_tex, delta_geo], dim=1)
        h = self.encoder(x).flatten(1)
        mu = self.fc_mu(h)
        logvar = self.fc_logvar(h)
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std, mu, logvar


class QuantumHeadModel(torch.nn.Module):
    def __init__(self, config=None):
        super().__init__()
        z_id = config.get("z_id_dim", 512) if config else 512
        z_exp = config.get("z_exp_dim", 256) if config else 256
        uv = config.get("uv_size", 256) if config else 256
        n_verts = config.get("guide_vertices", 7306) if config else 7306

        self.expression_encoder = ExpressionEncoder(z_dim=z_exp)
        self.neutral_decoder = NeutralDecoder(z_dim=z_id)
        self.guide_mesh_decoder = GuideMeshDecoder(z_id, z_exp, n_verts)
        self.gaussian_decoder = GaussianAvatarDecoder(z_id, z_exp, uv)

    def forward(self, z_id, z_exp, view_dir=None):
        bias_maps = self.neutral_decoder(z_id)
        guide_offsets = self.guide_mesh_decoder(z_id, z_exp)
        uv_maps = self.gaussian_decoder(z_id, z_exp, view_dir, bias_maps)
        return uv_maps, guide_offsets

    def encode_expression(self, delta_tex, delta_geo):
        return self.expression_encoder(delta_tex, delta_geo)


# Audio2FLAME Transformer
import math


class PeriodicPositionalEncoding(torch.nn.Module):
    def __init__(self, d_model, max_len=5000, period=25):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe[:, 0::2] += torch.sin(position * 2 * math.pi / period)
        pe[:, 1::2] += torch.cos(position * 2 * math.pi / period)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x):
        return x + self.pe[:, : x.size(1)]


class StyleEncoder(torch.nn.Module):
    def __init__(self, n_vertices=5023, d_model=512):
        super().__init__()
        self.net = torch.nn.Sequential(
            torch.nn.Linear(n_vertices * 3, 1024),
            torch.nn.ReLU(),
            torch.nn.Linear(1024, d_model),
        )

    def forward(self, template_mesh):
        return self.net(template_mesh.flatten(1))


class Audio2FLAMETransformer(torch.nn.Module):
    def __init__(self, d_model=512, nhead=8, num_layers=6, n_flame_params=53):
        super().__init__()
        self.d_model = d_model
        self.audio_proj = torch.nn.Linear(1024, d_model)
        self.pos_enc = PeriodicPositionalEncoding(d_model, period=25)
        decoder_layer = torch.nn.TransformerDecoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=2048,
            dropout=0.1,
            batch_first=True,
        )
        self.transformer_decoder = torch.nn.TransformerDecoder(
            decoder_layer, num_layers=num_layers
        )
        self.style_encoder = StyleEncoder(d_model=d_model)
        self.flame_head = torch.nn.Sequential(
            torch.nn.Linear(d_model, 256),
            torch.nn.ReLU(),
            torch.nn.Linear(256, n_flame_params),
        )

    def forward(self, audio_features, style_embedding, causal_mask=None):
        B, T, _ = audio_features.shape
        audio = self.audio_proj(audio_features)
        audio = self.pos_enc(audio)
        style = style_embedding.unsqueeze(1).expand(-1, T, -1)
        if causal_mask is None:
            causal_mask = torch.nn.Transformer.generate_square_subsequent_mask(
                T, device=audio.device
            )
        output = self.transformer_decoder(tgt=style, memory=audio, tgt_mask=causal_mask)
        return self.flame_head(output)


# ============================================================
# GAUSSIAN RENDERER (simplified for inference)
# ============================================================


class GaussianRenderer(torch.nn.Module):
    def __init__(self, uv_size=256, image_size=512):
        super().__init__()
        self.uv_size = uv_size
        self.image_size = image_size
        self.register_buffer(
            "uv_mask", torch.ones(uv_size, uv_size, dtype=torch.bool)
        )

    def uv_to_gaussians(self, uv_maps, position_map):
        pos_offset = uv_maps[:, 0:3]
        rotation = uv_maps[:, 3:7]
        scale = uv_maps[:, 7:10]
        opacity = uv_maps[:, 10:11]
        color = uv_maps[:, 11:14]
        positions = position_map + pos_offset
        mask = self.uv_mask.flatten()

        def flatten_uv(t):
            B, C, H, W = t.shape
            return t.reshape(B, C, H * W).permute(0, 2, 1)[:, mask]

        return {
            "positions": flatten_uv(positions),
            "rotations": F.normalize(flatten_uv(rotation), dim=-1),
            "scales": torch.exp(flatten_uv(scale)),
            "opacities": torch.sigmoid(flatten_uv(opacity)),
            "colors": flatten_uv(color),
        }

    def render(self, gaussians):
        try:
            import gsplat

            rendered = gsplat.rasterization(
                means=gaussians["positions"][0],
                quats=gaussians["rotations"][0],
                scales=gaussians["scales"][0],
                opacities=gaussians["opacities"][0].squeeze(-1),
                colors=gaussians["colors"][0],
                viewmats=torch.eye(4, device=gaussians["positions"].device).unsqueeze(0),
                Ks=torch.tensor(
                    [
                        [self.image_size, 0, self.image_size / 2],
                        [0, self.image_size, self.image_size / 2],
                        [0, 0, 1],
                    ],
                    device=gaussians["positions"].device,
                ).unsqueeze(0),
                width=self.image_size,
                height=self.image_size,
            )
            return rendered[0]
        except (ImportError, Exception):
            return self._neural_render(gaussians)

    def _neural_render(self, gaussians):
        B = gaussians["positions"].shape[0]
        pos_2d = gaussians["positions"][:, :, :2]
        colors = gaussians["colors"]
        opacities = gaussians["opacities"]
        H = W = self.image_size
        img = torch.zeros(B, 3, H, W, device=pos_2d.device)
        px = ((pos_2d[:, :, 0] + 1) * 0.5 * W).long().clamp(0, W - 1)
        py = ((pos_2d[:, :, 1] + 1) * 0.5 * H).long().clamp(0, H - 1)
        for b in range(B):
            for c in range(3):
                img[b, c].index_put_(
                    (py[b], px[b]),
                    colors[b, :, c] * opacities[b, :, 0],
                    accumulate=True,
                )
        return img.clamp(0, 1)


# ============================================================
# INFERENCE ENGINE
# ============================================================


class QuantumHeadInference:
    """Full inference pipeline: audio + image → video frames."""

    def __init__(self, weights_dir=WEIGHTS_DIR):
        self.weights_dir = weights_dir
        self.device = DEVICE
        self.model = None
        self.audio_model = None
        self.renderer = None
        self.wav2vec = None
        self.wav2vec_processor = None
        self.config = None
        self.loaded = False

    def load(self):
        """Load model weights and initialize pipeline."""
        config_path = os.path.join(self.weights_dir, "config.json")
        if os.path.exists(config_path):
            with open(config_path) as f:
                self.config = json.load(f)
        else:
            self.config = {
                "z_id_dim": 512,
                "z_exp_dim": 256,
                "uv_size": 256,
                "guide_vertices": 7306,
            }

        # Load QuantumHead model
        self.model = QuantumHeadModel(self.config).to(self.device)
        qh_path = os.path.join(self.weights_dir, "quantumhead.pt")
        if os.path.exists(qh_path):
            state_dict = torch.load(qh_path, map_location=self.device, weights_only=True)
            self.model.load_state_dict(state_dict)
            logger.info("Loaded QuantumHead weights: %s", qh_path)
        else:
            logger.warning("No QuantumHead weights at %s — using random init", qh_path)
        self.model.eval()

        # Load Audio2FLAME model
        self.audio_model = Audio2FLAMETransformer().to(self.device)
        a2f_path = os.path.join(self.weights_dir, "audio2flame.pt")
        if os.path.exists(a2f_path):
            state_dict = torch.load(a2f_path, map_location=self.device, weights_only=True)
            self.audio_model.load_state_dict(state_dict)
            logger.info("Loaded Audio2FLAME weights: %s", a2f_path)
        self.audio_model.eval()

        # Gaussian renderer
        self.renderer = GaussianRenderer(
            uv_size=self.config.get("uv_size", 256), image_size=IMAGE_SIZE
        ).to(self.device)

        # Wav2Vec2
        try:
            from transformers import Wav2Vec2Processor, Wav2Vec2Model

            self.wav2vec_processor = Wav2Vec2Processor.from_pretrained(
                "facebook/wav2vec2-large-960h"
            )
            self.wav2vec = Wav2Vec2Model.from_pretrained(
                "facebook/wav2vec2-large-960h"
            ).to(self.device)
            self.wav2vec.eval()
            logger.info("Wav2Vec2 loaded")
        except ImportError:
            logger.warning("transformers not installed — Wav2Vec2 disabled")

        self.loaded = True
        logger.info("QuantumHead inference engine ready on %s", self.device)

    def extract_audio_features(self, audio_path):
        """Extract Wav2Vec2 features from audio file."""
        import librosa

        waveform, sr = librosa.load(audio_path, sr=16000)
        inputs = self.wav2vec_processor(
            waveform, sampling_rate=16000, return_tensors="pt"
        )
        with torch.no_grad():
            outputs = self.wav2vec(inputs.input_values.to(self.device))
        features = outputs.last_hidden_state  # (1, T, 1024)

        # Resample to 25fps
        num_frames = int(len(waveform) / 16000 * FPS)
        features = F.interpolate(
            features.permute(0, 2, 1), size=num_frames, mode="linear", align_corners=False
        ).permute(0, 2, 1)
        return features, num_frames

    @torch.no_grad()
    def generate_frames(self, audio_path, source_image=None, z_id=None):
        """Generate video frames from audio.

        Args:
            audio_path: Path to audio file
            source_image: Optional source image (numpy HWC uint8)
            z_id: Optional identity code (if not provided, uses random)

        Returns:
            List of frames (numpy HWC uint8)
        """
        if not self.loaded:
            self.load()

        # Extract audio features
        audio_features, num_frames = self.extract_audio_features(audio_path)
        logger.info("Audio: %d frames at %dfps", num_frames, FPS)

        # Identity code
        if z_id is None:
            z_id = torch.randn(1, self.config["z_id_dim"], device=self.device)

        # Style embedding (from template mesh — simplified)
        style = torch.randn(1, 512, device=self.device)

        # Audio → FLAME params
        flame_params = self.audio_model(audio_features, style)  # (1, T, 53)
        logger.info("FLAME params: %s", flame_params.shape)

        # Generate frames
        frames = []
        for t in range(num_frames):
            # Expression from FLAME params → z_exp
            exp_params = flame_params[:, t, :50]  # 50 expression params
            z_exp = F.pad(exp_params, (0, self.config["z_exp_dim"] - 50))

            # Decode to UV maps
            uv_maps, guide = self.model(z_id, z_exp.unsqueeze(0) if z_exp.dim() == 1 else z_exp)

            # Render
            pos_map = torch.zeros_like(uv_maps[:, :3])
            gaussians = self.renderer.uv_to_gaussians(uv_maps, pos_map)
            rendered = self.renderer._neural_render(gaussians)

            # To numpy
            frame = (rendered[0].permute(1, 2, 0).cpu().numpy() * 255).astype(np.uint8)
            frames.append(frame)

        return frames

    def generate_video(self, audio_path, output_path, source_image=None):
        """Generate video from audio + optional source image."""
        import cv2

        frames = self.generate_frames(audio_path, source_image)

        # Write video
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_path, fourcc, FPS, (IMAGE_SIZE, IMAGE_SIZE))
        for frame in frames:
            out.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        out.release()

        # Add audio
        final_path = output_path.replace(".mp4", "_final.mp4")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i", output_path,
                "-i", audio_path,
                "-c:v", "libx264",
                "-c:a", "aac",
                "-shortest",
                final_path,
            ],
            capture_output=True,
            check=True,
        )
        os.replace(final_path, output_path)

        logger.info("Video saved: %s (%d frames)", output_path, len(frames))
        return output_path


# ============================================================
# FASTAPI SERVER
# ============================================================

engine = QuantumHeadInference()


def create_quantumhead_router():
    """Create FastAPI router for QuantumHead endpoints."""
    from fastapi import APIRouter

    router = APIRouter(prefix="/quantumhead", tags=["quantumhead"])

    @router.get("/status")
    async def status():
        weights_exist = os.path.exists(os.path.join(WEIGHTS_DIR, "quantumhead.pt"))
        return {
            "loaded": engine.loaded,
            "device": DEVICE,
            "weights_dir": WEIGHTS_DIR,
            "weights_exist": weights_exist,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "vram_gb": (
                torch.cuda.get_device_properties(0).total_mem / 1e9
                if torch.cuda.is_available()
                else 0
            ),
        }

    @router.post("/generate")
    async def generate(
        background_tasks: BackgroundTasks,
        audio_url: Optional[str] = Form(None),
        audio: Optional[UploadFile] = File(None),
        source_image: Optional[UploadFile] = File(None),
        text: Optional[str] = Form(None),
    ):
        """Generate avatar video from audio/text + optional source image."""
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        job_id = str(uuid.uuid4())[:8]

        # Get audio
        audio_path = os.path.join(OUTPUT_DIR, f"{job_id}_audio.wav")
        if audio:
            content = await audio.read()
            with open(audio_path, "wb") as f:
                f.write(content)
        elif audio_url:
            import requests as http_requests
            resp = http_requests.get(audio_url, timeout=30)
            resp.raise_for_status()
            with open(audio_path, "wb") as f:
                f.write(resp.content)
        elif text:
            # Generate via local TTS
            import requests as http_requests
            tts_resp = http_requests.post(
                "http://localhost:8000/speak",
                json={"text": text, "voice_id": "960f89fc"},
                timeout=60,
            )
            tts_resp.raise_for_status()
            tts_data = tts_resp.json()
            tts_url = tts_data.get("audio_url", tts_data.get("url", ""))
            if tts_url.startswith("/"):
                tts_url = f"http://localhost:8000{tts_url}"
            audio_resp = http_requests.get(tts_url, timeout=30)
            with open(audio_path, "wb") as f:
                f.write(audio_resp.content)
        else:
            raise HTTPException(400, "Provide audio, audio_url, or text")

        # Source image
        src_img = None
        if source_image:
            import cv2
            content = await source_image.read()
            nparr = np.frombuffer(content, np.uint8)
            src_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            src_img = cv2.cvtColor(src_img, cv2.COLOR_BGR2RGB)

        # Generate video
        output_path = os.path.join(OUTPUT_DIR, f"{job_id}.mp4")

        try:
            engine.generate_video(audio_path, output_path, src_img)
        except Exception as e:
            logger.error("Generation failed: %s", e, exc_info=True)
            raise HTTPException(500, f"Generation failed: {e}")

        return {
            "job_id": job_id,
            "video_url": f"/quantumhead/video/{job_id}.mp4",
            "frames": "completed",
        }

    @router.get("/video/{filename}")
    async def get_video(filename: str):
        # Prevent path traversal
        safe_name = os.path.basename(filename)
        path = os.path.join(OUTPUT_DIR, safe_name)
        if not os.path.exists(path):
            raise HTTPException(404, "Video not found")
        return FileResponse(path, media_type="video/mp4")

    @router.post("/upload-weights")
    async def upload_weights(weights: UploadFile = File(...)):
        """Upload trained model weights."""
        os.makedirs(WEIGHTS_DIR, exist_ok=True)
        safe_name = os.path.basename(weights.filename)
        dest = os.path.join(WEIGHTS_DIR, safe_name)
        content = await weights.read()
        with open(dest, "wb") as f:
            f.write(content)
        logger.info("Uploaded weights: %s (%d bytes)", dest, len(content))
        # Reload model
        engine.loaded = False
        return {"path": dest, "size_mb": len(content) / 1e6}

    @router.post("/pull-weights")
    async def pull_weights(url: str = Form(...)):
        """Pull weights from a URL (Google Drive, etc)."""
        os.makedirs(WEIGHTS_DIR, exist_ok=True)
        import requests as http_requests
        resp = http_requests.get(url, timeout=300, stream=True)
        resp.raise_for_status()
        filename = url.split("/")[-1].split("?")[0] or "weights.pt"
        safe_name = os.path.basename(filename)
        dest = os.path.join(WEIGHTS_DIR, safe_name)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        engine.loaded = False
        return {"path": dest, "size_mb": os.path.getsize(dest) / 1e6}

    @router.post("/reload")
    async def reload():
        """Reload model weights."""
        engine.loaded = False
        engine.load()
        return {"status": "reloaded", "loaded": engine.loaded}

    return router


# ============================================================
# STANDALONE SERVER
# ============================================================

app = FastAPI(title="QuantumHead Inference Server", version="0.1.0")
app.include_router(create_quantumhead_router())


@app.on_event("startup")
async def startup():
    """Load model on startup if weights exist."""
    if os.path.exists(os.path.join(WEIGHTS_DIR, "quantumhead.pt")):
        engine.load()
    else:
        logger.info("No weights found at %s — waiting for upload", WEIGHTS_DIR)


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--weights", type=str, default=WEIGHTS_DIR)
    args = parser.parse_args()

    WEIGHTS_DIR = args.weights
    engine.weights_dir = args.weights

    uvicorn.run(app, host=args.host, port=args.port)
