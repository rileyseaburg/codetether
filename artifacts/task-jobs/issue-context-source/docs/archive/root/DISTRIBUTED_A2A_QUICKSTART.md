# Distributed A2A Quick Start

Run these commands in **3 separate terminals** to see true agent-to-agent communication across different servers:

## Terminal 1: Start Server-A
```bash
cd c:/Users/riley/programming/A2A-Server-MCP
python examples/distributed_a2a_server.py --port 5001 --name "Server-A"
```

**What you'll see:**
- ✓ Coordinator agent created
- ✓ 2 Worker agents created
- ✓ Monitor agent created
- Server running on port 5001

## Terminal 2: Start Server-B (Connected to A)
```bash
cd c:/Users/riley/programming/A2A-Server-MCP
python examples/distributed_a2a_server.py --port 5002 --name "Server-B" --connect http://localhost:5001
```

**What you'll see:**
- 🔗 Server-B discovers agents on Server-A
- Creates its own agents
- Forms peer connection with Server-A

## Terminal 3: Start Server-C (Connected to A and B)
```bash
cd c:/Users/riley/programming/A2A-Server-MCP
python examples/distributed_a2a_server.py --port 5003 --name "Server-C" --connect http://localhost:5001,http://localhost:5002
```

**What you'll see:**
- 🔗 Server-C discovers agents on both Server-A and Server-B
- Creates its own agents
- Forms peer connections with A and B
- Now you have a 3-node distributed agent network!

## Test It! (Terminal 4)

Once all 3 servers are running, test the distributed coordination:

### Option 1: Simple message to Server-A
```bash
curl -X POST http://localhost:5001/ -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "message/send",
  "params": {
    "message": {
      "parts": [{"type": "text", "content": "Hello Server-A!"}]
    }
  }
}'
```

### Option 2: Trigger distributed coordination
```bash
curl -X POST http://localhost:5001/ -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "message/send",
  "params": {
    "message": {
      "parts": [{"type": "text", "content": "coordinate distributed analytics pipeline"}]
    }
  }
}'
```

**Watch the terminals!** You'll see:
1. Server-A Coordinator receives the request
2. Broadcasts task to Server-B and Server-C
3. Workers on B and C process the tasks
4. Monitors log all the activity
5. Coordinator reports back the results

### Option 3: Run automated test suite
```bash
cd c:/Users/riley/programming/A2A-Server-MCP
python examples/test_distributed_a2a.py
```

This runs 5 comprehensive tests showing:
- Agent discovery across all servers
- Simple messaging
- Distributed coordination
- Status reports
- Multi-hop coordination

## What Makes This "True A2A"?

✅ **Multiple servers** - Each running in its own process
✅ **Agent discovery** - Agents find each other via agent cards
✅ **Peer communication** - Servers talk as equals, not client/server
✅ **Event federation** - Events published on one server visible to others
✅ **Distributed coordination** - Agents orchestrate work across the network

## Compare to Local A2A

**Local A2A** (`agent_to_agent_messaging.py`):
- All agents in one process
- Shared in-memory message broker
- No network involved

**Distributed A2A** (`distributed_a2a_server.py`):
- Agents in separate processes/terminals
- HTTP communication between servers
- Each server has its own message broker
- True network distribution

## Next Steps

- Try starting 4+ servers to build a larger network
- Add custom agent types
- Integrate with Claude LLM for intelligent routing
- Deploy across multiple machines

---

**Ready?** Open 3 terminals and follow the commands above! 🚀
