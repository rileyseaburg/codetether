"""
Example demonstrating connection to a remote A2A agent on localhost:4400.

This example shows how to:
1. Connect to a remote A2A agent via HTTP
2. Send messages to the remote agent
3. Receive and process responses
4. Coordinate between local and remote agents
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict

# Add parent directory to path so we can import a2a_server
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from a2a_server.enhanced_agents import EnhancedAgent, initialize_agent_registry, ENHANCED_AGENTS
from a2a_server.message_broker import InMemoryMessageBroker
from a2a_server.models import Message, Part

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RemoteAgentClient(EnhancedAgent):
    """Agent that can communicate with a remote A2A server."""

    def __init__(self, remote_url: str, message_broker=None):
        super().__init__(
            name="Remote Agent Client",
            description="Connects to and communicates with remote A2A agent",
            message_broker=message_broker
        )
        self.remote_url = remote_url.rstrip('/')
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.agent_card = None

    async def initialize(self, message_broker=None):
        """Initialize and fetch remote agent card."""
        await super().initialize(message_broker)

        # Fetch agent card from remote server
        try:
            response = await self.http_client.get(f"{self.remote_url}/.well-known/agent-card.json")
            response.raise_for_status()
            self.agent_card = response.json()
            logger.info(f"✓ Connected to remote agent: {self.agent_card.get('name', 'Unknown')}")
            logger.info(f"  Description: {self.agent_card.get('description', 'N/A')}")
            logger.info(f"  Skills: {len(self.agent_card.get('skills', []))} available")
        except Exception as e:
            logger.error(f"✗ Failed to connect to remote agent at {self.remote_url}: {e}")
            raise

    async def send_to_remote(self, message: Message, method: str = "message/send") -> Dict[str, Any]:
        """Send a message to the remote A2A agent using JSON-RPC 2.0."""
        try:
            # Prepare JSON-RPC request
            request_data = {
                "jsonrpc": "2.0",
                "id": "1",
                "method": method,
                "params": {
                    "message": {
                        "parts": [{"type": part.type, "content": part.content} for part in message.parts]
                    }
                }
            }

            logger.info(f"→ Sending to remote agent: {message.parts[0].content if message.parts else 'empty'}")

            # Send to remote agent root endpoint (JSON-RPC 2.0)
            response = await self.http_client.post(
                self.remote_url,  # Always use root endpoint for JSON-RPC
                json=request_data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()

            result = response.json()
            logger.info(f"← Received from remote agent")

            return result

        except Exception as e:
            logger.error(f"Error sending to remote agent: {e}")
            raise

    async def process_message(self, message: Message) -> Message:
        """Process message by forwarding to remote agent."""
        try:
            result = await self.send_to_remote(message)

            # Extract response message
            if "result" in result and "message" in result["result"]:
                remote_message = result["result"]["message"]
                parts = remote_message.get("parts", [])

                response_parts = [
                    Part(type=p["type"], content=p["content"])
                    for p in parts
                ]

                return Message(parts=response_parts)

            return Message(parts=[Part(type="text", content="No response from remote agent")])

        except Exception as e:
            return Message(parts=[Part(type="text", content=f"Error: {str(e)}")])

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()


class BridgeAgent(EnhancedAgent):
    """Agent that bridges between local and remote agents."""

    def __init__(self, remote_client: RemoteAgentClient, message_broker=None):
        super().__init__(
            name="Bridge Agent",
            description="Bridges local and remote agent communication",
            message_broker=message_broker
        )
        self.remote_client = remote_client

    async def process_message(self, message: Message) -> Message:
        """Process message and coordinate between local and remote agents."""
        text = self._extract_text_content(message)

        if "remote" in text.lower():
            # Send to remote agent
            logger.info(f"Bridge: Forwarding to remote agent")
            response = await self.remote_client.process_message(message)

            # Publish event about remote interaction
            await self.publish_event("remote.interaction", {
                "request": text,
                "response": self._extract_text_content(response),
                "remote_url": self.remote_client.remote_url
            })

            return response

        elif "calculate" in text.lower():
            # Send to local calculator agent
            logger.info(f"Bridge: Forwarding to local Calculator agent")
            calc_msg = Message(parts=[Part(type="text", content=text)])
            await self.send_message_to_agent("Calculator Agent", calc_msg)

            return Message(parts=[Part(
                type="text",
                content="Request sent to local Calculator agent"
            )])

        else:
            return Message(parts=[Part(
                type="text",
                content=f"Bridge received: {text}. Use 'remote' or 'calculate' keywords to route."
            )])


async def demo_remote_agent_connection(remote_url: str = "http://localhost:4400"):
    """Demonstrate connection to remote A2A agent."""
    logger.info("=" * 60)
    logger.info(f"Connecting to Remote A2A Agent (LLM) at {remote_url}")
    logger.info("=" * 60)

    # Create message broker
    broker = InMemoryMessageBroker()
    await broker.start()
    logger.info("✓ Message broker started")

    # Initialize local agents
    initialize_agent_registry(broker)
    logger.info("✓ Local agent registry initialized")

    # Create remote agent client
    remote_client = RemoteAgentClient(remote_url, message_broker=broker)

    try:
        await remote_client.initialize(broker)

        logger.info("\n" + "=" * 60)
        logger.info("Demo 1: Ask LLM agent a question")
        logger.info("=" * 60)

        # Send a question to the LLM
        question = "What are the key benefits of agent-to-agent communication in multi-agent systems?"
        test_message = Message(parts=[Part(type="text", content=question)])
        logger.info(f"Question: {question}")
        response = await remote_client.process_message(test_message)
        logger.info(f"\nLLM Response:\n{response.parts[0].content if response.parts else 'No response'}\n")

        logger.info("\n" + "=" * 60)
        logger.info("Demo 2: Local Calculator + Remote LLM coordination")
        logger.info("=" * 60)

        # Get local calculator
        calculator = ENHANCED_AGENTS.get("calculator")
        if calculator:
            await calculator.initialize(broker)

            # Do a calculation locally
            calc_msg = Message(parts=[Part(type="text", content="Calculate 125 * 8 + 42")])
            calc_response = await calculator.process_message(calc_msg)
            logger.info(f"Local Calculator: {calc_response.parts[0].content if calc_response.parts else 'No response'}")

            # Ask LLM to explain the result
            explain_msg = Message(parts=[Part(
                type="text",
                content=f"The calculator returned: {calc_response.parts[0].content}. Can you explain this result in a creative way?"
            )])
            llm_response = await remote_client.process_message(explain_msg)
            logger.info(f"\nLLM Explanation:\n{llm_response.parts[0].content if llm_response.parts else 'No response'}\n")

        logger.info("\n" + "=" * 60)
        logger.info("Demo 3: Multi-step reasoning with LLM")
        logger.info("=" * 60)

        # Ask a multi-step question
        complex_question = "If I have 3 agents that can each process 50 messages per second, and I need to handle 200 messages per second with fault tolerance, how should I architect my system?"
        complex_msg = Message(parts=[Part(type="text", content=complex_question)])
        logger.info(f"Question: {complex_question}")
        complex_response = await remote_client.process_message(complex_msg)
        logger.info(f"\nLLM Response:\n{complex_response.parts[0].content if complex_response.parts else 'No response'}\n")

        logger.info("\n" + "=" * 60)
        logger.info("Demo 4: Local Memory + Remote LLM integration")
        logger.info("=" * 60)

        # Get local memory agent
        memory = ENHANCED_AGENTS.get("memory")
        if memory:
            await memory.initialize(broker)

            # Store some data
            store_msg = Message(parts=[Part(type="text", content="Store 'Agent-to-agent messaging enables sophisticated multi-agent coordination' as system_feature")])
            await memory.process_message(store_msg)
            logger.info("Stored data in local Memory agent")

            # Retrieve and ask LLM to elaborate
            retrieve_msg = Message(parts=[Part(type="text", content="Retrieve system_feature")])
            memory_response = await memory.process_message(retrieve_msg)
            logger.info(f"Memory agent: {memory_response.parts[0].content if memory_response.parts else 'No response'}")

            # Ask LLM to elaborate on the stored concept
            elaborate_msg = Message(parts=[Part(
                type="text",
                content=f"Based on this concept: '{memory_response.parts[0].content}', can you provide 3 specific examples of sophisticated coordination patterns?"
            )])
            elaborate_response = await remote_client.process_message(elaborate_msg)
            logger.info(f"\nLLM Elaboration:\n{elaborate_response.parts[0].content if elaborate_response.parts else 'No response'}\n")

        logger.info("\n" + "=" * 60)
        logger.info("Demo 5: Create intelligent workflow with LLM orchestration")
        logger.info("=" * 60)

        # Create an orchestrator that uses LLM for decision making
        class LLMOrchestrator(EnhancedAgent):
            def __init__(self, llm_client: RemoteAgentClient, message_broker=None):
                super().__init__(
                    name="LLM Orchestrator",
                    description="Uses LLM to make intelligent routing decisions",
                    message_broker=message_broker
                )
                self.llm_client = llm_client

            async def process_message(self, message: Message) -> Message:
                text = self._extract_text_content(message)

                # Ask LLM which agent should handle this
                routing_query = f"""Given this user request: "{text}"

Which agent should handle it?
- Calculator Agent: for math operations
- Memory Agent: for storing/retrieving data
- Analysis Agent: for text analysis and weather
- Media Agent: for video/audio sessions

Respond with ONLY the agent name and a brief reason, like: "Calculator Agent - because it involves math"
"""
                routing_msg = Message(parts=[Part(type="text", content=routing_query)])
                llm_decision = await self.llm_client.process_message(routing_msg)
                decision_text = self._extract_text_content(llm_decision)

                logger.info(f"🤖 LLM Decision: {decision_text}")

                # Parse the decision and route accordingly
                if "Calculator" in decision_text:
                    await self.send_message_to_agent("Calculator Agent", message)
                    return Message(parts=[Part(type="text", content=f"Routed to Calculator. LLM reasoning: {decision_text}")])
                elif "Memory" in decision_text:
                    await self.send_message_to_agent("Memory Agent", message)
                    return Message(parts=[Part(type="text", content=f"Routed to Memory. LLM reasoning: {decision_text}")])
                elif "Analysis" in decision_text:
                    await self.send_message_to_agent("Analysis Agent", message)
                    return Message(parts=[Part(type="text", content=f"Routed to Analysis. LLM reasoning: {decision_text}")])
                else:
                    return Message(parts=[Part(type="text", content=f"LLM suggested: {decision_text}")])

        orchestrator = LLMOrchestrator(remote_client, message_broker=broker)
        await orchestrator.initialize(broker)
        logger.info("✓ LLM Orchestrator created")

        # Test intelligent routing
        test_requests = [
            "What is 456 divided by 12?",
            "Remember that my favorite color is blue",
            "How many words are in this sentence right here?"
        ]

        for request in test_requests:
            logger.info(f"\n→ User request: {request}")
            orch_msg = Message(parts=[Part(type="text", content=request)])
            orch_response = await orchestrator.process_message(orch_msg)
            logger.info(f"← {orch_response.parts[0].content if orch_response.parts else 'No response'}")
            await asyncio.sleep(1)  # Small delay between requests

        logger.info("\n" + "=" * 60)
        logger.info("Demo 6: Query remote agent capabilities")
        logger.info("=" * 60)

        if remote_client.agent_card:
            logger.info(f"Remote LLM Agent Card:")
            logger.info(f"  Name: {remote_client.agent_card.get('name')}")
            logger.info(f"  Description: {remote_client.agent_card.get('description')}")
            logger.info(f"  URL: {remote_client.agent_card.get('url')}")

            skills = remote_client.agent_card.get('skills', [])
            logger.info(f"  Skills ({len(skills)}):")
            for skill in skills[:5]:  # Show first 5 skills
                logger.info(f"    - {skill.get('name')}: {skill.get('description')}")

            capabilities = remote_client.agent_card.get('capabilities', {})
            if capabilities:
                logger.info(f"  Capabilities:")
                logger.info(f"    - Streaming: {capabilities.get('streaming', False)}")
                logger.info(f"    - Push Notifications: {capabilities.get('push_notifications', False)}")
                logger.info(f"    - Media: {capabilities.get('media', False)}")

        logger.info("\n" + "=" * 60)
        logger.info("✓ Remote LLM agent connection demo completed successfully")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"\n✗ Error during demo: {e}")
        logger.error(f"Make sure an A2A server is running at {remote_url}")
        logger.error("You can start one with: python run_server.py run --port 4400")

    finally:
        # Cleanup
        await remote_client.close()
        await broker.stop()


async def interactive_remote_session(remote_url: str = "http://localhost:4400"):
    """Interactive session with remote agent."""
    logger.info("=" * 60)
    logger.info("Interactive Remote Agent Session")
    logger.info(f"Connected to: {remote_url}")
    logger.info("=" * 60)
    logger.info("Type messages to send to the remote agent")
    logger.info("Type 'quit' to exit")
    logger.info("=" * 60)

    broker = InMemoryMessageBroker()
    await broker.start()

    remote_client = RemoteAgentClient(remote_url, message_broker=broker)

    try:
        await remote_client.initialize(broker)

        while True:
            try:
                # Get user input
                user_input = input("\nYou: ").strip()

                if user_input.lower() in ['quit', 'exit', 'q']:
                    logger.info("Goodbye!")
                    break

                if not user_input:
                    continue

                # Send to remote agent
                message = Message(parts=[Part(type="text", content=user_input)])
                response = await remote_client.process_message(message)

                # Display response
                if response.parts:
                    print(f"Remote Agent: {response.parts[0].content}")
                else:
                    print("Remote Agent: (no response)")

            except KeyboardInterrupt:
                logger.info("\nSession interrupted")
                break
            except Exception as e:
                logger.error(f"Error: {e}")

    finally:
        await remote_client.close()
        await broker.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Connect to remote A2A agent")
    parser.add_argument(
        "--url",
        default="http://localhost:4400",
        help="URL of the remote A2A agent (default: http://localhost:4400)"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start interactive session"
    )

    args = parser.parse_args()

    async def main():
        if args.interactive:
            await interactive_remote_session(args.url)
        else:
            await demo_remote_agent_connection(args.url)

    asyncio.run(main())
