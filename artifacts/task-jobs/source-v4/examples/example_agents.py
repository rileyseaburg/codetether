"""
Example A2A agents demonstrating different capabilities.
"""

import asyncio
import logging
from typing import Optional

from a2a_server import A2AServer
from a2a_server.agent_card import create_agent_card
from a2a_server.models import Message, Part, AgentProvider
from a2a_server.task_manager import InMemoryTaskManager
from a2a_server.message_broker import InMemoryMessageBroker


class EchoAgent(A2AServer):
    """Simple echo agent that repeats messages back."""
    
    async def _process_message(self, message: Message, skill_id: Optional[str] = None) -> Message:
        """Echo the message back with a prefix."""
        response_parts = []
        for part in message.parts:
            if part.type == "text":
                response_parts.append(Part(
                    type="text",
                    content=f"Echo: {part.content}"
                ))
            else:
                # Pass through other content types
                response_parts.append(part)
        
        return Message(parts=response_parts)


class CalculatorAgent(A2AServer):
    """Calculator agent that performs basic math operations."""
    
    async def _process_message(self, message: Message, skill_id: Optional[str] = None) -> Message:
        """Process mathematical expressions."""
        response_parts = []
        
        for part in message.parts:
            if part.type == "text":
                content = part.content.strip()
                try:
                    # Simple expression evaluation (be careful in production!)
                    if all(c in "0123456789+-*/(). " for c in content):
                        result = eval(content)
                        response_parts.append(Part(
                            type="text",
                            content=f"{content} = {result}"
                        ))
                    else:
                        response_parts.append(Part(
                            type="text",
                            content="I can only evaluate basic mathematical expressions."
                        ))
                except Exception as e:
                    response_parts.append(Part(
                        type="text",
                        content=f"Error evaluating expression: {str(e)}"
                    ))
            else:
                response_parts.append(part)
        
        return Message(parts=response_parts)


class GreetingAgent(A2AServer):
    """Friendly greeting agent."""
    
    async def _process_message(self, message: Message, skill_id: Optional[str] = None) -> Message:
        """Generate friendly greetings and responses."""
        response_parts = []
        
        for part in message.parts:
            if part.type == "text":
                content = part.content.lower().strip()
                
                if any(word in content for word in ["hello", "hi", "hey"]):
                    response = "Hello! Nice to meet you. How can I help you today?"
                elif any(word in content for word in ["goodbye", "bye", "farewell"]):
                    response = "Goodbye! Have a wonderful day!"
                elif "how are you" in content:
                    response = "I'm doing great, thank you for asking! How are you?"
                elif "thank you" in content or "thanks" in content:
                    response = "You're very welcome! I'm happy to help."
                else:
                    response = f"That's interesting! You said: '{part.content}'. Is there anything specific I can help you with?"
                
                response_parts.append(Part(
                    type="text",
                    content=response
                ))
            else:
                response_parts.append(part)
        
        return Message(parts=response_parts)


async def create_echo_agent() -> EchoAgent:
    """Create an echo agent instance."""
    agent_card = (create_agent_card(
        name="Echo Agent",
        description="A simple agent that echoes back messages",
        url="http://localhost:8001",
        organization="A2A Examples",
        organization_url="https://example.com"
    )
    .with_streaming()
    .with_skill(
        skill_id="echo",
        name="Echo Messages",
        description="Echoes back any message with a prefix",
        input_modes=["text"],
        output_modes=["text"],
        examples=[{
            "input": {"type": "text", "content": "Hello world!"},
            "output": {"type": "text", "content": "Echo: Hello world!"}
        }]
    )
    .build())
    
    return EchoAgent(
        agent_card=agent_card,
        task_manager=InMemoryTaskManager(),
        message_broker=InMemoryMessageBroker()
    )


async def create_calculator_agent() -> CalculatorAgent:
    """Create a calculator agent instance."""
    agent_card = (create_agent_card(
        name="Calculator Agent",
        description="A calculator agent that performs basic mathematical operations",
        url="http://localhost:8002",
        organization="A2A Examples", 
        organization_url="https://example.com"
    )
    .with_streaming()
    .with_skill(
        skill_id="calculate",
        name="Basic Math",
        description="Performs basic mathematical calculations",
        input_modes=["text"],
        output_modes=["text"],
        examples=[{
            "input": {"type": "text", "content": "2 + 2"},
            "output": {"type": "text", "content": "2 + 2 = 4"}
        }]
    )
    .build())
    
    return CalculatorAgent(
        agent_card=agent_card,
        task_manager=InMemoryTaskManager(),
        message_broker=InMemoryMessageBroker()
    )


async def create_greeting_agent() -> GreetingAgent:
    """Create a greeting agent instance."""
    agent_card = (create_agent_card(
        name="Greeting Agent",
        description="A friendly agent that provides greetings and social interactions",
        url="http://localhost:8003",
        organization="A2A Examples",
        organization_url="https://example.com"
    )
    .with_streaming()
    .with_skill(
        skill_id="greet",
        name="Friendly Greetings",
        description="Provides friendly greetings and social interactions",
        input_modes=["text"],
        output_modes=["text"],
        examples=[{
            "input": {"type": "text", "content": "Hello!"},
            "output": {"type": "text", "content": "Hello! Nice to meet you. How can I help you today?"}
        }]
    )
    .build())
    
    return GreetingAgent(
        agent_card=agent_card,
        task_manager=InMemoryTaskManager(),
        message_broker=InMemoryMessageBroker()
    )


if __name__ == "__main__":
    # Example of running the echo agent
    logging.basicConfig(level=logging.INFO)
    
    async def main():
        agent = await create_echo_agent()
        await agent.start(port=8001)
    
    asyncio.run(main())