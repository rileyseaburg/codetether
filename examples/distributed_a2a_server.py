"""
Distributed A2A Server Example

This example demonstrates true distributed agent-to-agent communication where:
1. Multiple A2A servers run in different terminals
2. Agents on different servers discover and communicate with each other
3. Events are federated across servers
4. Agents coordinate work across the network

Run multiple instances:
  Terminal 1: python examples/distributed_a2a_server.py --port 5001 --name "Server-A"
  Terminal 2: python examples/distributed_a2a_server.py --port 5002 --name "Server-B" --connect http://localhost:5001
  Terminal 3: python examples/distributed_a2a_server.py --port 5003 --name "Server-C" --connect http://localhost:5001,http://localhost:5002
"""

import asyncio
import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from a2a_server.enhanced_server import EnhancedA2AServer
from a2a_server.enhanced_agents import EnhancedAgent
from a2a_server.message_broker import InMemoryMessageBroker
from a2a_server.models import Message, Part, AgentProvider
from a2a_server.agent_card import AgentCard

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DistributedAgent(EnhancedAgent):
    """Agent that can communicate with agents on remote A2A servers."""

    def __init__(self, name: str, server_name: str, peer_servers: List[str] = None, message_broker=None):
        super().__init__(
            name=name,
            description=f"Distributed agent on {server_name}",
            message_broker=message_broker
        )
        self.server_name = server_name
        self.peer_servers = peer_servers or []
        self.peer_agents: Dict[str, Dict] = {}  # Map of server_url -> agent_card
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def initialize(self, message_broker=None):
        """Initialize and discover peer agents."""
        await super().initialize(message_broker)

        # Discover agents on peer servers
        for peer_url in self.peer_servers:
            try:
                response = await self.http_client.get(f"{peer_url}/.well-known/agent-card.json")
                response.raise_for_status()
                agent_card = response.json()
                self.peer_agents[peer_url] = agent_card
                logger.info(f"🔗 {self.name} discovered peer: {agent_card.get('name')} at {peer_url}")
            except Exception as e:
                logger.warning(f"Could not discover peer at {peer_url}: {e}")

    async def send_to_peer(self, peer_url: str, message: Message) -> Optional[Message]:
        """Send a message to an agent on a peer A2A server."""
        try:
            request_data = {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "message/send",
                "params": {
                    "message": {
                        "parts": [{"type": part.type, "content": part.content} for part in message.parts]
                    }
                }
            }

            logger.info(f"📤 {self.name} sending to peer at {peer_url}")

            response = await self.http_client.post(peer_url, json=request_data)
            response.raise_for_status()
            result = response.json()

            if "result" in result and "message" in result["result"]:
                remote_message = result["result"]["message"]
                parts = remote_message.get("parts", [])
                return Message(parts=[Part(type=p["type"], content=p["content"]) for p in parts])

            return None

        except Exception as e:
            logger.error(f"Error sending to peer {peer_url}: {e}")
            return None

    async def broadcast_to_peers(self, message: Message):
        """Broadcast a message to all peer servers."""
        tasks = [self.send_to_peer(peer_url, message) for peer_url in self.peer_servers]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        valid_responses = [r for r in responses if isinstance(r, Message)]
        logger.info(f"📡 {self.name} broadcast to {len(self.peer_servers)} peers, got {len(valid_responses)} responses")

        return valid_responses

    async def process_message(self, message: Message) -> Message:
        """Process messages and coordinate with peer agents."""
        text = self._extract_text_content(message)

        # Publish local event about receiving message
        await self.publish_event("message.received", {
            "from": self.name,
            "server": self.server_name,
            "content": text[:100]
        })

        return Message(parts=[Part(
            type="text",
            content=f"[{self.server_name}] {self.name} processed: {text}"
        )])

    async def close(self):
        """Cleanup."""
        await self.http_client.aclose()


class CoordinatorAgent(DistributedAgent):
    """Coordinator that orchestrates work across multiple servers."""

    async def process_message(self, message: Message) -> Message:
        text = self._extract_text_content(message)

        if "coordinate" in text.lower():
            logger.info(f"🎯 {self.name} coordinating distributed task")

            # Publish coordination event locally
            await self.publish_event("coordination.started", {
                "task": text,
                "peer_count": len(self.peer_servers)
            })

            # Broadcast to all peers
            task_msg = Message(parts=[Part(
                type="text",
                content=f"Task from {self.server_name}: {text}"
            )])

            responses = await self.broadcast_to_peers(task_msg)

            # Publish coordination complete event
            await self.publish_event("coordination.complete", {
                "task": text,
                "responses_received": len(responses)
            })

            result = f"[{self.server_name}] Coordinated task across {len(self.peer_servers)} servers, received {len(responses)} responses"
            return Message(parts=[Part(type="text", content=result)])

        return await super().process_message(message)


class WorkerAgent(DistributedAgent):
    """Worker that processes tasks and reports back."""

    def __init__(self, name: str, server_name: str, specialty: str, peer_servers: List[str] = None, message_broker=None):
        super().__init__(name, server_name, peer_servers, message_broker)
        self.specialty = specialty
        self.tasks_completed = 0

    async def process_message(self, message: Message) -> Message:
        text = self._extract_text_content(message)

        if "task from" in text.lower():
            self.tasks_completed += 1
            logger.info(f"⚙️  {self.name} processing task #{self.tasks_completed}")

            # Publish task completion event
            await self.publish_event("task.completed", {
                "worker": self.name,
                "server": self.server_name,
                "specialty": self.specialty,
                "task_number": self.tasks_completed,
                "task": text[:50]
            })

            result = f"[{self.server_name}] {self.name} ({self.specialty}) completed task #{self.tasks_completed}"
            return Message(parts=[Part(type="text", content=result)])

        return await super().process_message(message)


class MonitorAgent(DistributedAgent):
    """Monitor that tracks activity across all servers."""

    def __init__(self, name: str, server_name: str, peer_servers: List[str] = None, message_broker=None):
        super().__init__(name, server_name, peer_servers, message_broker)
        self.event_log = []

    async def initialize(self, message_broker=None):
        await super().initialize(message_broker)

        # Subscribe to coordination and task events
        # Note: InMemoryMessageBroker doesn't support wildcard patterns,
        # so we subscribe to specific event types
        if self.message_broker:
            # Subscribe to coordination events
            await self.message_broker.subscribe_to_events(
                "coordination.started",
                self.log_event
            )
            await self.message_broker.subscribe_to_events(
                "coordination.complete",
                self.log_event
            )
            # Subscribe to task events
            await self.message_broker.subscribe_to_events(
                "task.completed",
                self.log_event
            )
            # Subscribe to message events
            await self.message_broker.subscribe_to_events(
                "message.received",
                self.log_event
            )

    async def log_event(self, event_type: str, data: Dict[str, Any]):
        """Log events from across the system."""
        event_entry = {
            'event_type': event_type,
            'data': data,
            'timestamp': datetime.now().isoformat()
        }
        self.event_log.append(event_entry)

        # Extract agent name from data if available
        agent = data.get('agent', data.get('worker', 'unknown'))
        logger.info(f"📊 Monitor logged: {agent} -> {event_type}")

    async def process_message(self, message: Message) -> Message:
        text = self._extract_text_content(message)

        if "status" in text.lower() or "report" in text.lower():
            report = f"[{self.server_name}] Monitor Report:\n"
            report += f"  Events logged: {len(self.event_log)}\n"
            report += f"  Connected peers: {len(self.peer_servers)}\n"

            # Count event types
            event_types = {}
            for event in self.event_log:
                et = event.get('event_type', 'unknown')
                event_types[et] = event_types.get(et, 0) + 1

            report += f"  Event breakdown:\n"
            for et, count in event_types.items():
                report += f"    - {et}: {count}\n"

            return Message(parts=[Part(type="text", content=report)])

        return await super().process_message(message)


async def run_distributed_server(
    port: int,
    name: str,
    peer_urls: List[str] = None,
    agent_type: str = "mixed"
):
    """Run a distributed A2A server with specialized agents."""
    peer_urls = peer_urls or []

    logger.info("=" * 70)
    logger.info(f"Starting Distributed A2A Server: {name}")
    logger.info(f"Port: {port}")
    logger.info(f"Peers: {len(peer_urls)}")
    logger.info("=" * 70)

    # Create message broker
    broker = InMemoryMessageBroker()
    await broker.start()

    # Create agents based on server type
    agents = []

    if agent_type in ["mixed", "coordinator"]:
        coordinator = CoordinatorAgent(
            name=f"Coordinator-{name}",
            server_name=name,
            peer_servers=peer_urls,
            message_broker=broker
        )
        await coordinator.initialize(broker)
        agents.append(coordinator)
        logger.info(f"✓ Created Coordinator agent on {name}")

    if agent_type in ["mixed", "worker"]:
        worker1 = WorkerAgent(
            name=f"Worker-A-{name}",
            server_name=name,
            specialty="data-processing",
            peer_servers=peer_urls,
            message_broker=broker
        )
        await worker1.initialize(broker)
        agents.append(worker1)

        worker2 = WorkerAgent(
            name=f"Worker-B-{name}",
            server_name=name,
            specialty="analytics",
            peer_servers=peer_urls,
            message_broker=broker
        )
        await worker2.initialize(broker)
        agents.append(worker2)
        logger.info(f"✓ Created 2 Worker agents on {name}")

    if agent_type in ["mixed", "monitor"]:
        monitor = MonitorAgent(
            name=f"Monitor-{name}",
            server_name=name,
            peer_servers=peer_urls,
            message_broker=broker
        )
        await monitor.initialize(broker)
        agents.append(monitor)
        logger.info(f"✓ Created Monitor agent on {name}")

    # Create agent card for the server
    provider = AgentProvider(
        organization="Distributed A2A Network",
        url="https://github.com/rileyseaburg/A2A-Server-MCP"
    )

    agent_card = AgentCard(
        name=name,
        description=f"Distributed A2A server with {len(agents)} agents",
        url=f"http://localhost:{port}",
        provider=provider
    )

    # Add skills for each agent
    for agent in agents:
        agent_card.add_skill(
            skill_id=agent.name.lower().replace(" ", "_").replace("-", "_"),
            name=agent.name,
            description=agent.description,
            input_modes=["text"],
            output_modes=["text"]
        )

    # Create and start the A2A server
    server = EnhancedA2AServer(
        agent_card=agent_card,
        message_broker=broker,
        use_redis=False
    )

    # Register our custom agents with the server (if there's an agents dict)
    if hasattr(server, 'agents'):
        for agent in agents:
            server.agents[agent.name] = agent

    logger.info(f"🚀 Starting {name} on port {port}")
    logger.info(f"   Agent card: http://localhost:{port}/.well-known/agent-card.json")
    logger.info(f"   Agents: {', '.join([a.name for a in agents])}")

    # Start server
    try:
        await server.start(host="0.0.0.0", port=port)
    except KeyboardInterrupt:
        logger.info(f"\n⏹️  Stopping {name}")
    finally:
        # Cleanup
        for agent in agents:
            await agent.close()
        await broker.stop()
        logger.info(f"✓ {name} stopped cleanly")


def main():
    parser = argparse.ArgumentParser(
        description="Run a distributed A2A server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start first server
  python examples/distributed_a2a_server.py --port 5001 --name "Server-A"

  # Start second server connected to first
  python examples/distributed_a2a_server.py --port 5002 --name "Server-B" --connect http://localhost:5001

  # Start third server connected to both
  python examples/distributed_a2a_server.py --port 5003 --name "Server-C" --connect http://localhost:5001,http://localhost:5002

  # Test coordination (in another terminal)
  curl -X POST http://localhost:5001/ -H "Content-Type: application/json" -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "parts": [{"type": "text", "content": "coordinate distributed task"}]
      }
    }
  }'
        """
    )

    parser.add_argument("--port", type=int, required=True, help="Port to run server on")
    parser.add_argument("--name", type=str, required=True, help="Name of this server")
    parser.add_argument(
        "--connect",
        type=str,
        help="Comma-separated list of peer server URLs (e.g., http://localhost:5001,http://localhost:5002)"
    )
    parser.add_argument(
        "--type",
        choices=["mixed", "coordinator", "worker", "monitor"],
        default="mixed",
        help="Type of agents to run on this server"
    )

    args = parser.parse_args()

    # Parse peer URLs
    peer_urls = []
    if args.connect:
        peer_urls = [url.strip() for url in args.connect.split(",")]

    # Run the server
    asyncio.run(run_distributed_server(
        port=args.port,
        name=args.name,
        peer_urls=peer_urls,
        agent_type=args.type
    ))


if __name__ == "__main__":
    main()
