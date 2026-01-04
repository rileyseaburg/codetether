"""CodeTether MCP Client Module.

This module provides an async client to interact with CodeTether's MCP (Model Context Protocol)
tools and APIs.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class MCPError(Exception):
    """Exception raised for MCP-specific errors."""

    def __init__(
        self,
        message: str,
        code: Optional[int] = None,
        data: Optional[Any] = None,
    ):
        self.message = message
        self.code = code
        self.data = data
        super().__init__(self.message)


@dataclass
class Task:
    """Represents a CodeTether task."""

    id: str
    title: str
    description: str = ''
    status: str = 'pending'
    codebase_id: str = 'global'
    agent_type: str = 'build'
    priority: int = 0
    created_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class Agent:
    """Represents a CodeTether agent."""

    name: str
    description: str = ''
    url: str = ''


@dataclass
class Message:
    """Represents a message in a session."""

    role: str
    content: str
    timestamp: Optional[str] = None


class CodeTetherMCP:
    """Async client for CodeTether MCP tools and APIs.

    Args:
        api_url: The base URL for the CodeTether API.
    """

    def __init__(self, api_url: str):
        self.api_url = api_url.rstrip('/')
        self.mcp_url = f'{self.api_url}/mcp'
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp client session.

        Returns:
            The aiohttp ClientSession instance.
        """
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call an MCP tool with the given name and arguments.

        Args:
            tool_name: The name of the tool to call.
            arguments: The arguments to pass to the tool.

        Returns:
            The result from the tool call.

        Raises:
            MCPError: If the tool call fails.
        """
        session = await self._get_session()
        request_id = str(uuid.uuid4())

        payload = {
            'jsonrpc': '2.0',
            'id': request_id,
            'method': 'tools/call',
            'params': {'name': tool_name, 'arguments': arguments},
        }

        logger.info(
            f'Calling MCP tool: {tool_name} with request_id: {request_id}'
        )

        try:
            async with session.post(
                self.mcp_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(
                        f'MCP tool call failed with status {response.status}: {error_text}'
                    )
                    raise MCPError(f'HTTP {response.status}: {error_text}')

                result = await response.json()

                if 'error' in result and result['error'] is not None:
                    error = result['error']
                    logger.error(f'MCP tool call error: {error}')
                    raise MCPError(
                        message=error.get('message', 'Unknown error'),
                        code=error.get('code'),
                        data=error.get('data'),
                    )

                if 'result' not in result:
                    logger.error(f'MCP tool call returned no result: {result}')
                    raise MCPError('MCP tool call returned no result')

                logger.info(f'MCP tool {tool_name} completed successfully')
                return result['result']

        except aiohttp.ClientError as e:
            logger.error(f'Network error calling MCP tool {tool_name}: {e}')
            raise MCPError(f'Network error: {str(e)}')

    async def create_task(
        self,
        title: str,
        description: str = '',
        codebase_id: str = 'global',
        agent_type: str = 'build',
        priority: int = 0,
    ) -> Task:
        """Create a new task.

        Args:
            title: The title of the task.
            description: The description of the task.
            codebase_id: The codebase ID to associate with the task.
            agent_type: The type of agent to use.
            priority: The priority of the task (0-10).

        Returns:
            The created Task object.
        """
        arguments = {
            'title': title,
            'description': description,
            'codebase_id': codebase_id,
            'agent_type': agent_type,
            'priority': priority,
        }

        result = await self.call_tool('create_task', arguments)

        return Task(
            id=result.get('id', ''),
            title=result.get('title', title),
            description=result.get('description', description),
            status=result.get('status', 'pending'),
            codebase_id=result.get('codebase_id', codebase_id),
            agent_type=result.get('agent_type', agent_type),
            priority=result.get('priority', priority),
            created_at=result.get('created_at'),
            result=result.get('result'),
            error=result.get('error'),
        )

    async def list_tasks(
        self, status: Optional[str] = None, codebase_id: Optional[str] = None
    ) -> List[Task]:
        """List tasks with optional filtering.

        Args:
            status: Filter tasks by status.
            codebase_id: Filter tasks by codebase ID.

        Returns:
            A list of Task objects.
        """
        arguments: Dict[str, Any] = {}
        if status is not None:
            arguments['status'] = status
        if codebase_id is not None:
            arguments['codebase_id'] = codebase_id

        result = await self.call_tool('list_tasks', arguments)

        tasks = []
        for task_data in result.get('tasks', []):
            tasks.append(
                Task(
                    id=task_data.get('id', ''),
                    title=task_data.get('title', ''),
                    description=task_data.get('description', ''),
                    status=task_data.get('status', 'pending'),
                    codebase_id=task_data.get('codebase_id', 'global'),
                    agent_type=task_data.get('agent_type', 'build'),
                    priority=task_data.get('priority', 0),
                    created_at=task_data.get('created_at'),
                    result=task_data.get('result'),
                    error=task_data.get('error'),
                )
            )

        return tasks

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID.

        Args:
            task_id: The ID of the task to retrieve.

        Returns:
            The Task object if found, None otherwise.
        """
        result = await self.call_tool('get_task', {'task_id': task_id})

        if not result:
            return None

        return Task(
            id=result.get('id', ''),
            title=result.get('title', ''),
            description=result.get('description', ''),
            status=result.get('status', 'pending'),
            codebase_id=result.get('codebase_id', 'global'),
            agent_type=result.get('agent_type', 'build'),
            priority=result.get('priority', 0),
            created_at=result.get('created_at'),
            result=result.get('result'),
            error=result.get('error'),
        )

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task.

        Args:
            task_id: The ID of the task to cancel.

        Returns:
            True if the task was cancelled, False otherwise.
        """
        result = await self.call_tool('cancel_task', {'task_id': task_id})
        return result.get('success', False)

    async def get_session_messages(self, session_id: str) -> List[Message]:
        """Get messages from a session.

        Args:
            session_id: The ID of the session.

        Returns:
            A list of Message objects.
        """
        result = await self.call_tool('get_session', {'session_id': session_id})

        messages = []
        for msg_data in result.get('messages', []):
            messages.append(
                Message(
                    role=msg_data.get('role', ''),
                    content=msg_data.get('content', ''),
                    timestamp=msg_data.get('timestamp'),
                )
            )

        return messages

    async def discover_agents(self) -> List[Agent]:
        """Discover available agents.

        Returns:
            A list of Agent objects.
        """
        result = await self.call_tool('discover_agents', {})

        agents = []
        for agent_data in result.get('agents', []):
            agents.append(
                Agent(
                    name=agent_data.get('name', ''),
                    description=agent_data.get('description', ''),
                    url=agent_data.get('url', ''),
                )
            )

        return agents

    async def send_message(
        self, agent_name: str, message: str
    ) -> Dict[str, Any]:
        """Send a message to an agent.

        Args:
            agent_name: The name of the agent to send the message to.
            message: The message content.

        Returns:
            The response from the agent.
        """
        result = await self.call_tool(
            'send_message', {'agent_name': agent_name, 'message': message}
        )
        return result
