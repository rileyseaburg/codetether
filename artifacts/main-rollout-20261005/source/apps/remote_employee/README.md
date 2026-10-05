# Remote Employee MVP

Remote Employee is a small company control plane backed by the locally installed
CodeTether agent. Every employee gets a persistent `codetether mux`, a procedural
3D avatar, task history, a private LiveKit room, and presence in one shared office
room. The CEO can publish real camera and microphone tracks into either room.

## What works

- Hiring creates a real, detached CodeTether mux rooted in an existing workspace.
- Assigning work sends a safely quoted `codetether run` turn into mux window `0`.
- Mux output is polled by byte offset and shown in the employee inspector.
- A random completion sentinel separates a task from the persistent mux shell.
- Employee state animates a procedural Three.js avatar in a navigable office.
- The CEO can publish camera/audio and subscribe to participants through LiveKit.
- Employees can submit hire, delegation, and meeting proposals; CEO approval is
  required before a proposal provisions another mux or starts delegated work.
- SQLite persists employees, work, and proposals across server restarts.

## Run against the existing Kubernetes LiveKit service

From the repository root:

```bash
python apps/remote_employee/run.py
```

Open <http://127.0.0.1:8090>. The bootstrap reads the `livekit-server` ConfigMap
from namespace `quantum-forge`, keeps its credentials only in process memory, and
connects browsers to `wss://live.quantum-forge.net`.

To expose the control plane beyond loopback, HTTPS and a CEO token are mandatory:

```bash
export REMOTE_EMPLOYEE_ADMIN_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python apps/remote_employee/run.py --host 0.0.0.0
```

The UI stores that token only in `sessionStorage`. Never put a LiveKit API secret,
mux registry token, or CEO token into browser code.

You can also supply `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, and
`LIVEKIT_PUBLIC_URL` yourself and use `--no-cluster-config`.

## Architecture

```text
Browser (Three.js + LiveKit JS)
        │ same-origin REST / short-lived room JWT
FastAPI control plane ─── SQLite
        │ owner-private loopback protocol
CodeTether mux per employee ─── codetether run
        │
        └──────────────── LiveKit cluster (media only)
```

LiveKit is not used as durable company state. The browser never receives mux
addresses/tokens or LiveKit API credentials. Room JWTs are scoped to one room,
permit publish/subscribe without room administration, and expire after 30 minutes.

## API summary

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/company` | Employees, tasks, proposals, live mux output |
| `POST` | `/api/employees` | Hire and create a mux |
| `POST` | `/api/employees/{id}/tasks` | Start a CodeTether turn in the mux |
| `POST` | `/api/office-token` | Join the shared LiveKit office |
| `POST` | `/api/employees/{id}/meeting-token` | Join a private room |
| `POST` | `/api/proposals` | Propose a hire, delegation, or meeting |
| `POST` | `/api/proposals/{id}/decision` | CEO approval/rejection |

## MVP boundaries

- Avatars are procedural low-poly characters, not photorealistic generated video.
- The CEO media path is real. An employee publishes media only when a voice/avatar
  worker joins with identity `employee:{employee_id}`; wiring a per-mux TTS worker
  is the next production slice.
- Raw mux output is visible to the local CEO. Before multi-tenant use it needs
  redaction, tenant isolation, per-employee budgets, and an audit log.
- Workspaces are CEO-provided existing local paths. Production should select from
  a server-side allowlist instead of accepting filesystem paths.