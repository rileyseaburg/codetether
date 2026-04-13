# Voice Agent

The CodeTether Voice Agent enables real-time voice interactions with AI agents through LiveKit integration.

## Overview

The voice agent provides:
- **Real-time voice streaming** via LiveKit
- **Session playback** for reviewing conversations
- **GLM-5 reasoning** with OpenAI-compatible chat completions
- **Local Qwen STT/TTS** for speech input and output
- **Voice selector** for choosing different AI voice models
- **Playback controls** (pause, resume, speed adjustment)

## Installation

### Via Helm Chart

```bash
helm install codetether-voice-agent oci://registry.quantum-forge.net/library/codetether-voice-agent \
  --namespace codetether --create-namespace
```

### From Source

```bash
cd codetether_voice_agent
pip install -r requirements.txt
```

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LIVEKIT_URL` | LiveKit server URL | `wss://livekit.codetether.run` |
| `LIVEKIT_API_KEY` | LiveKit API key | - |
| `LIVEKIT_API_SECRET` | LiveKit API secret | - |
| `VOICE_AGENT_BACKEND` | Voice runtime backend | `glm-qwen` |
| `VOICE_AGENT_LLM_MODEL` | Chat model used for reasoning | `glm-5` |
| `VOICE_AGENT_LLM_BASE_URL` | OpenAI-compatible chat completions base URL | `https://api.z.ai/api/paas/v4` |
| `VOICE_AGENT_LLM_API_KEY` | API key for the configured chat model backend | - |
| `CODETETHER_VOICE_API_URL` | Local Qwen voice API base URL | `http://127.0.0.1:8000` |
| `VOICE_AGENT_DEFAULT_VOICE_ID` | Default Qwen voice profile ID | `960f89fc` |

## Usage

### Web UI Integration

The voice agent integrates with the CodeTether dashboard:

```tsx
import { VoiceAssistantUI } from '@/components/voice/VoiceAssistantUI';

<VoiceAssistantUI sessionId={session.id} />
```

### Swift iOS/macOS App

```swift
import A2AMonitor

let voiceManager = VoiceSessionManager()
await voiceManager.connect(sessionId: "session-123")
```

## Supported Runtime

- GLM-5 over an OpenAI-compatible chat-completions endpoint
- Local Qwen `/transcribe` for STT
- Local Qwen `/voices/{voice_id}/speak` for TTS

## Session Playback

Review past voice conversations:

```bash
GET /v1/voice/sessions/{id}/playback
```

Returns:
- Audio recordings
- Transcript
- Agent responses
- Timestamps

## Architecture

```
Client (Web/Mobile)
    ↓ (WebSocket)
LiveKit Server
    ↓
Voice Agent (Python)
    ↓ (Qwen STT/TTS + MCP)
A2A Server → GLM-5
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/voice/sessions` | POST | Create voice session |
| `/v1/voice/sessions/{id}` | GET | Get session details |
| `/v1/voice/sessions/{id}/playback` | GET | Get playback data |
| `/v1/voice/models` | GET | List available models |

## Fine-Tuning

The voice agent includes fine-tuning capabilities:

```bash
cd codetether_voice_agent/finetuning
pip install -r requirements.txt
python finetune.py --data training_examples.jsonl
```

See [finetuning/README.md](https://github.com/rileyseaburg/codetether/tree/main/codetether_voice_agent/finetuning) for details.

## Troubleshooting

### Audio not playing?

Check LiveKit connectivity:
```bash
curl https://livekit.codetether.run/health
```

### No voice response?

Verify model credentials:
```bash
cat ~/.local/share/agent/auth.json
```

### Session sync issues?

Restart the voice agent:
```bash
kubectl rollout restart deployment/codetether-voice-agent
```

## See Also

- [Session Management](sessions.md)
- [Real-time Streaming](streaming.md)
- [CodeTether Integration](agent.md)
