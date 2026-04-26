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

SYSTEM_INSTRUCTIONS = """You are a voice assistant for CodeTether, an Agent-to-Agent (A2A) platform for AI agent collaboration.

## About CodeTether / A2A Protocol
CodeTether implements the A2A (Agent-to-Agent) protocol — an open standard for AI agents to communicate, delegate tasks, and collaborate. Key concepts:
- **A2A Messages**: Structured messages with parts (text, data, files) sent between agents via `message/send`
- **A2A Tasks**: Every message creates a task that goes through a lifecycle: pending → working → completed/failed/cancelled
- **Artifacts**: Task results are returned as artifacts containing text, data, or file parts
- **Workers**: Rust-based codetether-agent processes that connect via SSE and autonomously execute tasks using AI models
- **Agent Discovery**: Agents register themselves and can discover each other in the network
- **Model Routing**: Tasks can specify which AI model to use (Claude, Gemini, GPT, etc.) and which worker personality to target
- **Codebases**: Registered project directories that workers operate on

## Your Role
You are the voice interface to the CodeTether A2A network. You are a registered agent yourself ("codetether-voice-agent"). Users talk to you to:
1. Send A2A messages that create tasks for worker agents to process
2. Delegate work to specific agents by name with model preferences
3. Check A2A task status and retrieve artifacts (results)
4. Discover what agents are online and what they can do
5. Monitor system activity across all agents
6. Manage codebases and target work to specific projects

## Available Tools

### A2A Protocol (Primary)
- **a2a_send_message**: Send a message via the A2A protocol. Creates a task, routes to a worker, returns the task with status and artifacts. Use this for general questions/work.
- **a2a_send_to_agent**: Send a message to a specific named agent. The task queues until that agent claims it. Use discover_agents first to find agent names.
- **a2a_get_task**: Get the current status and artifacts of an A2A task. Use to check if a task completed and read its results.
- **a2a_cancel_task**: Cancel an in-progress A2A task.

### Task Management (Queue-based)
- **create_task**: Queue a new coding task with title, description, priority, and model selection. Tasks are claimed by workers via SSE.
- **list_tasks**: See all tasks. Filter by status (pending, working, completed, failed, cancelled).
- **get_task**: Get detailed info about a specific task by its ID.
- **cancel_task**: Stop a pending or in-progress task.

### Agent Discovery & Communication
- **discover_agents**: Find what agents are registered and online in the A2A network.
- **send_message**: Send a direct message to a registered agent.

### Model Selection
When creating tasks or sending A2A messages, you can specify:
- **model**: Friendly names like "claude-sonnet", "gemini", "gpt-4", "minimax"
- **model_ref**: Precise identifiers like "anthropic:claude-3.5-sonnet", "openai:gpt-4.1"
- **worker_personality**: Target specific worker profiles like "reviewer", "builder"

### Codebase Management
- **list_codebases**: See all registered project codebases.
- **get_current_codebase**: Get the currently active codebase context.

### Monitoring & History
- **get_monitor_messages**: See recent activity from all agents in the monitoring system.
- **get_conversation_history**: Get the message history for a specific conversation thread.
- **get_task_updates**: Poll for recent task status changes since a timestamp.

## A2A Task Lifecycle
1. User asks you to do something → you call `a2a_send_message` or `a2a_send_to_agent`
2. A task is created (status: pending)
3. A worker agent claims the task (status: working)
4. Worker processes and returns artifacts (status: completed)
5. You read the artifacts and relay the results to the user

## Guidelines
- Speak naturally and concisely for voice interaction
- Use `a2a_send_message` as the primary way to delegate work — it's the A2A protocol way
- Use `a2a_send_to_agent` when the user wants a specific agent to handle something
- Use `create_task` for simpler queue-based task creation without A2A messaging
- Offer model selection when users have complex tasks ("Would you like me to use Claude, Gemini, or GPT for this?")
- When showing task results, extract and read the artifact text
- Confirm task creation before proceeding
- Proactively check task status if a task was recently created"""


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

    Includes A2A protocol tools (message/send, tasks/get, etc.), task queue tools,
    agent discovery, model selection, codebase management, and monitoring.

    Args:
        mcp_client: The CodeTether MCP client for tool execution.

    Returns:
        List of FunctionTool objects.
    """
    global _current_room
    tools = []

    # ─── A2A Protocol Tools ──────────────────────────────────────────

    @llm.function_tool(
        name='a2a_send_message',
        description='Send a message via the A2A protocol. Creates a task that a worker agent processes and returns artifacts with results. This is the primary way to delegate work.',
    )
    async def a2a_send_message(
        message: str,
        model: Optional[str] = None,
        model_ref: Optional[str] = None,
    ) -> str:
        """Send an A2A protocol message."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'a2a_send_message', 'args': {'message': message[:100], 'model': model}},
        )
        try:
            logger.info(f'A2A message/send: {message[:80]}...')
            config = {}
            if model:
                config['model'] = model
            if model_ref:
                config['model_ref'] = model_ref

            task = await mcp_client.a2a_send_message(
                text=message,
                configuration=config if config else None,
            )
            result_text = task.result_text
            if result_text:
                result = f'Task {task.id} completed ({task.status}). Result: {result_text[:500]}'
            else:
                result = f'Task {task.id} created (status: {task.status}). Use a2a_get_task to check for results.'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'a2a_send_message', 'result': result[:300], 'success': True},
            )
            return result
        except Exception as e:
            logger.error(f'a2a_send_message failed: {e}')
            error_result = f'A2A message failed: {str(e)}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'a2a_send_message', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(a2a_send_message)

    @llm.function_tool(
        name='a2a_send_to_agent',
        description='Send a message to a specific named agent via A2A protocol. The task queues until that agent claims it. Use discover_agents first to find names.',
    )
    async def a2a_send_to_agent(
        agent_name: str,
        message: str,
        model: Optional[str] = None,
        model_ref: Optional[str] = None,
        deadline_seconds: Optional[int] = None,
    ) -> str:
        """Send a message to a specific agent."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'a2a_send_to_agent', 'args': {'agent_name': agent_name, 'message': message[:80]}},
        )
        try:
            logger.info(f'A2A send_to_agent: {agent_name}')
            result = await mcp_client.send_to_agent(
                agent_name=agent_name,
                message=message,
                model=model,
                model_ref=model_ref,
                deadline_seconds=deadline_seconds,
            )
            task_id = result.get('task_id', 'unknown')
            status = result.get('status', 'pending')
            response = f'Message sent to {agent_name}. Task {task_id} (status: {status}).'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'a2a_send_to_agent', 'result': response, 'success': True},
            )
            return response
        except Exception as e:
            logger.error(f'a2a_send_to_agent failed: {e}')
            error_result = f'Failed to send to {agent_name}: {str(e)}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'a2a_send_to_agent', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(a2a_send_to_agent)

    @llm.function_tool(
        name='a2a_get_task',
        description='Get the status and artifacts of an A2A task. Use after a2a_send_message to check if the task completed and read results.',
    )
    async def a2a_get_task(task_id: str) -> str:
        """Get an A2A task status and artifacts."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'a2a_get_task', 'args': {'task_id': task_id}},
        )
        try:
            logger.info(f'A2A tasks/get: {task_id}')
            task = await mcp_client.a2a_get_task(task_id, history_length=5)
            if not task:
                result = f'A2A task {task_id} not found.'
            else:
                result = f'Task {task.id}: status={task.status}'
                artifact_text = task.result_text
                if artifact_text:
                    result += f'. Artifacts: {artifact_text[:500]}'
                if task.history:
                    result += f'. History: {len(task.history)} entries.'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'a2a_get_task', 'result': result[:300], 'success': True},
            )
            return result
        except Exception as e:
            logger.error(f'a2a_get_task failed: {e}')
            error_result = f'Failed to get A2A task: {str(e)}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'a2a_get_task', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(a2a_get_task)

    @llm.function_tool(
        name='a2a_cancel_task',
        description='Cancel an in-progress A2A task.',
    )
    async def a2a_cancel_task(task_id: str) -> str:
        """Cancel an A2A task."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'a2a_cancel_task', 'args': {'task_id': task_id}},
        )
        try:
            logger.info(f'A2A tasks/cancel: {task_id}')
            task = await mcp_client.a2a_cancel_task(task_id)
            result = f'Task {task.id} cancelled (status: {task.status}).'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'a2a_cancel_task', 'result': result, 'success': True},
            )
            return result
        except Exception as e:
            logger.error(f'a2a_cancel_task failed: {e}')
            error_result = f'Failed to cancel A2A task: {str(e)}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'a2a_cancel_task', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(a2a_cancel_task)

    # ─── Task Queue Tools ────────────────────────────────────────────

    @llm.function_tool(
        name='create_task',
        description='Create a task in the queue with model selection. Workers claim pending tasks via SSE.',
    )
    async def create_task(
        title: str,
        description: str = '',
        priority: int = 0,
        model: Optional[str] = None,
        model_ref: Optional[str] = None,
    ) -> str:
        """Create a new task with model routing."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'create_task', 'args': {'title': title, 'model': model}},
        )
        try:
            logger.info(f'create_task: {title} (model={model})')
            arguments: Dict[str, Any] = {
                'title': title,
                'description': description,
                'codebase_id': 'global',
                'agent_type': 'build',
                'priority': priority,
            }
            if model:
                arguments['model'] = model
            if model_ref:
                arguments['model_ref'] = model_ref

            raw_result = await mcp_client.call_tool('create_task', arguments)
            task_id = raw_result.get('task_id', raw_result.get('id', ''))
            status = raw_result.get('status', 'pending')
            result = f"Created task '{title}' (ID: {task_id}, status: {status})"
            if model:
                result += f' with model {model}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'create_task', 'result': result, 'success': True},
            )
            return result
        except Exception as e:
            logger.error(f'create_task failed: {e}')
            error_result = f'Error creating task: {str(e)}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'create_task', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(create_task)

    # List tasks tool
    @llm.function_tool(
        name='list_tasks',
        description='List tasks in the queue. Filter by status (pending, working, completed, failed, cancelled).',
    )
    async def list_tasks(status: Optional[str] = None) -> str:
        """List tasks with optional status filter."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'list_tasks', 'args': {'status': status}},
        )
        try:
            logger.info(f'list_tasks (status={status})')
            tasks = await mcp_client.list_tasks(status=status)
            if not tasks:
                result = 'No tasks found.' + (f' (filtered by {status})' if status else '')
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
            error_result = f'Error listing tasks: {str(e)}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'list_tasks', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(list_tasks)

    # Get task tool
    @llm.function_tool(
        name='get_task',
        description='Get details about a specific task by ID (from the task queue).',
    )
    async def get_task(task_id: str) -> str:
        """Get task details."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'get_task', 'args': {'task_id': task_id}},
        )
        try:
            logger.info(f'get_task: {task_id}')
            task = await mcp_client.get_task(task_id)
            if task:
                result = f"Task '{task.title}': status={task.status}, priority={task.priority}"
                if task.result:
                    result += f'. Has result data.'
                if task.error:
                    result += f'. Error: {task.error}'
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
            error_result = f'Error getting task: {str(e)}'
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
        description='Cancel a running or pending task from the queue.',
    )
    async def cancel_task(task_id: str) -> str:
        """Cancel a task."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'cancel_task', 'args': {'task_id': task_id}},
        )
        try:
            logger.info(f'cancel_task: {task_id}')
            success = await mcp_client.cancel_task(task_id)
            result = 'Task cancelled.' if success else 'Could not cancel the task.'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'cancel_task', 'result': result, 'success': success},
            )
            return result
        except Exception as e:
            logger.error(f'cancel_task failed: {e}')
            error_result = f'Error cancelling task: {str(e)}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'cancel_task', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(cancel_task)

    # ─── Agent Discovery & Communication ─────────────────────────────

    @llm.function_tool(
        name='discover_agents',
        description='Find what agents are registered and online in the A2A network.',
    )
    async def discover_agents() -> str:
        """Discover available agents."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'discover_agents', 'args': {}},
        )
        try:
            logger.info('discover_agents')
            agents = await mcp_client.discover_agents()
            if not agents:
                result = 'No agents are currently online in the A2A network.'
            else:
                agent_info = []
                for a in agents[:8]:
                    info = a.name
                    if a.description:
                        info += f' - {a.description[:60]}'
                    agent_info.append(info)
                result = f'Found {len(agents)} agents: ' + '; '.join(agent_info)
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'discover_agents', 'result': result[:300], 'success': True},
            )
            return result
        except Exception as e:
            logger.error(f'discover_agents failed: {e}')
            error_result = f'Error discovering agents: {str(e)}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'discover_agents', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(discover_agents)

    @llm.function_tool(
        name='send_message',
        description='Send a direct message to a registered agent.',
    )
    async def send_message(agent_name: str, message: str) -> str:
        """Send a message to an agent."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'send_message', 'args': {'agent_name': agent_name}},
        )
        try:
            logger.info(f'send_message to {agent_name}')
            result = await mcp_client.send_message(
                agent_name=agent_name, message=message
            )
            if isinstance(result, dict):
                task_id = result.get('task_id', '')
                response_text = result.get('response', result.get('message', ''))
                if response_text:
                    response = f'Response from {agent_name}: {str(response_text)[:300]}'
                elif task_id:
                    response = f'Message queued for {agent_name}. Task ID: {task_id}'
                else:
                    response = f'Message sent to {agent_name}.'
            else:
                response = f'Sent to {agent_name}: {str(result)[:200]}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'send_message', 'result': response[:300], 'success': True},
            )
            return response
        except Exception as e:
            logger.error(f'send_message failed: {e}')
            error_result = f'Error sending message: {str(e)}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'send_message', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(send_message)

    # ─── Codebase Tools ──────────────────────────────────────────────

    @llm.function_tool(
        name='list_codebases',
        description='List all registered project codebases that workers operate on.',
    )
    async def list_codebases() -> str:
        """List codebases."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'list_codebases', 'args': {}},
        )
        try:
            logger.info('list_codebases')
            codebases = await mcp_client.list_codebases()
            if not codebases:
                result = 'No codebases registered.'
            else:
                cb_info = [f'{cb.name} (ID: {cb.id})' for cb in codebases[:10]]
                result = f'Found {len(codebases)} codebases: ' + ', '.join(cb_info)
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'list_codebases', 'result': result, 'success': True},
            )
            return result
        except Exception as e:
            logger.error(f'list_codebases failed: {e}')
            error_result = f'Error listing codebases: {str(e)}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'list_codebases', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(list_codebases)

    @llm.function_tool(
        name='get_current_codebase',
        description='Get the currently active codebase context.',
    )
    async def get_current_codebase() -> str:
        """Get current codebase."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'get_current_codebase', 'args': {}},
        )
        try:
            logger.info('get_current_codebase')
            cb = await mcp_client.get_current_codebase()
            if cb:
                result = f'Active codebase: {cb.name} (ID: {cb.id}, path: {cb.path})'
            else:
                result = 'No active codebase set. Using global context.'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'get_current_codebase', 'result': result, 'success': True},
            )
            return result
        except Exception as e:
            logger.error(f'get_current_codebase failed: {e}')
            error_result = f'Error getting codebase: {str(e)}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'get_current_codebase', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(get_current_codebase)

    # ─── Monitoring & History ────────────────────────────────────────

    @llm.function_tool(
        name='get_monitor_messages',
        description='Get recent activity from all agents in the monitoring system.',
    )
    async def get_monitor_messages(limit: int = 20) -> str:
        """Get recent monitoring messages."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'get_monitor_messages', 'args': {'limit': limit}},
        )
        try:
            logger.info(f'get_monitor_messages (limit={limit})')
            messages = await mcp_client.get_monitor_messages(limit=limit)
            if not messages:
                result = 'No recent activity in the monitoring system.'
            else:
                msg_summaries = []
                for msg in messages[:5]:
                    agent = msg.get('agent_name', 'unknown')
                    content = msg.get('content', '')[:80]
                    msg_summaries.append(f'{agent}: {content}')
                result = (
                    f'Found {len(messages)} recent messages. '
                    + '; '.join(msg_summaries)
                )
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'get_monitor_messages', 'result': result[:300], 'success': True},
            )
            return result
        except Exception as e:
            logger.error(f'get_monitor_messages failed: {e}')
            error_result = f'Error getting messages: {str(e)}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'get_monitor_messages', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(get_monitor_messages)

    @llm.function_tool(
        name='get_conversation_history',
        description='Get message history for a specific conversation thread by ID.',
    )
    async def get_conversation_history(conversation_id: str) -> str:
        """Get conversation history by ID."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'get_conversation_history', 'args': {'conversation_id': conversation_id}},
        )
        try:
            logger.info(f'get_conversation_history: {conversation_id}')
            messages = await mcp_client.get_session_messages(conversation_id)
            if not messages:
                result = f"No messages for conversation '{conversation_id}'."
            else:
                msg_count = len(messages)
                user_count = sum(1 for m in messages if m.role == 'user')
                result = f'{msg_count} messages ({user_count} from users). '
                if msg_count <= 3:
                    for m in messages:
                        result += f'{m.role}: {m.content[:60]}... '
                else:
                    result += f'Latest: {messages[-1].role}: {messages[-1].content[:100]}...'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'get_conversation_history', 'result': result[:300], 'success': True},
            )
            return result
        except Exception as e:
            logger.error(f'get_conversation_history failed: {e}')
            error_result = f'Error getting conversation: {str(e)}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'get_conversation_history', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(get_conversation_history)

    @llm.function_tool(
        name='get_task_updates',
        description='Poll for recent task status changes. Optionally filter by timestamp or specific task IDs.',
    )
    async def get_task_updates(
        since_timestamp: Optional[str] = None,
    ) -> str:
        """Get recent task updates."""
        await publish_state(
            _current_room,
            'tool_calling',
            {'tool_name': 'get_task_updates', 'args': {'since': since_timestamp}},
        )
        try:
            logger.info(f'get_task_updates (since={since_timestamp})')
            updates = await mcp_client.get_task_updates(
                since_timestamp=since_timestamp
            )
            if not updates:
                result = 'No recent task updates.'
            else:
                update_info = []
                for u in updates[:5]:
                    title = u.get('title', u.get('id', 'unknown'))
                    status = u.get('status', '?')
                    update_info.append(f'{title}: {status}')
                result = f'{len(updates)} task updates: ' + ', '.join(update_info)
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'get_task_updates', 'result': result[:300], 'success': True},
            )
            return result
        except Exception as e:
            logger.error(f'get_task_updates failed: {e}')
            error_result = f'Error getting updates: {str(e)}'
            await publish_state(
                _current_room,
                'tool_complete',
                {'tool_name': 'get_task_updates', 'error': str(e), 'success': False},
            )
            return error_result

    tools.append(get_task_updates)

    logger.info(f'Created {len(tools)} A2A protocol tools for voice agent')
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

        # Register as an A2A agent in the network
        agent_name = os.getenv('VOICE_AGENT_NAME', 'codetether-voice-agent')
        try:
            await mcp_client.register_agent(
                name=agent_name,
                description='Voice-enabled AI agent using Gemini Live API. Provides a natural language voice interface to the CodeTether A2A network.',
                url=api_url,
                capabilities={'streaming': True, 'push_notifications': False},
                models_supported=['google:gemini-live-2.5-flash-native-audio'],
            )
            logger.info(f'Registered as A2A agent: {agent_name}')
            await publish_state(
                _current_room, 'initializing', {'step': 'a2a_registered', 'agent_name': agent_name}
            )
        except Exception as e:
            logger.warning(f'A2A agent registration failed (non-fatal): {e}')

        # Start heartbeat task to keep agent visible in discovery
        async def _heartbeat_loop():
            while True:
                await asyncio.sleep(45)
                try:
                    await mcp_client.refresh_heartbeat(agent_name)
                    logger.debug(f'Heartbeat refreshed for {agent_name}')
                except Exception as e:
                    logger.warning(f'Heartbeat failed: {e}')

        heartbeat_task = asyncio.create_task(_heartbeat_loop())

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

    health_port = int(os.getenv('VOICE_WORKER_HEALTH_PORT', '0'))

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            initialize_process_timeout=init_timeout,
            shutdown_process_timeout=shutdown_timeout,
            agent_name=agent_name,
            max_retry=max_retry,
            port=health_port,
        ),
    )
