"""Session playback module for voice-based replay of historical conversations.

This module provides functionality to playback historical sessions via voice,
either verbatim or as a summary. It handles message formatting, role-based
prefixes, and interruption handling for natural conversation flow.
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from codetether_voice_agent.mcp_client import CodeTetherMCP

logger = logging.getLogger(__name__)


class SessionPlayback:
    """Handles voice playback of historical conversation sessions.

    Provides methods to replay sessions either verbatim (reading each message)
    or as a summary, with support for natural interruption handling.
    """

    def __init__(self, mcp_client: 'CodeTetherMCP') -> None:
        """Initialize the session playback handler.

        Args:
            mcp_client: The MCP client instance for session operations.
        """
        self.mcp_client = mcp_client
        self._interrupted = False
        self._playback_task: Optional[asyncio.Task] = None

    async def start(
        self, session: Any, session_id: str, style: str = 'verbatim'
    ) -> None:
        """Start playback of a historical session.

        Main entry point for playing back sessions. Loads session messages
        from the MCP client and routes to the appropriate playback method.

        Args:
            session: The session object to use for voice output.
            session_id: The unique identifier of the session to playback.
            style: Playback style - "verbatim" or "summary". Defaults to "verbatim".

        Raises:
            ValueError: If an invalid playback style is specified.
        """
        self._interrupted = False
        logger.info(f'Starting {style} playback for session: {session_id}')

        try:
            messages = await self._load_session_messages(session_id)

            if not messages:
                await session.generate_reply(
                    instructions='This session has no messages to playback.'
                )
                return

            if style == 'verbatim':
                await self.playback_verbatim(session, messages)
            elif style == 'summary':
                await self.playback_summary(session, messages)
            else:
                raise ValueError(
                    f"Invalid playback style: {style}. Must be 'verbatim' or 'summary'"
                )

        except Exception as e:
            logger.error(f'Error during session playback: {e}')
            await session.generate_reply(
                instructions='I encountered an error while trying to playback the session.'
            )

    async def playback_verbatim(
        self, session: Any, messages: List[Dict]
    ) -> None:
        """Play back messages verbatim with role prefixes.

        Reads each message aloud exactly as it was written, prefixed with
        "You said:" for user messages or "The agent responded:" for agent messages.
        Includes brief pauses between messages for natural pacing.

        Args:
            session: The session object for voice output.
            messages: List of message dictionaries to playback.
        """
        logger.info(f'Starting verbatim playback of {len(messages)} messages')

        for idx, message in enumerate(messages):
            if self._interrupted:
                logger.debug('Playback interrupted during verbatim mode')
                break

            role = message.get('role', 'unknown')
            content = message.get('content', '')

            if not content:
                continue

            prefix = self._get_role_prefix(role)
            text_to_read = f'{prefix} {content}'

            try:
                await session.generate_reply(
                    instructions=f'Read this aloud exactly: {text_to_read}'
                )
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.warning(f'Error reading message {idx}: {e}')
                continue

        if not self._interrupted:
            await session.generate_reply(
                instructions='That concludes the playback of this session.'
            )

    async def playback_summary(
        self, session: Any, messages: List[Dict]
    ) -> None:
        """Play back messages as a natural summary.

        Creates a coherent summary of all messages and reads it aloud
        in a conversational manner, rather than reading each message verbatim.

        Args:
            session: The session object for voice output.
            messages: List of message dictionaries to summarize.
        """
        logger.info(f'Starting summary playback of {len(messages)} messages')

        formatted_text = self._format_messages_for_summary(messages)

        summary_prompt = (
            'Summarize the following conversation in a natural, conversational way. '
            "Present it as if you're recounting what happened in the conversation. "
            'Keep it concise but include the key points and exchanges. '
            f'Here is the conversation:\n\n{formatted_text}'
        )

        try:
            await session.generate_reply(instructions=summary_prompt)
        except Exception as e:
            logger.error(f'Error generating summary: {e}')
            await session.generate_reply(
                instructions='I was unable to generate a summary of this session.'
            )

    def _format_messages_for_summary(self, messages: List[Dict]) -> str:
        """Format messages into a readable string for summarization.

        Creates a clean, linear representation of the conversation for
        the LLM to summarize effectively.

        Args:
            messages: List of message dictionaries.

        Returns:
            A formatted string representation of the conversation.
        """
        formatted_parts = []

        for message in messages:
            role = message.get('role', 'unknown')
            content = message.get('content', '')

            if not content:
                continue

            prefix = self._get_role_prefix(role)
            formatted_parts.append(f'{prefix}\n{content}\n')

        return '\n'.join(formatted_parts)

    def _get_role_prefix(self, role: str) -> str:
        """Get the appropriate role prefix for voice playback.

        Args:
            role: The role identifier from the message.

        Returns:
            A human-readable prefix for the role.
        """
        role_prefix_map = {
            'user': 'You said:',
            'assistant': 'The agent responded:',
            'agent': 'The agent responded:',
            'system': 'System note:',
        }

        return role_prefix_map.get(role, f'{role.capitalize()}:')

    def interrupt(self) -> None:
        """Signal that playback has been interrupted.

        Sets the interrupted flag to pause or stop current playback.
        Call this method when user interruption is detected.
        """
        self._interrupted = True
        logger.info('Session playback interruption requested')

    def resume(self) -> None:
        """Resume playback after interruption.

        Resets the interrupted flag to allow playback to continue.
        Note: This only resets the flag; actual resuming must be
        handled by the calling code.
        """
        self._interrupted = False
        logger.info('Session playback interruption cleared')

    def is_interrupted(self) -> bool:
        """Check if playback is currently interrupted.

        Returns:
            True if playback is interrupted, False otherwise.
        """
        return self._interrupted

    async def _load_session_messages(self, session_id: str) -> List[Dict]:
        """Load messages for a session from the MCP client.

        Args:
            session_id: The unique identifier of the session.

        Returns:
            List of message dictionaries for the session.
        """
        try:
            if hasattr(self.mcp_client, 'get_session_messages'):
                messages = await self.mcp_client.get_session_messages(
                    session_id
                )
                return messages if messages else []
            else:
                logger.warning(
                    'MCP client does not have get_session_messages method'
                )
                return []

        except Exception as e:
            logger.error(f'Failed to load session messages: {e}')
            return []
