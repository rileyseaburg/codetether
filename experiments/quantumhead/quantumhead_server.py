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

import math
import torch.nn as nn


class ConvBlock(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.conv = nn.Conv2d(in_ch, out_ch, 3, padding=1)
        self.norm = nn.InstanceNorm2d(out_ch)
        self.act = nn.LeakyReLU(0.2, inplace=True)

    def forward(self, x):
        return self.act(self.norm(self.conv(x)))


class UVDecoder(nn.Module):
    """Decodes latent -> UV-space Gaussian attribute maps.
    Output channels: position_offset(3) + rotation(4) + scale(3) + opacity(1) + color(3) = 14
    """
    def __init__(self, z_dim, uv_size=256, out_channels=14):
        super().__init__()
        self.uv_size = uv_size
        self.init_size = 4
        self.fc = nn.Linear(z_dim, 256 * self.init_size * self.init_size)
        channels = [256, 256, 128, 128, 64, 64]
        self.blocks = nn.ModuleList()
        in_ch = 256
        for out_ch in channels:
            self.blocks.append(nn.Sequential(
                nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False),
                ConvBlock(in_ch, out_ch),
                ConvBlock(out_ch, out_ch),
            ))
            in_ch = out_ch
        self.head = nn.Conv2d(channels[-1], out_channels, 1)

    def forward(self, z):
        x = self.fc(z).view(-1, 256, self.init_size, self.init_size)
        for block in self.blocks:
            x = block(x)
        return self.head(x)


class ExpressionEncoder(nn.Module):
    """Encodes UV attribute difference maps -> expression latent Z_exp."""
    def __init__(self, in_channels=14, z_dim=256, uv_size=256):
        super().__init__()
        channels = [32, 64, 64, 128, 128, 256]
        layers = []
        in_ch = in_channels
        for out_ch in channels:
            layers.extend([
                nn.Conv2d(in_ch, out_ch, 4, 2, 1),
                nn.InstanceNorm2d(out_ch),
                nn.LeakyReLU(0.2, inplace=True),
            ])
            in_ch = out_ch
        self.encoder = nn.Sequential(*layers)
        self.fc_mu = nn.Linear(256 * 4 * 4, z_dim)
        self.fc_logvar = nn.Linear(256 * 4 * 4, z_dim)

    def forward(self, uv_diff):
        h = self.encoder(uv_diff).flatten(1)
        mu = self.fc_mu(h)
        logvar = self.fc_logvar(h)
        if self.training:
            std = torch.exp(0.5 * logvar)
            z = mu + std * torch.randn_like(std)
        else:
            z = mu
        return z, mu, logvar


class QuantumHeadModel(nn.Module):
    """Full model: Z_id + Z_exp -> UV Gaussian maps + guide mesh offsets."""
    def __init__(self, z_id_dim=512, z_exp_dim=256, uv_size=256, n_vertices=5023, config=None):
        super().__init__()
        if config:
            z_id_dim = config.get("z_id_dim", z_id_dim)
            z_exp_dim = config.get("z_exp_dim", z_exp_dim)
            uv_size = config.get("uv_size", uv_size)
            n_vertices = config.get("n_vertices", config.get("guide_vertices", n_vertices))
        self.z_id_dim = z_id_dim
        self.z_exp_dim = z_exp_dim
        self.neutral_decoder = UVDecoder(z_id_dim, uv_size, out_channels=14)
        self.expr_decoder = UVDecoder(z_id_dim + z_exp_dim, uv_size, out_channels=14)
        self.expr_encoder = ExpressionEncoder(14, z_exp_dim, uv_size)
        self.mesh_decoder = nn.Sequential(
            nn.Linear(z_id_dim + z_exp_dim, 1024),
            nn.ReLU(inplace=True),
            nn.Linear(1024, 2048),
            nn.ReLU(inplace=True),
            nn.Linear(2048, n_vertices * 3),
        )
        self.n_vertices = n_vertices

    def forward(self, z_id, z_exp):
        uv_neutral = self.neutral_decoder(z_id)
        z_combined = torch.cat([z_id, z_exp], dim=-1)
        uv_delta = self.expr_decoder(z_combined)
        uv_maps = uv_neutral + uv_delta
        mesh_offsets = self.mesh_decoder(z_combined).view(-1, self.n_vertices, 3)
        return uv_maps, mesh_offsets

    def encode_expression(self, uv_target, uv_neutral):
        diff = uv_target - uv_neutral
        z_exp, mu, logvar = self.expr_encoder(diff)
        return z_exp, mu, logvar


class Audio2FLAMETransformer(nn.Module):
    """Predicts FLAME expression+jaw params from Wav2Vec2 audio features."""
    def __init__(self, d_model=512, nhead=8, num_layers=6, n_flame_params=53):
        super().__init__()
        self.d_model = d_model
        self.n_flame_params = n_flame_params
        self.audio_proj = nn.Linear(1024, d_model)
        pe = torch.zeros(5000, d_model)
        position = torch.arange(0, 5000, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))
        decoder_layer = nn.TransformerDecoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=2048,
            dropout=0.1, batch_first=True
        )
        self.decoder = nn.TransformerDecoder(decoder_layer, num_layers=num_layers)
        self.head = nn.Sequential(
            nn.Linear(d_model, 256),
            nn.ReLU(inplace=True),
            nn.Linear(256, n_flame_params),
        )

    def forward(self, audio_features):
        B, T, _ = audio_features.shape
        x = self.audio_proj(audio_features) + self.pe[:, :T]
        mask = nn.Transformer.generate_square_subsequent_mask(T, device=x.device)
        out = self.decoder(x, x, tgt_mask=mask)
        return self.head(out)


class GaussianRenderer(nn.Module):
    """Differentiable renderer: UV Gaussian maps -> 2D image."""
    def __init__(self, uv_size=256, image_size=512):
        super().__init__()
        self.uv_size = uv_size
        self.image_size = image_size
        self.renderer = nn.Sequential(
            ConvBlock(14, 64),
            ConvBlock(64, 128),
            nn.Upsample(scale_factor=2, mode='bilinear', align_corners=False),
            ConvBlock(128, 64),
            ConvBlock(64, 32),
            nn.Conv2d(32, 3, 1),
            nn.Sigmoid(),
        )

    def forward(self, uv_maps):
        return self.renderer(uv_maps)


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

        # Map config keys
        if "n_vertices" in self.config and "guide_vertices" not in self.config:
            self.config["guide_vertices"] = self.config["n_vertices"]

        # Load QuantumHead model (keep in fp16 to save VRAM)
        self.model = QuantumHeadModel(config=self.config).half().to(self.device)
        for qh_name in ["quantumhead_fp16.pt", "quantumhead.pt"]:
            qh_path = os.path.join(self.weights_dir, qh_name)
            if os.path.exists(qh_path):
                state_dict = torch.load(qh_path, map_location=self.device, weights_only=True)
                state_dict = {k: v.half() for k, v in state_dict.items()}
                self.model.load_state_dict(state_dict)
                logger.info("Loaded QuantumHead weights: %s", qh_path)
                break
        else:
            logger.warning("No QuantumHead weights found — using random init")
        self.model.eval()

        # Load Audio2FLAME model (fp16)
        self.audio_model = Audio2FLAMETransformer().half().to(self.device)
        for a2f_name in ["audio2flame_fp16.pt", "audio2flame.pt"]:
            a2f_path = os.path.join(self.weights_dir, a2f_name)
            if os.path.exists(a2f_path):
                state_dict = torch.load(a2f_path, map_location=self.device, weights_only=True)
                state_dict = {k: v.half() for k, v in state_dict.items()}
                self.audio_model.load_state_dict(state_dict)
                logger.info("Loaded Audio2FLAME weights: %s", a2f_path)
                break
        self.audio_model.eval()

        # Gaussian renderer (fp16)
        self.renderer = GaussianRenderer(
            uv_size=self.config.get("uv_size", 256), image_size=IMAGE_SIZE
        ).half().to(self.device)
        for r_name in ["renderer_fp16.pt", "renderer.pt"]:
            r_path = os.path.join(self.weights_dir, r_name)
            if os.path.exists(r_path):
                state_dict = torch.load(r_path, map_location=self.device, weights_only=True)
                state_dict = {k: v.half() for k, v in state_dict.items()}
                self.renderer.load_state_dict(state_dict, strict=False)
                logger.info("Loaded renderer weights: %s", r_path)
                break

        # Wav2Vec2
        try:
            from transformers import Wav2Vec2Processor, Wav2Vec2Model

            self.wav2vec_processor = Wav2Vec2Processor.from_pretrained(
                "facebook/wav2vec2-large-960h"
            )
            self.wav2vec = Wav2Vec2Model.from_pretrained(
                "facebook/wav2vec2-large-960h"
            ).half().to(self.device)
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
            outputs = self.wav2vec(inputs.input_values.half().to(self.device))
        features = outputs.last_hidden_state  # (1, T, 1024) fp16

        # Resample to 25fps
        num_frames = int(len(waveform) / 16000 * FPS)
        features = F.interpolate(
            features.float().permute(0, 2, 1), size=num_frames, mode="linear", align_corners=False
        ).permute(0, 2, 1).half()
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

        torch.cuda.empty_cache()

        # Extract audio features
        audio_features, num_frames = self.extract_audio_features(audio_path)
        logger.info("Audio: %d frames at %dfps", num_frames, FPS)

        # Identity code (fp16)
        if z_id is None:
            z_id = torch.randn(1, self.config["z_id_dim"], device=self.device, dtype=torch.float16)

        # Audio → FLAME params
        flame_params = self.audio_model(audio_features)  # (1, T, 53)
        logger.info("FLAME params: %s", flame_params.shape)

        # Generate frames
        frames = []
        for t in range(num_frames):
            # Expression from FLAME params → z_exp
            exp_params = flame_params[:, t, :50]  # 50 expression params
            z_exp = F.pad(exp_params, (0, self.config["z_exp_dim"] - 50))

            # Decode to UV maps
            uv_maps, guide = self.model(z_id, z_exp.unsqueeze(0) if z_exp.dim() == 1 else z_exp)

            # Render UV maps → RGB image
            rendered = self.renderer(uv_maps)

            # To numpy (cast to float32 for numpy conversion)
            frame = (rendered[0].float().permute(1, 2, 0).cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
            frames.append(frame)

        torch.cuda.empty_cache()
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
        weights_exist = any(
            os.path.exists(os.path.join(WEIGHTS_DIR, n))
            for n in ["quantumhead_fp16.pt", "quantumhead.pt"]
        )
        return {
            "loaded": engine.loaded,
            "device": DEVICE,
            "weights_dir": WEIGHTS_DIR,
            "weights_exist": weights_exist,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "vram_gb": (
                torch.cuda.get_device_properties(0).total_memory / 1e9
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
            # Generate via local TTS (Qwen voice clone API — returns raw WAV)
            import requests as http_requests
            voice_id = "960f89fc"
            tts_resp = http_requests.post(
                f"http://localhost:8000/voices/{voice_id}/speak",
                data={"text": text},
                timeout=120,
            )
            tts_resp.raise_for_status()
            with open(audio_path, "wb") as f:
                f.write(tts_resp.content)
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
    async def pull_weights(
        bucket: str = Form("veo-spotless"),
        prefix: str = Form("quantumhead/weights"),
        project: str = Form("spotlessbinco"),
    ):
        """Pull weights from GCS bucket."""
        os.makedirs(WEIGHTS_DIR, exist_ok=True)
        from google.cloud import storage as gcs_storage

        client = gcs_storage.Client(project=project)
        gcs_bucket = client.bucket(bucket)
        blobs = list(gcs_bucket.list_blobs(prefix=prefix))
        weight_blobs = [b for b in blobs if b.name.endswith((".pt", ".pkl", ".json"))]

        if not weight_blobs:
            return {"error": f"No weights found at gs://{bucket}/{prefix}/"}

        downloaded = []
        for blob in weight_blobs:
            fname = os.path.basename(blob.name)
            dest = os.path.join(WEIGHTS_DIR, fname)
            blob.download_to_filename(dest)
            downloaded.append({"file": fname, "size_mb": os.path.getsize(dest) / 1e6})

        engine.loaded = False
        return {"downloaded": downloaded, "source": f"gs://{bucket}/{prefix}/"}

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
    if any(
        os.path.exists(os.path.join(WEIGHTS_DIR, n))
        for n in ["quantumhead_fp16.pt", "quantumhead.pt"]
    ):
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
