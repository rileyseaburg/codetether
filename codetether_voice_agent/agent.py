"""LiveKit Voice Agent with Gemini 3 Live API and CodeTether MCP Integration.

This module provides a voice-enabled AI agent that uses Google's Gemini 3 Live API
for real-time voice conversation and integrates with CodeTether MCP tools for
task management and agent communication.
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from typing import Any, Dict, List, Optional


def _validate_environment():
    """Validate required environment variables are set.

    Raises:
        SystemExit: If required environment variables are missing.
    """
    required_vars = {
        'LIVEKIT_API_KEY': 'Required for LiveKit worker registration',
        'LIVEKIT_API_SECRET': 'Required for LiveKit worker registration',
    }

    # At least one Google credential is required
    google_api_key = os.getenv('GOOGLE_API_KEY', '').strip()
    google_creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '').strip()

    missing = []
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value or value.strip() == '':
            missing.append(f'  - {var}: {description}')

    if not google_api_key and not google_creds_path:
        missing.append(
            '  - GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS: '
            'Required for Gemini Live API authentication'
        )

    if missing:
        error_msg = (
            'ERROR: Missing required environment variables:\n'
            + '\n'.join(missing)
            + '\n\nPlease ensure these are set in your deployment configuration.'
        )
        print(error_msg, file=sys.stderr)
        logging.error(error_msg)
        sys.exit(1)

    # Log successful validation
    print(f'Environment validation passed:', file=sys.stderr)
    print(f'  - LIVEKIT_API_KEY: set', file=sys.stderr)
    print(f'  - LIVEKIT_API_SECRET: set', file=sys.stderr)
    if google_api_key:
        print(
            f'  - GOOGLE_API_KEY: set (length: {len(google_api_key)})',
            file=sys.stderr,
        )
    if google_creds_path:
        print(
            f'  - GOOGLE_APPLICATION_CREDENTIALS: {google_creds_path}',
            file=sys.stderr,
        )


# Validate environment before importing anything else
_validate_environment()

from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.plugins import google

from codetether_mcp import CodeTetherMCP
from functiongemma_caller import FunctionGemmaCaller
from session_playback import SessionPlayback

logger = logging.getLogger(__name__)

VOICES: Dict[str, str] = {
    'puck': 'Puck',
    'charon': 'Charon',
    'kore': 'Kore',
    'fenrir': 'Fenrir',
    'aoede': 'Aoede',
}

DEFAULT_VOICE = 'puck'

SYSTEM_INSTRUCTIONS = """You are a helpful voice assistant powered by Gemini 3 Live API.

Your core capabilities:
1. Voice Conversation - You can speak naturally with users in real-time
2. Task Management - Create, list, get, and cancel tasks
3. Session Playback - Play back historical conversation sessions
4. Agent Communication - Send messages to other agents in the system
5. Session Management - Retrieve and continue previous conversations

Available Tools:
- create_task: Create a new task with title, description, optional codebase_id and priority
- list_tasks: List tasks with optional status and codebase_id filters
- get_task: Get details of a specific task by ID
- cancel_task: Cancel an active task by ID
- get_session_history: Retrieve message history for a session
- playback_session: Play back a session verbatim or as summary
- discover_agents: List available agents in the system
- send_message: Send a message to a specific agent

Guidelines:
- Speak clearly and concisely in your responses
- Use tools proactively when users ask for task management or information
- Confirm tool results before proceeding with related actions
- Handle errors gracefully and explain issues clearly
- For session playback, offer both verbatim and summary options
- When agents are mentioned, provide helpful information about their capabilities

Remember to adapt your communication style to be natural for voice interaction."""


def format_history_for_context(history: List[Dict[str, Any]]) -> str:
    """Format message history into a readable string for context.

    Args:
        history: List of message dictionaries with 'role' and 'content' keys.

    Returns:
        A formatted string representation of the conversation history.
    """
    if not history:
        return 'No previous conversation history.'

    formatted_parts = []
    for message in history:
        role = message.get('role', 'unknown')
        content = message.get('content', '')

        if not content:
            continue

        if role == 'user':
            formatted_parts.append(f'User: {content}')
        elif role in ('assistant', 'agent'):
            formatted_parts.append(f'Agent: {content}')
        else:
            formatted_parts.append(f'{role.capitalize()}: {content}')

    return '\n'.join(formatted_parts)


def create_tools(mcp_client: CodeTetherMCP) -> List[llm.FunctionTool]:
    """Create FunctionTool objects for the voice agent.

    Args:
        mcp_client: The CodeTether MCP client for tool execution.

    Returns:
        List of FunctionTool objects.
    """
    tools = []

    # List tasks tool
    @llm.function_tool(
        name='list_tasks',
        description='List tasks in the CodeTether system. Use this to show the user what tasks exist.',
    )
    async def list_tasks(status: Optional[str] = None) -> str:
        """List tasks with optional status filter."""
        try:
            logger.info(f'Executing list_tasks with status: {status}')
            tasks = await mcp_client.list_tasks(status=status)
            if not tasks:
                return 'There are no tasks in the system.'
            task_list = ', '.join(
                [f"'{t.title}' ({t.status})" for t in tasks[:5]]
            )
            return f'Found {len(tasks)} tasks: {task_list}'
        except Exception as e:
            logger.error(f'list_tasks failed: {e}')
            return f'Sorry, there was an error listing tasks: {str(e)}'

    tools.append(list_tasks)

    # Create task tool
    @llm.function_tool(
        name='create_task',
        description='Create a new task in the CodeTether system.',
    )
    async def create_task(
        title: str,
        description: str = '',
        priority: int = 0,
    ) -> str:
        """Create a new task."""
        try:
            logger.info(f'Executing create_task: {title}')
            task = await mcp_client.create_task(
                title=title,
                description=description,
                codebase_id='global',
                agent_type='build',
                priority=priority,
            )
            return f"Created task '{task.title}' with ID {task.id}. Status: {task.status}"
        except Exception as e:
            logger.error(f'create_task failed: {e}')
            return f'Sorry, there was an error creating the task: {str(e)}'

    tools.append(create_task)

    # Get task tool
    @llm.function_tool(
        name='get_task',
        description='Get details about a specific task by its ID.',
    )
    async def get_task(task_id: str) -> str:
        """Get task details."""
        try:
            logger.info(f'Executing get_task: {task_id}')
            task = await mcp_client.get_task(task_id)
            if task:
                return f"Task '{task.title}' is {task.status}. Priority: {task.priority}"
            return 'Task not found.'
        except Exception as e:
            logger.error(f'get_task failed: {e}')
            return f'Sorry, there was an error getting the task: {str(e)}'

    tools.append(get_task)

    # Cancel task tool
    @llm.function_tool(
        name='cancel_task',
        description='Cancel a running or pending task.',
    )
    async def cancel_task(task_id: str) -> str:
        """Cancel a task."""
        try:
            logger.info(f'Executing cancel_task: {task_id}')
            success = await mcp_client.cancel_task(task_id)
            return (
                'Task cancelled successfully.'
                if success
                else 'Could not cancel the task.'
            )
        except Exception as e:
            logger.error(f'cancel_task failed: {e}')
            return f'Sorry, there was an error cancelling the task: {str(e)}'

    tools.append(cancel_task)

    # Discover agents tool
    @llm.function_tool(
        name='discover_agents',
        description='Discover available CodeTether agents that can be messaged.',
    )
    async def discover_agents() -> str:
        """Discover available agents."""
        try:
            logger.info('Executing discover_agents')
            agents = await mcp_client.discover_agents()
            if not agents:
                return 'No agents are currently available.'
            agent_names = ', '.join([a.name for a in agents[:5]])
            return f'Found {len(agents)} agents: {agent_names}'
        except Exception as e:
            logger.error(f'discover_agents failed: {e}')
            return f'Sorry, there was an error discovering agents: {str(e)}'

    tools.append(discover_agents)

    logger.info(f'Created {len(tools)} tools for voice agent')
    return tools


async def entrypoint(ctx: JobContext) -> None:
    """Main entrypoint for the voice agent.

    Connects to the LiveKit room, initializes all components, and starts
    the voice agent session with Gemini 3 Live API.

    Args:
        ctx: The job context containing room connection and metadata.
    """
    logger.info(f'Starting voice agent in room: {ctx.room.name}')

    initial_ctx = ctx.room.metadata or '{}'
    try:
        metadata = json.loads(initial_ctx)
    except (json.JSONDecodeError, TypeError):
        metadata = {}

    voice_id = metadata.get('voice', DEFAULT_VOICE)
    codebase_id = metadata.get('codebase_id', 'global')
    session_id = metadata.get('session_id')
    mode = metadata.get('mode', 'interactive')
    playback_style = metadata.get('playback_style', 'verbatim')

    voice_name = VOICES.get(voice_id, VOICES[DEFAULT_VOICE])
    logger.info(
        f'Configuration - voice: {voice_name}, codebase_id: {codebase_id}, '
        f'session_id: {session_id}, mode: {mode}, playback_style: {playback_style}'
    )

    logger.info('About to call ctx.connect()...')
    try:
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
        logger.info('Connected to room successfully!')
    except Exception as e:
        logger.error(f'Failed to connect to room: {type(e).__name__}: {e}')
        raise

    logger.info('Waiting for participant...')
    try:
        participant = await ctx.wait_for_participant()
        logger.info(f'Participant joined: {participant.identity}')
    except Exception as e:
        logger.error(f'Error waiting for participant: {type(e).__name__}: {e}')
        raise

    try:
        api_url = os.getenv('CODETETHER_API_URL', 'http://localhost:8000')
        logger.info(f'Creating CodeTetherMCP with API URL: {api_url}')
        mcp_client = CodeTetherMCP(api_url=api_url)
        logger.info(f'Initialized CodeTetherMCP with API URL: {api_url}')

        function_caller = FunctionGemmaCaller()
        logger.info('Initialized FunctionGemmaCaller')

        session_playback = SessionPlayback(mcp_client=mcp_client)
        logger.info('Initialized SessionPlayback')

        session_history = None
        if session_id:
            try:
                session_history = await mcp_client.get_session_messages(
                    session_id
                )
                logger.info(
                    f'Loaded session history: {len(session_history)} messages'
                )
            except Exception as e:
                logger.warning(f'Failed to load session history: {e}')

        context_string = ''
        if session_history:
            context_string = f'\n\nPrevious conversation context:\n{format_history_for_context(session_history)}'

        full_instructions = SYSTEM_INSTRUCTIONS + context_string

        logger.info(f'Creating Gemini RealtimeModel with voice: {voice_name}')

        # Check if we have Vertex AI credentials (preferred) or fallback to API key
        google_creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        google_api_key = os.getenv('GOOGLE_API_KEY')
        use_vertex = google_creds_path and os.path.exists(google_creds_path)

        if use_vertex:
            logger.info(
                f'Using Vertex AI with credentials from: {google_creds_path}'
            )
            # Get project ID from credentials file or environment
            project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'spotlessbinco')
            location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
            logger.info(
                f'Vertex AI project: {project_id}, location: {location}'
            )

            gemini_model = google.realtime.RealtimeModel(
                model='gemini-live-2.5-flash-native-audio',
                voice=voice_name,
                instructions=full_instructions,
                vertexai=True,
                project=project_id,
                location=location,
            )
        elif google_api_key:
            logger.info(f'Using Google API key (length: {len(google_api_key)})')
            gemini_model = google.realtime.RealtimeModel(
                model='gemini-2.0-flash-exp',
                voice=voice_name,
                instructions=full_instructions,
                api_key=google_api_key,
            )
        else:
            logger.error(
                'No Google credentials found! Set GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_API_KEY'
            )
            raise ValueError('No Google credentials configured')
        logger.info('Gemini RealtimeModel created successfully')

        # Create tools for the agent
        try:
            agent_tools = create_tools(mcp_client)
            logger.info(f'Created {len(agent_tools)} tools for agent')
        except Exception as e:
            logger.error(f'Failed to create tools: {e}')
            agent_tools = []

        session = AgentSession(
            llm=gemini_model,
            tools=agent_tools if agent_tools else None,
        )
        logger.info('AgentSession created with tools')

        if mode == 'playback' and session_id:
            logger.info(
                f'Starting session playback for session_id: {session_id}'
            )
            await session_playback.start(
                session=session,
                session_id=session_id,
                style=playback_style,
            )

        logger.info(f'Starting agent session in room: {ctx.room.name}')

        # Create the Agent with the Gemini model
        agent = Agent(
            instructions=full_instructions,
            llm=gemini_model,
        )

        # Start the session with the agent and room
        await session.start(agent=agent, room=ctx.room)

    except Exception as e:
        logger.error(f'Error in voice agent entrypoint: {e}')
        raise


if __name__ == '__main__':
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        ),
    )
