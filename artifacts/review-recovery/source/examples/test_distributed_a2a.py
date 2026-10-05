"""
Test script for distributed A2A servers.

This script sends test messages to distributed A2A servers to demonstrate
agent-to-agent communication across multiple servers.

Usage:
  1. Start servers in separate terminals:
     Terminal 1: python examples/distributed_a2a_server.py --port 5001 --name "Server-A"
     Terminal 2: python examples/distributed_a2a_server.py --port 5002 --name "Server-B" --connect http://localhost:5001
     Terminal 3: python examples/distributed_a2a_server.py --port 5003 --name "Server-C" --connect http://localhost:5001,http://localhost:5002

  2. Run this test script:
     python examples/test_distributed_a2a.py
"""

import asyncio
import httpx
import logging
import json
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DistributedA2ATester:
    """Test client for distributed A2A servers."""

    def __init__(self, servers: Dict[str, str]):
        """
        Args:
            servers: Dict mapping server names to URLs, e.g., {"Server-A": "http://localhost:5001"}
        """
        self.servers = servers
        self.client = httpx.AsyncClient(timeout=30.0)

    async def send_message(self, server_url: str, message: str) -> Dict[str, Any]:
        """Send a JSON-RPC message to a server."""
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "message/send",
            "params": {
                "message": {
                    "parts": [{"type": "text", "content": message}]
                }
            }
        }

        try:
            response = await self.client.post(server_url, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error sending to {server_url}: {e}")
            return {"error": str(e)}

    async def get_agent_card(self, server_url: str) -> Dict[str, Any]:
        """Get the agent card from a server."""
        try:
            response = await self.client.get(f"{server_url}/.well-known/agent-card.json")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting agent card from {server_url}: {e}")
            return {"error": str(e)}

    async def test_discovery(self):
        """Test agent discovery across servers."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 1: Agent Discovery")
        logger.info("=" * 70)

        for name, url in self.servers.items():
            logger.info(f"\nDiscovering agents on {name} ({url})...")
            card = await self.get_agent_card(url)

            if "error" in card:
                logger.error(f"  ❌ Could not connect to {name}")
                continue

            logger.info(f"  ✓ Server: {card.get('name')}")
            logger.info(f"  ✓ Description: {card.get('description')}")

            skills = card.get('skills', [])
            logger.info(f"  ✓ Agents/Skills: {len(skills)}")
            for skill in skills[:3]:  # Show first 3
                logger.info(f"    - {skill.get('name')}")

    async def test_simple_messaging(self):
        """Test simple message sending."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 2: Simple Messaging")
        logger.info("=" * 70)

        for name, url in self.servers.items():
            logger.info(f"\nSending test message to {name}...")
            result = await self.send_message(url, f"Hello from test client to {name}")

            if "error" in result:
                logger.error(f"  ❌ Error: {result['error']}")
                continue

            if "result" in result and "message" in result["result"]:
                response_text = result["result"]["message"]["parts"][0]["content"]
                logger.info(f"  ✓ Response: {response_text[:100]}")

    async def test_distributed_coordination(self):
        """Test distributed coordination."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 3: Distributed Coordination")
        logger.info("=" * 70)

        # Send coordination request to first server
        first_server_url = list(self.servers.values())[0]
        first_server_name = list(self.servers.keys())[0]

        logger.info(f"\nSending coordination request to {first_server_name}...")
        result = await self.send_message(
            first_server_url,
            "coordinate distributed task: Process analytics pipeline"
        )

        if "error" in result:
            logger.error(f"  ❌ Error: {result['error']}")
            return

        if "result" in result and "message" in result["result"]:
            response_text = result["result"]["message"]["parts"][0]["content"]
            logger.info(f"  ✓ Coordination response:\n{response_text}")

        # Give time for distributed processing
        logger.info("\n⏳ Waiting for distributed processing...")
        await asyncio.sleep(2)

    async def test_status_check(self):
        """Check status/monitor reports."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 4: Status/Monitor Reports")
        logger.info("=" * 70)

        for name, url in self.servers.items():
            logger.info(f"\nRequesting status report from {name}...")
            result = await self.send_message(url, "status report")

            if "error" in result:
                logger.error(f"  ❌ Error: {result['error']}")
                continue

            if "result" in result and "message" in result["result"]:
                response_text = result["result"]["message"]["parts"][0]["content"]
                logger.info(f"  ✓ Report:\n{response_text}")

    async def test_multi_hop_coordination(self):
        """Test coordination that hops across multiple servers."""
        logger.info("\n" + "=" * 70)
        logger.info("TEST 5: Multi-Hop Coordination")
        logger.info("=" * 70)

        if len(self.servers) < 2:
            logger.warning("Need at least 2 servers for multi-hop test")
            return

        # Send to each server in sequence
        for i, (name, url) in enumerate(self.servers.items()):
            logger.info(f"\n[Hop {i+1}] Sending task to {name}...")
            result = await self.send_message(
                url,
                f"coordinate task hop {i+1}: Multi-server pipeline step {i+1}"
            )

            if "result" in result and "message" in result["result"]:
                response_text = result["result"]["message"]["parts"][0]["content"]
                logger.info(f"  ✓ Response: {response_text[:150]}")

            await asyncio.sleep(1)

    async def run_all_tests(self):
        """Run all distributed A2A tests."""
        logger.info("\n" + "=" * 70)
        logger.info("🧪 DISTRIBUTED A2A TEST SUITE")
        logger.info("=" * 70)

        await self.test_discovery()
        await self.test_simple_messaging()
        await self.test_distributed_coordination()
        await self.test_status_check()
        await self.test_multi_hop_coordination()

        logger.info("\n" + "=" * 70)
        logger.info("✅ All tests completed!")
        logger.info("=" * 70)

    async def close(self):
        """Cleanup."""
        await self.client.aclose()


async def main():
    """Run distributed A2A tests."""

    # Define servers to test (add/remove as needed)
    servers = {
        "Server-A": "http://localhost:5001",
        "Server-B": "http://localhost:5002",
        "Server-C": "http://localhost:5003",
    }

    tester = DistributedA2ATester(servers)

    try:
        await tester.run_all_tests()
    finally:
        await tester.close()


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║           Distributed A2A Server Test Suite                          ║
╚══════════════════════════════════════════════════════════════════════╝

Before running this test, make sure you have started the distributed
A2A servers in separate terminals:

Terminal 1:
  python examples/distributed_a2a_server.py --port 5001 --name "Server-A"

Terminal 2:
  python examples/distributed_a2a_server.py --port 5002 --name "Server-B" --connect http://localhost:5001

Terminal 3:
  python examples/distributed_a2a_server.py --port 5003 --name "Server-C" --connect http://localhost:5001,http://localhost:5002

Press Ctrl+C to cancel, or Enter to continue...
    """)

    try:
        input()
    except KeyboardInterrupt:
        print("\nTest cancelled.")
        exit(0)

    asyncio.run(main())
