# Voice Agent

The CodeTether Voice Agent enables real-time voice interactions with AI agents through LiveKit integration.

## Overview

The voice agent provides:
- **Real-time voice streaming** via LiveKit
- **Session playback** for reviewing conversations
- **Multi-model support** (Claude, GPT-4, Gemini, Grok)
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
| `VOICE_MODEL` | Default AI voice model | `claude-opus` |

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

## Supported Voice Models

- Claude (Opus, Sonnet, Haiku)
- GPT-4, GPT-4 Turbo
- Gemini Pro, Gemini Flash
- Grok 3

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
    ↓ (MCP)
A2A Server → Agent LLM
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
