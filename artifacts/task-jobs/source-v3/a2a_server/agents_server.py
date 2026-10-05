"""
A2A Server using OpenAI Agents SDK
This replaces the custom MCP implementation with the official OpenAI Agents SDK.
"""
import asyncio
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents import Agent, Runner, function_tool
from agents.memory import SQLiteSession

logger = logging.getLogger(__name__)


class TaskRequest(BaseModel):
    """Request to create a task."""
    input: str
    session_id: Optional[str] = None
    agent_name: Optional[str] = "Assistant"


class TaskResponse(BaseModel):
    """Response from task execution."""
    output: str
    session_id: Optional[str] = None
    timestamp: str


# Define agent tools using the @function_tool decorator
@function_tool
def calculator(operation: str, a: float, b: float = 0.0) -> str:
    """
    Perform mathematical calculations.

    Args:
        operation: The operation to perform (add, subtract, multiply, divide, square, sqrt)
        a: First number
        b: Second number (optional for unary operations)

    Returns:
        The result of the calculation as a string
    """
    try:
        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                return "Error: Division by zero"
            result = a / b
        elif operation == "square":
            result = a ** 2
        elif operation == "sqrt":
            if a < 0:
                return "Error: Cannot take square root of negative number"
            result = a ** 0.5
        else:
            return f"Error: Unknown operation '{operation}'"

        return f"Result: {result}"
    except Exception as e:
        return f"Error: {str(e)}"


@function_tool
def get_weather(city: str) -> str:
    """
    Get weather information for a city.

    Args:
        city: The name of the city

    Returns:
        Weather information as a string
    """
    import os
    api_key = os.environ.get('WEATHER_API_KEY')
    if not api_key:
        return f"Weather service not configured. Set WEATHER_API_KEY environment variable."
    return f"Weather API integration not yet implemented for {city}. Configure a weather provider."


@function_tool
def echo(message: str) -> str:
    """
    Echo back a message.

    Args:
        message: The message to echo

    Returns:
        The same message
    """
    return message


class AgentsServer:
    """FastAPI server using OpenAI Agents SDK."""

    def __init__(self, port: int = 9000):
        self.app = FastAPI(title="A2A Agents Server", version="0.1.0")
        self.port = port
        self.sessions_db = "a2a_sessions.db"

        # Create default agents
        self.agents = {
            "Assistant": Agent(
                name="Assistant",
                instructions="You are a helpful assistant with access to various tools.",
                tools=[calculator, get_weather, echo]
            ),
            "Calculator": Agent(
                name="Calculator Agent",
                instructions="You specialize in mathematical calculations. Use the calculator tool for all math operations.",
                tools=[calculator]
            ),
            "Weather": Agent(
                name="Weather Agent",
                instructions="You specialize in providing weather information. Use the weather tool to get current conditions.",
                tools=[get_weather]
            )
        }

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup FastAPI routes."""

        @self.app.get("/")
        async def root():
            """Root endpoint with server info."""
            return {
                "name": "A2A Agents Server",
                "version": "0.1.0",
                "framework": "OpenAI Agents SDK",
                "agents": list(self.agents.keys()),
                "endpoints": {
                    "chat": "/chat",
                    "agents": "/agents",
                    "health": "/health"
                }
            }

        @self.app.get("/health")
        async def health():
            """Health check endpoint."""
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}

        @self.app.get("/agents")
        async def list_agents():
            """List available agents."""
            return {
                "agents": [
                    {
                        "name": name,
                        "instructions": agent.instructions,
                        "tools": [tool.__name__ if hasattr(tool, '__name__') else str(tool) for tool in agent.tools]
                    }
                    for name, agent in self.agents.items()
                ]
            }

        @self.app.post("/chat", response_model=TaskResponse)
        async def chat(request: TaskRequest):
            """
            Run an agent with the given input.

            Supports session memory if session_id is provided.
            """
            try:
                # Get the agent
                agent = self.agents.get(request.agent_name)
                if not agent:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Agent '{request.agent_name}' not found"
                    )

                # Create session if session_id provided
                session = None
                if request.session_id:
                    session = SQLiteSession(request.session_id, self.sessions_db)

                # Run the agent
                result = await Runner.run(
                    agent,
                    input=request.input,
                    session=session
                )

                return TaskResponse(
                    output=result.final_output,
                    session_id=request.session_id,
                    timestamp=datetime.now().isoformat()
                )

            except Exception as e:
                logger.error(f"Error running agent: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/chat/stream")
        async def chat_stream(input: str, agent_name: str = "Assistant", session_id: Optional[str] = None):
            """
            Stream agent responses using Server-Sent Events.
            """
            async def event_generator():
                try:
                    # Get the agent
                    agent = self.agents.get(agent_name)
                    if not agent:
                        yield f"data: {{'error': 'Agent not found'}}\n\n"
                        return

                    # Create session if needed
                    session = None
                    if session_id:
                        session = SQLiteSession(session_id, self.sessions_db)

                    # Stream the response
                    result = Runner.run_streamed(agent, input=input, session=session)

                    async for event in result.stream_events():
                        if event.type == "run_item_stream_event":
                            yield f"data: {{'type': 'chunk', 'content': '{event.item}'}}\n\n"

                    # Send final output
                    yield f"data: {{'type': 'final', 'output': '{result.final_output}'}}\n\n"

                except Exception as e:
                    logger.error(f"Error in stream: {e}", exc_info=True)
                    yield f"data: {{'error': '{str(e)}'}}\n\n"

            return StreamingResponse(
                event_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )

    async def start(self):
        """Start the server."""
        import uvicorn
        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()


async def main():
    """Main entry point."""
    server = AgentsServer(port=9000)
    logger.info(f"Starting A2A Agents Server on port {server.port}")
    await server.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
