# Distributed Agent-to-Agent Communication Guide

This guide shows you how to run **true distributed A2A** where agents on different servers (in different terminals) communicate as peers over the network.

## 🎯 What You'll See

- **Agent Discovery**: Agents on different servers discovering each other
- **Distributed Coordination**: Coordinator agent on one server orchestrating work across multiple servers
- **Event Federation**: Events published by agents propagating across servers
- **Cross-Server Messaging**: Agents directly communicating with agents on remote servers

## 🚀 Quick Start

### Step 1: Start Server A (Terminal 1)

```bash
cd c:/Users/riley/programming/A2A-Server-MCP
python examples/distributed_a2a_server.py --port 5001 --name "Server-A"
```

This starts the first A2A server with:
- Coordinator agent (orchestrates tasks)
- 2 Worker agents (process tasks)
- Monitor agent (tracks all activity)

### Step 2: Start Server B (Terminal 2)

```bash
cd c:/Users/riley/programming/A2A-Server-MCP
python examples/distributed_a2a_server.py --port 5002 --name "Server-B" --connect http://localhost:5001
```

This starts a second server that:
- Discovers agents on Server-A
- Connects as a peer
- Has its own set of agents

### Step 3: Start Server C (Terminal 3)

```bash
cd c:/Users/riley/programming/A2A-Server-MCP
python examples/distributed_a2a_server.py --port 5003 --name "Server-C" --connect http://localhost:5001,http://localhost:5002
```

This starts a third server that:
- Discovers agents on both Server-A and Server-B
- Forms a network of 3 peer servers

### Step 4: Run Tests (Terminal 4)

```bash
cd c:/Users/riley/programming/A2A-Server-MCP
python examples/test_distributed_a2a.py
```

This runs automated tests showing:
- Agent discovery across all servers
- Simple messaging to each server
- Distributed coordination (Server-A coordinates work across B and C)
- Status reports from each server
- Multi-hop coordination patterns

## 📡 What's Happening Behind the Scenes

### Agent Discovery
```
Server-A (port 5001)
  ↓ fetch agent card
Server-B (port 5002) discovers:
  - Coordinator-Server-A
  - Worker-A-Server-A
  - Worker-B-Server-A
  - Monitor-Server-A
```

### Distributed Coordination Example
```
1. Client sends "coordinate task" to Server-A
2. Coordinator-Server-A broadcasts to peers (Server-B, Server-C)
3. Workers on Server-B process task
4. Workers on Server-C process task
5. All publish task.completed events
6. Monitors on all servers log the events
7. Coordinator reports back to client
```

### Event Flow
```
[Server-A] Coordinator publishes "coordination.started"
    ↓
[Server-A] Monitor logs event
    ↓
[Server-A] Coordinator sends tasks to Server-B and Server-C
    ↓
[Server-B] Worker-A processes task, publishes "task.completed"
    ↓
[Server-B] Monitor logs event
    ↓
[Server-C] Worker-A processes task, publishes "task.completed"
    ↓
[Server-C] Monitor logs event
    ↓
[Server-A] Coordinator publishes "coordination.complete"
```

## 🔧 Manual Testing

You can also send messages manually using curl:

### Send a Simple Message
```bash
curl -X POST http://localhost:5001/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "parts": [{"type": "text", "content": "Hello Server-A"}]
      }
    }
  }'
```

### Trigger Distributed Coordination
```bash
curl -X POST http://localhost:5001/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "parts": [{"type": "text", "content": "coordinate distributed analytics task"}]
      }
    }
  }'
```

### Get Status Report
```bash
curl -X POST http://localhost:5002/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "parts": [{"type": "text", "content": "status report"}]
      }
    }
  }'
```

## 🎭 Agent Types

### Coordinator Agent
- Orchestrates distributed tasks
- Broadcasts work to peer servers
- Publishes coordination events

### Worker Agent
- Processes assigned tasks
- Has a specialty (data-processing, analytics, etc.)
- Reports completion back
- **OpenCode Integration**: Can register local codebases and a "Global Codebase" for direct chat.

### Monitor Agent
- Tracks all events across the system
- Provides status reports
- Logs coordination activity

## 🌐 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Distributed A2A Network                   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌───────────────┐      ┌───────────────┐      ┌──────────┐ │
│  │  Server-A     │◄────►│  Server-B     │◄────►│ Server-C │ │
│  │  Port 5001    │      │  Port 5002    │      │ Port 5003│ │
│  │               │      │               │      │          │ │
│  │ • Coordinator │      │ • Coordinator │      │• Monitor │ │
│  │ • Worker-A    │      │ • Worker-A    │      │• Worker-A│ │
│  │ • Worker-B    │      │ • Worker-B    │      │• Worker-B│ │
│  │ • Monitor     │      │ • Monitor     │      │          │ │
│  └───────────────┘      └───────────────┘      └──────────┘ │
│         ▲                      ▲                     ▲       │
│         │                      │                     │       │
│         └──────────────────────┴─────────────────────┘       │
│                         Message Broker                       │
│                    (Events & Direct Messages)                │
└─────────────────────────────────────────────────────────────┘
```

### Agent Workers & OpenCode

Distributed workers can now register their local OpenCode capabilities:

1. **Worker Registration**: Workers send their `worker_id`, `name`, `capabilities`, and `models` to the server.
2. **Global Codebase**: Workers automatically register a `global_codebase_id` pointing to `~` to enable Direct Chat.
3. **Model Discovery**: Available models (e.g., Gemini 3 Flash) are reported via the `/v1/opencode/workers/register` endpoint.

## 🔑 Key Differences: Local vs Distributed A2A

| Feature | Local A2A (`agent_to_agent_messaging.py`) | Distributed A2A (`distributed_a2a_server.py`) |
|---------|-------------------------------------------|----------------------------------------------|
| **Location** | All agents in one process | Agents across multiple servers/processes |
| **Communication** | Shared in-memory message broker | HTTP + message broker per server |
| **Discovery** | Pre-registered | Dynamic discovery via agent cards |
| **Network** | No network involved | True network communication |
| **Use Case** | Single-machine coordination | Multi-machine, distributed systems |
| **Scaling** | Limited to one machine | Scales across multiple machines |

## 💡 Use Cases

1. **Distributed Data Processing**: Spread heavy processing across multiple machines
2. **Geographic Distribution**: Agents in different data centers coordinating work
3. **Fault Tolerance**: If one server goes down, others continue working
4. **Specialization**: Different servers host agents with different capabilities
5. **Load Balancing**: Distribute work based on server capacity

## 🎓 Learning Path

1. **Start Simple**: Run `agent_to_agent_messaging.py` to understand local A2A
2. **Go Distributed**: Run 2 distributed servers (Server-A + Server-B)
3. **Add Complexity**: Add Server-C and watch the network form
4. **Experiment**: Send custom messages, modify agent behavior
5. **Build Your Own**: Create custom distributed agents for your use case

## 🐛 Troubleshooting

**Q: Server won't start - port already in use**
```
A: Kill the process using that port or use a different port:
   python examples/distributed_a2a_server.py --port 5004 --name "Server-D"
```

**Q: Server can't discover peers**
```
A: Make sure peer servers are running first, then start new servers with --connect
```

**Q: No responses from coordination**
```
A: Check that all servers show "Connected peers" in their startup logs
   The --connect URLs must point to running servers
```

**Q: Want to see raw JSON-RPC**
```
A: Check server logs - all HTTP requests/responses are logged
   Add more logging: logging.basicConfig(level=logging.DEBUG)
```

## 🚀 Next Steps

- Modify agents to add custom behavior
- Connect to Claude API for LLM-powered distributed agents
- Add Redis for persistent message queues
- Deploy across multiple machines/cloud instances
- Build a web UI to visualize the agent network

---

**Ready to see it in action?** Open 4 terminals and follow the Quick Start above! 🎉
