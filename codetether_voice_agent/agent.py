"""LiveKit Voice Agent with Gemini 3 Live API and CodeTether MCP Integration.

This module provides a voice-enabled AI agent that uses Google's Gemini 3 Live API
for real-time voice conversation and integrates with CodeTether MCP tools for
task management and agent communication.
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from livekit.agents import (
    AgentSession,
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
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


async def register_tools(
    session: AgentSession,
    function_caller: FunctionGemmaCaller,
    mcp_client: CodeTetherMCP,
) -> None:
    """Register all available tools with the agent session.

    Args:
        session: The agent session to register tools with.
        function_caller: The FunctionGemma caller for intent parsing.
        mcp_client: The CodeTether MCP client for tool execution.
    """
    try:
        tools = function_caller.CODETER_TOOLS

        for tool in tools:
            tool_name = tool.get('name')
            tool_description = tool.get('description', '')
            parameters = tool.get('parameters', {})

            async def tool_handler(
                tool_name: str = tool_name,
                arguments: Optional[Dict[str, Any]] = None,
            ) -> str:
                if arguments is None:
                    arguments = {}

                try:
                    result = await mcp_client.call_tool(tool_name, arguments)
                    return json.dumps(result)
                except Exception as e:
                    logger.error(f'Tool {tool_name} failed: {e}')
                    return json.dumps({'error': str(e)})

            session.register_tool(
                tool_name, tool_description, parameters, tool_handler
            )
            logger.debug(f'Registered tool: {tool_name}')

        logger.info(f'Registered {len(tools)} tools with agent session')

    except Exception as e:
        logger.error(f'Failed to register tools: {e}')
        raise


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

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    participant = await ctx.wait_for_participant()

    try:
        api_url = os.getenv('CODETETHER_API_URL', 'http://localhost:8000')
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

        gemini_model = google.realtime.RealtimeModel(
            model='gemini-2.0-flash-exp',
            voice=voice_name,
            instructions=full_instructions,
        )

        session = AgentSession(
            model=gemini_model,
        )

        await register_tools(session, function_caller, mcp_client)
        logger.info('Tools registered successfully')

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
        await session.start(room=ctx.room, participant=participant)

    except Exception as e:
        logger.error(f'Error in voice agent entrypoint: {e}')
        raise


if __name__ == '__main__':
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        ),
    )
