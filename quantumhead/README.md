# QuantumHead — 3DGS Talking Head Avatar

Custom 3D Gaussian Splatting avatar system built from SOTA research papers.

## Architecture

```
Single Image → DECA (FLAME fit) → UV-Space Gaussians → 3DGS Render
Audio (WAV) → Wav2Vec2 → Transformer → FLAME params → Animate Gaussians
```

Based on:
- **GAGAvatar** (246 FPS) — UV-space Gaussians + PanoHead 3D GAN
- **GaussianHeadTalk** — Wobble-free audio-driven via FLAME param prediction
- **UHAP** (SIGGRAPH Asia 2025) — Universal head avatar prior with expression diffusion

## Pipeline

```
┌─────────────────────────────────────────────────────┐
│  Google Colab (A100)                                │
│  QuantumHead_Training.ipynb                         │
│  - FLAME fitting (DECA)                             │
│  - UV-Space Gaussian decoder training               │
│  - Audio2FLAME transformer training                 │
│  - Expression diffusion model training              │
│  → Push weights to spike2                           │
└───────────────────────┬─────────────────────────────┘
                        │ weights (SCP / API / Drive)
                        ▼
┌─────────────────────────────────────────────────────┐
│  spike2 (RTX 2080 SUPER)                            │
│  quantumhead_server.py                              │
│  - Load trained QuantumHead + Audio2FLAME           │
│  - Wav2Vec2 audio feature extraction                │
│  - Real-time Gaussian splatting render              │
│  - POST /quantumhead/generate                       │
│  - Integrates with existing TTS at :8000            │
└─────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Train on Colab

1. Open `QuantumHead_Training.ipynb` in Google Colab
2. Set runtime to **A100 GPU**
3. Upload FLAME model (`generic_model.pkl` from https://flame.is.tue.mpg.de/)
4. Upload training data (selfies/HDTF/VFHQ)
5. Run all cells — weights auto-push to spike2

### 2. Deploy on spike2

```bash
# On spike2
cd /root/quantumhead
pip install -r requirements.txt

# Run inference server (separate from main TTS server)
python quantumhead_server.py --port 8100

# Or integrate with existing server.py:
# from quantumhead_server import create_quantumhead_router
# app.include_router(create_quantumhead_router())
```

### 3. Generate Avatar Video

```bash
# Via API
curl -X POST https://voice.quantum-forge.io:8100/quantumhead/generate \
  -F "text=Hello from QuantumHead!" \
  -F "source_image=@selfie.jpg"

# Check status
curl https://voice.quantum-forge.io:8100/quantumhead/status
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/quantumhead/status` | Model status & GPU info |
| POST | `/quantumhead/generate` | Generate avatar video |
| GET | `/quantumhead/video/{filename}` | Download generated video |
| POST | `/quantumhead/upload-weights` | Upload trained weights |
| POST | `/quantumhead/pull-weights` | Pull weights from URL |
| POST | `/quantumhead/reload` | Reload model weights |

## Model Architecture

| Component | Parameters | Purpose |
|-----------|-----------|---------|
| QuantumHeadModel | ~50M | UV Gaussian attribute decoder |
| Audio2FLAMETransformer | ~30M | Audio → FLAME expression params |
| ExpressionDiffusion | ~25M | Rich expression generation via DDPM |
| GaussianRenderer | - | 3DGS → image rasterization |

## Files

```
quantumhead/
├── QuantumHead_Training.ipynb   # Colab training notebook
├── quantumhead_server.py        # spike2 inference server
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```
