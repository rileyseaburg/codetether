"""
LLM Agent that connects to Anthropic-compatible API on localhost:4000.

This agent can:
1. Send messages to Claude LLM via the API
2. Participate in agent-to-agent messaging
3. Provide intelligent responses and reasoning
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from a2a_server.enhanced_agents import EnhancedAgent
from a2a_server.models import Message, Part

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClaudeAgent(EnhancedAgent):
    """Agent that uses Claude LLM for intelligent responses."""

    def __init__(
        self,
        api_url: str = "http://localhost:4000/anthropic/v1/messages",
        api_key: str = "xxx",
        model: str = "claude-sonnet-4.5",
        message_broker=None
    ):
        super().__init__(
            name="Claude Agent",
            description="AI assistant powered by Claude LLM",
            message_broker=message_broker
        )
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.http_client = httpx.AsyncClient(timeout=60.0, verify=False)
        self.conversation_history: list = []

    async def call_claude(self, user_message: str, system_prompt: Optional[str] = None) -> str:
        """Call Claude API and get response."""
        try:
            # Prepare messages
            messages = [{"role": "user", "content": user_message}]

            # Prepare request
            request_data = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "max_tokens": 4096
            }

            if system_prompt:
                request_data["system"] = system_prompt

            # Make API call
            response = await self.http_client.post(
                self.api_url,
                json=request_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}"
                }
            )
            response.raise_for_status()

            # Parse response
            result = response.json()

            if "content" in result and len(result["content"]) > 0:
                return result["content"][0]["text"]
            else:
                return "No response from Claude"

        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            return f"Error: {str(e)}"

    async def process_message(self, message: Message) -> Message:
        """Process message using Claude LLM."""
        text = self._extract_text_content(message)

        # Add context about being an agent in a multi-agent system
        system_prompt = """You are Claude, an AI assistant that is part of a multi-agent system.
You can communicate with other specialized agents like Calculator, Memory, and Analysis agents.
Provide helpful, concise responses. When appropriate, mention if another agent might be better suited for the task."""

        # Get response from Claude
        logger.info(f"🤖 Claude processing: {text[:100]}...")
        response_text = await self.call_claude(text, system_prompt)
        logger.info(f"✓ Claude responded ({len(response_text)} chars)")

        # Publish event about Claude interaction
        await self.publish_event("llm.response", {
            "input": text,
            "output": response_text,
            "model": self.model,
            "tokens": len(response_text.split())
        })

        return Message(parts=[Part(type="text", content=response_text)])

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()


async def demo_claude_agent():
    """Demonstrate Claude agent integration."""
    logger.info("=" * 60)
    logger.info("Claude LLM Agent Demo")
    logger.info("=" * 60)

    from a2a_server.message_broker import InMemoryMessageBroker
    from a2a_server.enhanced_agents import initialize_agent_registry, ENHANCED_AGENTS

    # Create message broker
    broker = InMemoryMessageBroker()
    await broker.start()
    logger.info("✓ Message broker started")

    # Initialize local agents
    initialize_agent_registry(broker)
    logger.info("✓ Local agent registry initialized")

    # Create Claude agent
    claude = ClaudeAgent(message_broker=broker)
    await claude.initialize(broker)
    logger.info("✓ Claude agent initialized")

    try:
        logger.info("\n" + "=" * 60)
        logger.info("Demo 1: Simple question to Claude")
        logger.info("=" * 60)

        question = "What are the key benefits of agent-to-agent communication?"
        msg = Message(parts=[Part(type="text", content=question)])
        response = await claude.process_message(msg)
        logger.info(f"\nQuestion: {question}")
        logger.info(f"\nClaude's Response:\n{response.parts[0].content}\n")

        logger.info("\n" + "=" * 60)
        logger.info("Demo 2: Claude + Calculator coordination")
        logger.info("=" * 60)

        calculator = ENHANCED_AGENTS.get("calculator")
        if calculator:
            await calculator.initialize(broker)

            # Do calculation
            calc_msg = Message(parts=[Part(type="text", content="Calculate 1234 * 567")])
            calc_response = await calculator.process_message(calc_msg)
            calc_result = calc_response.parts[0].content
            logger.info(f"Calculator: {calc_result}")

            # Ask Claude to explain
            explain_msg = Message(parts=[Part(
                type="text",
                content=f"The calculator says: {calc_result}. Can you explain this multiplication in an interesting way?"
            )])
            claude_response = await claude.process_message(explain_msg)
            logger.info(f"\nClaude's Explanation:\n{claude_response.parts[0].content}\n")

        logger.info("\n" + "=" * 60)
        logger.info("Demo 3: Claude-powered intelligent router")
        logger.info("=" * 60)

        class IntelligentRouter(EnhancedAgent):
            """Uses Claude to make intelligent routing decisions."""

            def __init__(self, claude_agent: ClaudeAgent, message_broker=None):
                super().__init__(
                    name="Intelligent Router",
                    description="Routes requests using Claude's reasoning",
                    message_broker=message_broker
                )
                self.claude = claude_agent

            async def process_message(self, message: Message) -> Message:
                text = self._extract_text_content(message)

                # Ask Claude which agent should handle this
                routing_prompt = f"""Given this user request: "{text}"

Which specialized agent should handle it? Choose ONE:
1. Calculator Agent - for mathematical calculations
2. Memory Agent - for storing/retrieving information
3. Analysis Agent - for text analysis and weather info
4. You (Claude) - for general questions, explanations, or advice

Respond with ONLY the agent name and one sentence explaining why.
Format: "Agent Name - Reason"
"""

                routing_msg = Message(parts=[Part(type="text", content=routing_prompt)])
                decision = await self.claude.process_message(routing_msg)
                decision_text = self._extract_text_content(decision)

                logger.info(f"🧠 Claude's routing decision: {decision_text}")

                # Route based on decision
                if "Calculator" in decision_text:
                    await self.send_message_to_agent("Calculator Agent", message)
                    return Message(parts=[Part(type="text", content=f"Routed to Calculator Agent. Reasoning: {decision_text}")])
                elif "Memory" in decision_text:
                    await self.send_message_to_agent("Memory Agent", message)
                    return Message(parts=[Part(type="text", content=f"Routed to Memory Agent. Reasoning: {decision_text}")])
                elif "Analysis" in decision_text:
                    await self.send_message_to_agent("Analysis Agent", message)
                    return Message(parts=[Part(type="text", content=f"Routed to Analysis Agent. Reasoning: {decision_text}")])
                else:
                    # Let Claude handle it
                    claude_response = await self.claude.process_message(message)
                    return claude_response

        router = IntelligentRouter(claude, message_broker=broker)
        await router.initialize(broker)
        logger.info("✓ Intelligent Router created")

        # Test routing
        test_requests = [
            "What is 789 + 456?",
            "Store the fact that our system uses Redis for message brokering",
            "What's the best architecture pattern for microservices?"
        ]

        for request in test_requests:
            logger.info(f"\n→ Request: {request}")
            router_msg = Message(parts=[Part(type="text", content=request)])
            router_response = await router.process_message(router_msg)
            logger.info(f"← Response: {router_response.parts[0].content[:200]}...")
            await asyncio.sleep(1)

        logger.info("\n" + "=" * 60)
        logger.info("Demo 4: Multi-agent collaboration with Claude")
        logger.info("=" * 60)

        # Create a workflow agent
        class WorkflowAgent(EnhancedAgent):
            """Orchestrates complex workflows using Claude for reasoning."""

            def __init__(self, claude_agent: ClaudeAgent, message_broker=None):
                super().__init__(
                    name="Workflow Agent",
                    description="Orchestrates multi-step workflows",
                    message_broker=message_broker
                )
                self.claude = claude_agent

            async def process_message(self, message: Message) -> Message:
                text = self._extract_text_content(message)

                # Ask Claude to break down the task
                planning_prompt = f"""Break down this task into steps: "{text}"

Provide a numbered list of steps, where each step specifies which agent should do what.
Available agents: Calculator, Memory, Analysis, Claude (you)
Be specific and concise."""

                plan_msg = Message(parts=[Part(type="text", content=planning_prompt)])
                plan = await self.claude.process_message(plan_msg)
                plan_text = self._extract_text_content(plan)

                logger.info(f"\n📋 Workflow Plan:\n{plan_text}\n")

                return Message(parts=[Part(type="text", content=f"Workflow planned:\n{plan_text}")])

        workflow = WorkflowAgent(claude, message_broker=broker)
        await workflow.initialize(broker)

        complex_task = "Calculate the area of a circle with radius 10, store the formula in memory, and then explain why pi is important in this calculation"
        workflow_msg = Message(parts=[Part(type="text", content=complex_task)])
        logger.info(f"Complex Task: {complex_task}")
        workflow_response = await workflow.process_message(workflow_msg)

        logger.info("\n" + "=" * 60)
        logger.info("✓ Claude LLM Agent demo completed successfully")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"\n✗ Error during demo: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await claude.close()
        await broker.stop()


async def interactive_claude_session():
    """Interactive session with Claude agent."""
    logger.info("=" * 60)
    logger.info("Interactive Claude Agent Session")
    logger.info("=" * 60)
    logger.info("Chat with Claude! Type 'quit' to exit")
    logger.info("=" * 60)

    from a2a_server.message_broker import InMemoryMessageBroker

    broker = InMemoryMessageBroker()
    await broker.start()

    claude = ClaudeAgent(message_broker=broker)
    await claude.initialize(broker)

    try:
        while True:
            try:
                user_input = input("\nYou: ").strip()

                if user_input.lower() in ['quit', 'exit', 'q']:
                    logger.info("Goodbye!")
                    break

                if not user_input:
                    continue

                msg = Message(parts=[Part(type="text", content=user_input)])
                response = await claude.process_message(msg)

                print(f"\nClaude: {response.parts[0].content if response.parts else 'No response'}")

            except KeyboardInterrupt:
                logger.info("\nSession interrupted")
                break
            except Exception as e:
                logger.error(f"Error: {e}")

    finally:
        await claude.close()
        await broker.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Claude LLM Agent")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start interactive chat session"
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:4000/anthropic/v1/messages",
        help="Claude API URL"
    )
    parser.add_argument(
        "--api-key",
        default="xxx",
        help="API key"
    )
    parser.add_argument(
        "--model",
        default="claude-3.5-sonnet",
        help="Model name"
    )

    args = parser.parse_args()

    # Update ClaudeAgent defaults if provided
    if args.api_url != "http://localhost:4000/anthropic/v1/messages":
        ClaudeAgent.__init__.__defaults__ = (
            args.api_url,
            args.api_key,
            args.model,
            None
        )

    async def main():
        if args.interactive:
            await interactive_claude_session()
        else:
            await demo_claude_agent()

    asyncio.run(main())
