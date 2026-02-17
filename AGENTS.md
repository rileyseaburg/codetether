---

## CodeTether Avatar Pipeline

Proprietary AI avatar system targeting Synthesia-quality talking-head video from audio input. Runs on **spike2** (`192.168.50.119`), RTX 2080 SUPER 8GB.

### Architecture

```
TTS Audio → LatentSync (lip-sync @ 512×512) → LivePortrait (reenact @ 1080×1080) → FFmpeg (1920×1080) → YouTube
```

### Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| LatentSync 1.6 | **WORKING** (static photo) | ByteDance, Apache 2.0, 512×512, ~1.9GB VRAM w/ CPU offload |
| LivePortrait | **WORKING** | Kuaishou, 1080×1080, video-driven reenactment |
| TTS (Qwen3-TTS) | **RUNNING** | `qwen-tts-api.service`, port 8000, voice_id `960f89fc` |
| YouTube Upload | **WORKING** | `POST http://localhost:8000/youtube/upload` |
| Motion-video input | **BLOCKED** | Face detector crashes on head turns — **one patch needed** |

### The One Bug (BLOCKER)

**File:** `/root/LatentSync/latentsync/utils/image_processor.py` → `affine_transform()`
**Problem:** `raise RuntimeError("Face not detected")` when InsightFace can't find a face (e.g., head turns in motion video)
**Fix:** Cache the last successful face detection result and reuse it when detection fails, instead of crashing.
**Impact:** This is the ONLY thing preventing motion-video-based avatars from working end-to-end.

### Key Files on spike2

| File | Purpose |
|------|---------|
| `/root/LatentSync/` | Core lip-sync engine (installed, deps working, checkpoints present) |
| `/root/LatentSync/scripts/inference_lowvram.py` | Custom low-VRAM inference with CPU offloading, VAE slicing/tiling |
| `/root/LatentSync/latentsync/utils/image_processor.py` | Contains the face detector bug to fix |
| `/root/LatentSync/latentsync/pipelines/lipsync_pipeline.py` | Main pipeline (477 lines, audited) |
| `/root/LivePortrait/` | Photorealistic 2D portrait reenactment |
| `/root/qwen-tts-api/youtube_publisher.py` | YouTube OAuth upload (~11.6KB) |
| `/root/MuseTalk/data/video/riley.png` | Riley selfie (1080×1080) |
| `/tmp/lam_demo_audio.wav` | TTS audio (41.2s, 24kHz mono) |
| `/root/duix_avatar_data/face2face/riley_model_hd2.mp4` | Real Riley motion video (45s) — target driving video |

### Checkpoints

- `checkpoints/latentsync_unet.pt` — 4.8GB UNet (AnimateDiff-based, 13-channel input)
- `checkpoints/whisper/tiny.pt` — Whisper audio encoder
- `checkpoints/auxiliary/` — InsightFace buffalo_l (auto-downloaded)

### Environments

| Env | Python | Torch | Used By |
|-----|--------|-------|---------|
| `latentsync-env` | 3.10 | 2.5.1+cu121 | LatentSync |
| `lam-env` | 3.10 | 2.3.0+cu121 | LivePortrait |

### Inference Command

```bash
# LatentSync (low-VRAM)
conda activate latentsync-env
cd /root/LatentSync
python scripts/inference_lowvram.py \
  --unet_config_path configs/unet/stage2_512.yaml \
  --inference_ckpt_path checkpoints/latentsync_unet.pt \
  --inference_steps 20 --guidance_scale 1.5 \
  --video_path <input_video> \
  --audio_path <audio> \
  --video_out_path <output>

# LivePortrait
conda activate lam-env
cd /root/LivePortrait
python inference.py -s riley.png -d <driving_video> -o <output_dir>
```

### Published YouTube Videos

| # | URL | Result |
|---|-----|--------|
| v6 | `https://www.youtube.com/watch?v=-nsQUCNPIZM` | LatentSync+LivePortrait static photo — **REJECTED** ("so 2014") |
| v7 | Not yet | Blocked by face detector crash on motion video |

### Next Steps

1. **Patch `affine_transform()`** — cache last good face crop, skip crash on detection failure
2. **Re-run LatentSync** with `riley_model_hd2.mp4` (45s motion video) as input
3. **Chain through LivePortrait** → FFmpeg composite → YouTube upload
4. **Deliver YouTube URL** (only accepted deliverable)

### SSH Access

```bash
ssh -o BatchMode=yes root@192.168.50.119 'bash --norc --noprofile -c "COMMAND"'
```

### GPU State

RTX 2080 SUPER: ~4.1GB used / ~3.9GB free (TTS service running). LatentSync needs ~1.9GB with CPU offload — fits alongside TTS.

---

## OPA Policy Engine

The project uses **Open Policy Agent (OPA)** as a centralized authorization engine across both the Python A2A server and the Rust CodeTether agent.

### Key Files

| Layer | File | Purpose |
|-------|------|---------|
| Rego policies | `policies/authz.rego` | RBAC permission checks |
| Rego policies | `policies/api_keys.rego` | API key scope enforcement |
| Rego policies | `policies/tenants.rego` | Tenant isolation |
| Static data | `policies/data.json` | Role→permission mappings |
| Python client | `a2a_server/policy.py` | OPA HTTP client + `require_permission()` dependency |
| Python middleware | `a2a_server/policy_middleware.py` | Centralized auth middleware (~160 route rules) |
| Rust client | `codetether-agent/src/server/policy.rs` | OPA HTTP client + local eval fallback |
| Rust middleware | `codetether-agent/src/server/mod.rs` | `POLICY_ROUTES` + `policy_middleware()` |
| Helm | `chart/a2a-server/templates/opa-configmap.yaml` | OPA sidecar ConfigMap |

### Testing

```bash
# Run all policy tests (Rego + Python + Rust)
make policy-test

# Individual test suites
opa test policies/ -v                    # 41 Rego tests
python -m pytest tests/test_policy.py     # 23 Python tests
python -m pytest tests/test_policy_middleware.py  # 83 middleware tests
cargo test policy                         # 9 Rust tests
```

### RBAC Roles

`admin` > `a2a-admin` > `operator` > `editor` > `viewer`

Permissions follow `resource:action` format (e.g., `task:read`, `agent:admin`). See `policies/data.json` for the full mapping.

---

## CodeTether Releases

CodeTether binaries are automatically built and published to **GitHub Releases** when you create a tag matching `agent-v*` or `v*`.

### Release Process

**Automatic (GitHub Actions):**
```bash
# Trigger a release from the current version in package.json
make release-agent

# Or manually create and push a tag
git tag agent-v1.1.25
git push origin agent-v1.1.25
```

The GitHub Actions workflow (`.github/workflows/release-agent.yml`) will:
1. Build binaries for all 11 platforms (Linux, macOS, Windows - x64/ARM64/baseline/musl)
2. Package them as `.tar.gz` (Unix) or `.zip` (Windows)
3. Create a GitHub Release with all binaries attached

**Manual (Local Build):**
```bash
# Build locally and upload to GitHub release (requires gh CLI)
make release-agent-local
```

### Available Platforms

| Platform | File | Notes |
|----------|------|-------|
| Linux x64 | `agent-vX.X.X-linux-x64.tar.gz` | Standard glibc build |
| Linux x64 (baseline) | `agent-vX.X.X-linux-x64-baseline.tar.gz` | For older CPUs without AVX2 |
| Linux x64 (musl) | `agent-vX.X.X-linux-x64-musl.tar.gz` | For Alpine Linux |
| Linux ARM64 | `agent-vX.X.X-linux-arm64.tar.gz` | ARM64 glibc |
| Linux ARM64 (musl) | `agent-vX.X.X-linux-arm64-musl.tar.gz` | ARM64 musl |
| macOS x64 | `agent-vX.X.X-darwin-x64.tar.gz` | Intel Macs |
| macOS x64 (baseline) | `agent-vX.X.X-darwin-x64-baseline.tar.gz` | Intel Macs without AVX2 |
| macOS ARM64 | `agent-vX.X.X-darwin-arm64.tar.gz` | Apple Silicon |
| Windows x64 | `agent-vX.X.X-windows-x64.zip` | Standard build |
| Windows x64 (baseline) | `agent-vX.X.X-windows-x64-baseline.zip` | For older CPUs |

### Installation for End Users

**Linux/macOS (Bash):**
```bash
curl -fsSL https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-agent.sh | bash
```

**Windows (PowerShell):**
```powershell
Invoke-Expression (Invoke-WebRequest -Uri "https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-agent.ps1" -UseBasicParsing).Content
```

**Manual download:**
1. Go to [GitHub Releases](https://github.com/rileyseaburg/A2A-Server-MCP/releases)
2. Download the appropriate binary for your platform
3. Extract and place in your PATH

### Release File Locations

- **Workflow:** `.github/workflows/release-agent.yml`
- **Install Scripts:**
  - `scripts/install-agent.sh` (Linux/macOS)
  - `scripts/install-agent.ps1` (Windows)
- **Makefile Targets:**
  - `build-agent` - Build local binaries
  - `release-agent` - Trigger GitHub Actions release
  - `release-agent-local` - Build and upload locally

## Repository Structure

This is a monorepo. `codetether-agent/` is a git submodule with its own `Cargo.toml`.

- **Rust project root:** `codetether-agent/` (run all cargo commands from here)
- **Python MCP server:** `a2a_server/`
- **React dashboard:** `marketing-site/`
- **Proto definitions:** `specification/grpc/`
- **Buf config:** `specification/grpc/buf.gen.yaml`

When working in a git worktree, `cd codetether-agent/` before running `cargo check`, `cargo clippy`, `cargo test`, or `cargo build`. The worktree root is `A2A-Server-MCP/`, not the crate root.
