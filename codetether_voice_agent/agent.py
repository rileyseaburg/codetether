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
from livekit.rtc import Room

from codetether_mcp import CodeTetherMCP
from functiongemma_caller import FunctionGemmaCaller
from session_playback import SessionPlayback

logger = logging.getLogger(__name__)

# Global reference to room for state publishing
_current_room: Optional[Room] = None


async def emit_thinking_state(context: Optional[str] = None) -> None:
    """Emit a 'thinking' state to indicate the agent is processing.

    Args:
        context: Optional context about what the agent is thinking about.
    """
    await publish_state(
        _current_room, 'thinking', {'context': context} if context else None
    )


async def publish_state(
    room: Optional[Room], state: str, data: Optional[Dict[str, Any]] = None
) -> None:
    """Publish agent state to the room via data messages.

    Args:
        room: The LiveKit room to publish to.
        state: The current state (e.g., 'tool_calling', 'tool_complete', 'thinking').
        data: Optional additional data to include in the message.
    """
    if room is None:
        logger.warning('Cannot publish state: room is None')
        return

    message = json.dumps(
        {'type': 'agent_state', 'state': state, **(data or {})}
    )
    try:
        await room.local_participant.publish_data(
            message.encode(), reliable=True
        )
        logger.debug(f'Published state: {state}, data: {data}')
    except Exception as e:
        logger.warning(f'Failed to publish state: {e}')


def create_tool_wrapper(tool_name: str, tool_func, room_getter):
    """Create a wrapper function that emits state before/after tool execution.

    Args:
        tool_name: Name of the tool being wrapped.
        tool_func: The actual tool function to wrap.
        room_getter: A callable that returns the current room.

    Returns:
        A wrapped async function that emits state updates.
    """

    async def wrapper(*args, **kwargs):
        room = room_getter()

        # Emit tool_calling state
        await publish_state(
            room, 'tool_calling', {'tool_name': tool_name, 'args': str(kwargs)}
        )

        try:
            # Execute the actual tool
            result = await tool_func(*args, **kwargs)

            # Emit tool_complete state
            await publish_state(
                room,
                'tool_complete',
                {
                    'tool_name': tool_name,
                    'result': str(result)[:500],  # Truncate long results
                    'success': True,
                },
            )

            return result
        except Exception as e:
            # Emit tool_error state
            await publish_state(
                room,
                'tool_complete',
                {'tool_name': tool_name, 'error': str(e), 'success': False},
            )
            raise

    return wrapper


VOICES: Dict[str, str] = {
    'puck': 'Puck',
    'charon': 'Charon',
    'kore': 'Kore',
    'fenrir': 'Fenrir',
    'aoede': 'Aoede',
}

DEFAULT_VOICE = 'puck'

SYSTEM_INSTRUCTIONS = """You are a voice assistant for CodeTether, an Agent-to-Agent (A2A) task management and coordination system.

## About CodeTether / A2A Server
CodeTether is a system that allows AI agents to collaborate on coding tasks. Key concepts:
- **Tasks**: Work items that get queued and executed by worker agents (build, test, review, deploy, etc.)
- **Workers**: Rust-based codetether-agent processes that connect via SSE and autonomously execute tasks using AI models
- **Agents**: Registered services that can communicate with each other via the A2A protocol
- **Monitoring**: All agent activity is logged and can be reviewed in real time

## Your Role
You are the voice interface to the CodeTether system. Users talk to you to:
1. Create and manage tasks for the worker agents to execute
2. Check on task status and results
3. Review what agents have been doing (monitoring messages)
4. Send messages to other registered agents

## Available Tools

### Task Management
- **create_task**: Queue a new coding task. Specify title, description, priority (0-10). Tasks are claimed by codetether-agent workers via SSE.
- **list_tasks**: See all tasks. Filter by status (pending, working, completed, failed, cancelled).
- **get_task**: Get detailed info about a specific task by its ID.
- **cancel_task**: Stop a pending or in-progress task.

### Agent Communication
- **discover_agents**: Find what agents are registered in the system.
- **send_message**: Send a message to a registered agent for agent-to-agent communication.

### Monitoring & History
- **get_monitor_messages**: See recent activity from all agents in the monitoring system.
- **get_conversation_history**: Get the message history for a specific conversation thread (by conversation ID).

## Important Clarification
"Session history" and "conversation history" refer to logged messages in the A2A server's monitoring system - NOT our current voice conversation. These are records of past tasks, agent communications, and system events. If you want to know what you just discussed with the user, that's in your context - no tool needed.

## Guidelines
- Speak naturally and concisely for voice interaction
- Use tools proactively when users ask about tasks or agent activity
- When users say "session history" they likely mean monitoring messages or past task results
- Clarify if the user wants to create a task vs. just discuss something
- Confirm task creation before proceeding"""


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

    Each tool emits state updates via LiveKit data messages before and after execution
    to keep the frontend informed of agent activity.

    Args:
        mcp_client: The CodeTether MCP client for tool execution.

    Returns:
        List of FunctionTool objects.
    """
    global _current_room
    tools = []

    # List tasks tool
    @llm.function_tool(
        name='list_tasks',
        description='List tasks in the CodeTether system. Use this to show the user what tasks exist.',
    )
    async def list_tasks(status: Optional[str] = None) -> str:
        """List tasks with optional status filter."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'list_tasks', 'args': {'status': status}},
        )
        try:
            logger.info(f'Executing list_tasks with status: {status}')
            tasks = await mcp_client.list_tasks(status=status)
            if not tasks:
                result = 'There are no tasks in the system.'
            else:
                task_list = ', '.join(
                    [f"'{t.title}' ({t.status})" for t in tasks[:5]]
                )
                result = f'Found {len(tasks)} tasks: {task_list}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'list_tasks', 'result': result, 'success': True},
            )
            return result
        except Exception as e:
            logger.error(f'list_tasks failed: {e}')
            error_result = f'Sorry, there was an error listing tasks: {str(e)}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'list_tasks', 'error': str(e), 'success': False},
            )
            return error_result

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
        await publish_state(
            _current_room,
            'tool_calling',
            {
                'tool_name': 'create_task',
                'args': {
                    'title': title,
                    'description': description,
                    'priority': priority,
                },
            },
        )
        try:
            logger.info(f'Executing create_task: {title}')
            task = await mcp_client.create_task(
                title=title,
                description=description,
                codebase_id='global',
                agent_type='build',
                priority=priority,
            )
            result = f"Created task '{task.title}' with ID {task.id}. Status: {task.status}"
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'create_task', 'result': result, 'success': True},
            )
            return result
        except Exception as e:
            logger.error(f'create_task failed: {e}')
            error_result = (
                f'Sorry, there was an error creating the task: {str(e)}'
            )
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'create_task', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(create_task)

    # Get task tool
    @llm.function_tool(
        name='get_task',
        description='Get details about a specific task by its ID.',
    )
    async def get_task(task_id: str) -> str:
        """Get task details."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'get_task', 'args': {'task_id': task_id}},
        )
        try:
            logger.info(f'Executing get_task: {task_id}')
            task = await mcp_client.get_task(task_id)
            if task:
                result = f"Task '{task.title}' is {task.status}. Priority: {task.priority}"
            else:
                result = 'Task not found.'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'get_task', 'result': result, 'success': True},
            )
            return result
        except Exception as e:
            logger.error(f'get_task failed: {e}')
            error_result = (
                f'Sorry, there was an error getting the task: {str(e)}'
            )
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'get_task', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(get_task)

    # Cancel task tool
    @llm.function_tool(
        name='cancel_task',
        description='Cancel a running or pending task.',
    )
    async def cancel_task(task_id: str) -> str:
        """Cancel a task."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'cancel_task', 'args': {'task_id': task_id}},
        )
        try:
            logger.info(f'Executing cancel_task: {task_id}')
            success = await mcp_client.cancel_task(task_id)
            result = (
                'Task cancelled successfully.'
                if success
                else 'Could not cancel the task.'
            )
            await publish_state(
                _current_room,
                'tool_complete',
                {
                    'tool_name': 'cancel_task',
                    'result': result,
                    'success': success,
                },
            )
            return result
        except Exception as e:
            logger.error(f'cancel_task failed: {e}')
            error_result = (
                f'Sorry, there was an error cancelling the task: {str(e)}'
            )
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'cancel_task', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(cancel_task)

    # Discover agents tool
    @llm.function_tool(
        name='discover_agents',
        description='Discover available CodeTether agents that can be messaged.',
    )
    async def discover_agents() -> str:
        """Discover available agents."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'discover_agents', 'args': {}},
        )
        try:
            logger.info('Executing discover_agents')
            agents = await mcp_client.discover_agents()
            if not agents:
                result = 'No agents are currently available.'
            else:
                agent_names = ', '.join([a.name for a in agents[:5]])
                result = f'Found {len(agents)} agents: {agent_names}'
            await publish_state(
                _current_room,
                'tool_complete',
                {
                    'tool_name': 'discover_agents',
                    'result': result,
                    'success': True,
                },
            )
            return result
        except Exception as e:
            logger.error(f'discover_agents failed: {e}')
            error_result = (
                f'Sorry, there was an error discovering agents: {str(e)}'
            )
            await publish_state(
                _current_room,
                'tool_complete',
                {
                    'tool_name': 'discover_agents',
                    'error': str(e),
                    'success': False,
                },
            )
            return error_result

    tools.append(discover_agents)

    # Send message to agent tool
    @llm.function_tool(
        name='send_message',
        description='Send a message to a specific CodeTether agent for agent-to-agent communication.',
    )
    async def send_message(agent_name: str, message: str) -> str:
        """Send a message to an agent."""
        await publish_state(
            _current_room,
            'tool_calling',
            {
                'tool_name': 'send_message',
                'args': {'agent_name': agent_name, 'message': message[:100]},
            },
        )
        try:
            logger.info(f'Executing send_message to {agent_name}')
            result = await mcp_client.send_message(
                agent_name=agent_name, message=message
            )
            if isinstance(result, dict):
                response_text = result.get('response', result.get('message', ''))
                task_id = result.get('task_id', '')
                if response_text:
                    response = f'Message sent to {agent_name}. Response: {str(response_text)[:200]}'
                elif task_id:
                    response = f'Message sent to {agent_name}. Task ID: {task_id}'
                else:
                    response = f'Message sent to {agent_name} successfully.'
            else:
                response = f'Message sent to {agent_name}. Result: {str(result)[:200]}'
            await publish_state(
                _current_room,
                'tool_complete',
                {
                    'tool_name': 'send_message',
                    'result': response,
                    'success': True,
                },
            )
            return response
        except Exception as e:
            logger.error(f'send_message failed: {e}')
            error_result = (
                f'Sorry, there was an error sending the message: {str(e)}'
            )
            await publish_state(
                _current_room,
                'tool_complete',
                {
                    'tool_name': 'send_message',
                    'error': str(e),
                    'success': False,
                },
            )
            return error_result

    tools.append(send_message)

    # Get recent monitor messages tool
    @llm.function_tool(
        name='get_monitor_messages',
        description='Get recent messages from the A2A monitoring system. Shows what tasks and agent communications have happened recently.',
    )
    async def get_monitor_messages(limit: int = 20) -> str:
        """Get recent monitoring messages."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'get_monitor_messages', 'args': {'limit': limit}},
        )
        try:
            logger.info(f'Executing get_monitor_messages with limit: {limit}')
            messages = await mcp_client.get_monitor_messages(limit=limit)
            if not messages:
                result = 'No recent messages in the monitoring system.'
            else:
                msg_summaries = []
                for msg in messages[:5]:
                    agent = msg.get('agent_name', 'unknown')
                    content = msg.get('content', '')[:80]
                    msg_summaries.append(f'{agent}: {content}')
                result = (
                    f'Found {len(messages)} recent messages. Most recent: '
                    + '; '.join(msg_summaries)
                )
            await publish_state(
                _current_room,
                'tool_complete',
                {
                    'tool_name': 'get_monitor_messages',
                    'result': result,
                    'success': True,
                },
            )
            return result
        except Exception as e:
            logger.error(f'get_monitor_messages failed: {e}')
            error_result = (
                f'Sorry, there was an error getting messages: {str(e)}'
            )
            await publish_state(
                _current_room,
                'tool_complete',
                {
                    'tool_name': 'get_monitor_messages',
                    'error': str(e),
                    'success': False,
                },
            )
            return error_result

    tools.append(get_monitor_messages)

    # Get conversation history tool
    @llm.function_tool(
        name='get_conversation_history',
        description='Get the message history for a specific conversation thread by its ID. Use this to review what was discussed in a particular task or session.',
    )
    async def get_conversation_history(conversation_id: str) -> str:
        """Get conversation history by ID."""
        await publish_state(
            _current_room,
            'tool_calling',
            {
                'tool_name': 'get_conversation_history',
                'args': {'conversation_id': conversation_id},
            },
        )
        try:
            logger.info(
                f'Executing get_conversation_history: {conversation_id}'
            )
            messages = await mcp_client.get_session_messages(conversation_id)
            if not messages:
                result = (
                    f"No messages found for conversation '{conversation_id}'."
                )
            else:
                msg_count = len(messages)
                user_count = sum(1 for m in messages if m.role == 'user')
                result = f'Found {msg_count} messages in this conversation ({user_count} from users). '
                if msg_count <= 3:
                    for m in messages:
                        result += f'{m.role}: {m.content[:60]}... '
                else:
                    result += f'Latest: {messages[-1].role}: {messages[-1].content[:100]}...'
            await publish_state(
                _current_room,
                'tool_complete',
                {
                    'tool_name': 'get_conversation_history',
                    'result': result,
                    'success': True,
                },
            )
            return result
        except Exception as e:
            logger.error(f'get_conversation_history failed: {e}')
            error_result = (
                f'Sorry, there was an error getting the conversation: {str(e)}'
            )
            await publish_state(
                _current_room,
                'tool_complete',
                {
                    'tool_name': 'get_conversation_history',
                    'error': str(e),
                    'success': False,
                },
            )
            return error_result

    tools.append(get_conversation_history)

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

    global _current_room

    logger.info('About to call ctx.connect()...')
    try:
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
        logger.info('Connected to room successfully!')
    except Exception as e:
        logger.error(f'Failed to connect to room: {type(e).__name__}: {e}')
        raise

    # Set the global room reference for state publishing
    _current_room = ctx.room
    logger.info('Set global room reference for state publishing')

    # Emit initial connecting state
    await publish_state(_current_room, 'connecting', {'room': ctx.room.name})

    logger.info('Waiting for participant...')
    try:
        participant = await ctx.wait_for_participant()
        logger.info(f'Participant joined: {participant.identity}')
        await publish_state(
            _current_room,
            'participant_joined',
            {'participant': participant.identity},
        )
    except Exception as e:
        logger.error(f'Error waiting for participant: {type(e).__name__}: {e}')
        raise

    try:
        # Emit initializing state
        await publish_state(
            _current_room, 'initializing', {'step': 'mcp_client'}
        )

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
        await publish_state(
            _current_room, 'initializing', {'step': 'model_ready'}
        )

        # Create tools for the agent
        try:
            agent_tools = create_tools(mcp_client)
            logger.info(f'Created {len(agent_tools)} tools for agent')
            await publish_state(
                _current_room,
                'initializing',
                {'step': 'tools_ready', 'tool_count': len(agent_tools)},
            )
        except Exception as e:
            logger.error(f'Failed to create tools: {e}')
            agent_tools = []
            await publish_state(
                _current_room,
                'initializing',
                {'step': 'tools_failed', 'error': str(e)},
            )

        session = AgentSession()
        logger.info('AgentSession created')

        if mode == 'playback' and session_id:
            logger.info(
                f'Starting session playback for session_id: {session_id}'
            )
            await publish_state(
                _current_room,
                'playback_starting',
                {'session_id': session_id, 'style': playback_style},
            )
            await session_playback.start(
                session=session,
                session_id=session_id,
                style=playback_style,
            )

        logger.info(f'Starting agent session in room: {ctx.room.name}')

        # Create the Agent with tools and instructions (canonical pattern)
        agent = Agent(
            instructions=full_instructions,
            llm=gemini_model,
            tools=agent_tools if agent_tools else None,
        )

        # Emit ready state before starting
        await publish_state(
            _current_room, 'ready', {'room': ctx.room.name, 'mode': mode}
        )

        # Start the session with the agent and room
        await session.start(agent=agent, room=ctx.room)

        # Emit listening state after session starts
        await publish_state(_current_room, 'listening', {'voice': voice_name})

    except Exception as e:
        logger.error(f'Error in voice agent entrypoint: {e}')
        await publish_state(_current_room, 'error', {'error': str(e)})
        raise


if __name__ == '__main__':
    init_timeout = float(
        os.getenv('VOICE_WORKER_INIT_TIMEOUT_SEC', '45')
    )
    shutdown_timeout = float(
        os.getenv('VOICE_WORKER_SHUTDOWN_TIMEOUT_SEC', '15')
    )
    max_retry = int(os.getenv('VOICE_WORKER_MAX_RETRY', '24'))
    agent_name = os.getenv('VOICE_AGENT_NAME', 'codetether-voice-agent')

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            initialize_process_timeout=init_timeout,
            shutdown_process_timeout=shutdown_timeout,
            agent_name=agent_name,
            max_retry=max_retry,
        ),
    )
