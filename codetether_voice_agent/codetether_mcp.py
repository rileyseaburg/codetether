"""CodeTether MCP & A2A Protocol Client Module.

This module provides an async client to interact with CodeTether's MCP (Model Context Protocol)
tools and A2A (Agent-to-Agent) protocol endpoints.

A2A Protocol support:
  - message/send & message/stream via JSON-RPC at /a2a/jsonrpc
  - tasks/get, tasks/cancel
  - Agent self-registration & heartbeat
  - Model routing (model_ref, worker_personality)
  - Codebase awareness (list_codebases, get_current_codebase)
"""

import asyncio
import json
import logging
import os
import time
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


@dataclass
class A2AMessagePart:
    """A part of an A2A protocol message (text, data, or file)."""

    type: str = 'text'
    text: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class A2ATask:
    """Represents an A2A protocol task with full lifecycle."""

    id: str
    status: str = 'pending'
    context_id: Optional[str] = None
    artifacts: Optional[List[Dict[str, Any]]] = None
    history: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None

    @property
    def is_terminal(self) -> bool:
        return self.status in ('completed', 'failed', 'cancelled')

    @property
    def result_text(self) -> str:
        """Extract text from artifacts."""
        if not self.artifacts:
            return ''
        texts = []
        for artifact in self.artifacts:
            for part in artifact.get('parts', []):
                if part.get('type') == 'text':
                    texts.append(part.get('text', ''))
        return '\n'.join(texts)


@dataclass
class Codebase:
    """Represents a registered codebase."""

    id: str
    name: str
    path: str = ''
    status: str = 'active'
    worker_id: Optional[str] = None


class CodeTetherMCP:
    """Async client for CodeTether MCP tools and A2A protocol.

    Supports both MCP tool calls (/mcp) and A2A protocol methods (/a2a/jsonrpc).
    Authenticates via Keycloak client credentials (OAuth2) when
    KEYCLOAK_CLIENT_ID, KEYCLOAK_CLIENT_SECRET, and KEYCLOAK_TOKEN_URL
    are set.

    Args:
        api_url: The base URL for the CodeTether API.
    """

    def __init__(self, api_url: str):
        self.api_url = api_url.rstrip('/')
        self.mcp_url = f'{self.api_url}/mcp'
        self.a2a_url = f'{self.api_url}/a2a/jsonrpc'
        self._session: Optional[aiohttp.ClientSession] = None

        # OAuth2 client credentials
        self._client_id = os.environ.get('KEYCLOAK_CLIENT_ID', '')
        self._client_secret = os.environ.get('KEYCLOAK_CLIENT_SECRET', '')
        self._token_url = os.environ.get('KEYCLOAK_TOKEN_URL', '')
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

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

    async def _get_access_token(self) -> Optional[str]:
        """Get a valid OAuth2 access token, refreshing if needed."""
        if not self._client_id or not self._client_secret or not self._token_url:
            return None

        # Reuse token if still valid (with 30s buffer)
        if self._access_token and time.time() < self._token_expires_at - 30:
            return self._access_token

        session = await self._get_session()
        try:
            async with session.post(
                self._token_url,
                data={
                    'grant_type': 'client_credentials',
                    'client_id': self._client_id,
                    'client_secret': self._client_secret,
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
            ) as resp:
                if resp.status != 200:
                    logger.error(f'Failed to get OAuth token: HTTP {resp.status}')
                    return None
                token_data = await resp.json()
                self._access_token = token_data['access_token']
                self._token_expires_at = time.time() + token_data.get('expires_in', 300)
                logger.info('OAuth token acquired successfully')
                return self._access_token
        except Exception as e:
            logger.error(f'OAuth token request failed: {e}')
            return None

    @staticmethod
    def _unwrap_mcp_content(mcp_result: Dict[str, Any]) -> Dict[str, Any]:
        """Unwrap MCP content format to extract the inner JSON data.

        MCP tools/call returns: {"content": [{"type": "text", "text": "<json>"}]}
        This extracts and parses the JSON from the text content.

        Args:
            mcp_result: The raw MCP result with content array.

        Returns:
            The parsed inner JSON data as a dict.
        """
        if not isinstance(mcp_result, dict):
            return mcp_result

        content = mcp_result.get('content')
        if not content or not isinstance(content, list):
            # Already unwrapped or unexpected format — return as-is
            return mcp_result

        # Extract text from the first content item
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text':
                text = item.get('text', '')
                try:
                    return json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(
                        f'MCP content text is not valid JSON: {text[:200]}'
                    )
                    return {'raw_text': text}

        # No text content found — return as-is
        return mcp_result

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
            headers = {'Content-Type': 'application/json'}
            token = await self._get_access_token()
            if token:
                headers['Authorization'] = f'Bearer {token}'

            async with session.post(
                self.mcp_url,
                json=payload,
                headers=headers,
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

                # Unwrap MCP content format: {"content": [{"type": "text", "text": "<json>"}]}
                mcp_result = result['result']
                return self._unwrap_mcp_content(mcp_result)

        except aiohttp.ClientError as e:
            logger.error(f'Network error calling MCP tool {tool_name}: {e}')
            raise MCPError(f'Network error: {str(e)}')
        except asyncio.TimeoutError:
            logger.error(f'Timeout calling MCP tool {tool_name} (30s)')
            raise MCPError(f'Timeout calling tool {tool_name}')

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
            id=result.get('task_id', result.get('id', '')),
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
                    id=task_data.get('task_id', task_data.get('id', '')),
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
            id=result.get('task_id', result.get('id', '')),
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
        """Get messages from a session/conversation.

        This retrieves message history from the A2A server's monitoring system.
        The session_id is used as a conversation_id filter.

        Args:
            session_id: The ID of the session/conversation to retrieve.

        Returns:
            A list of Message objects.
        """
        # Use get_messages tool from A2A server with conversation_id filter
        result = await self.call_tool(
            'get_messages', {'conversation_id': session_id, 'limit': 100}
        )

        messages = []
        for msg_data in result.get('messages', []):
            # Map A2A server message format to our Message dataclass
            # A2A server has: id, timestamp, type (human/agent), agent_name, content, metadata
            msg_type = msg_data.get('type', 'unknown')
            role = 'user' if msg_type == 'human' else 'assistant'
            messages.append(
                Message(
                    role=role,
                    content=msg_data.get('content', ''),
                    timestamp=msg_data.get('timestamp'),
                )
            )

        return messages

    async def get_monitor_messages(
        self, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent messages from the A2A monitoring system.

        This retrieves all recent monitoring messages regardless of conversation.
        Useful for seeing overall system activity.

        Args:
            limit: Maximum number of messages to retrieve.

        Returns:
            A list of message dictionaries with full metadata.
        """
        result = await self.call_tool('get_messages', {'limit': limit})
        return result.get('messages', [])

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

        Uses the 'send_to_agent' MCP tool which routes messages to specific agents.

        Args:
            agent_name: The name of the agent to send the message to.
            message: The message content.

        Returns:
            The response from the agent.
        """
        result = await self.call_tool(
            'send_to_agent', {'agent_name': agent_name, 'message': message}
        )
        return result

    # =========================================================================
    # A2A Protocol Methods
    # =========================================================================

    async def _a2a_call(
        self, method: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call an A2A protocol method via JSON-RPC at /a2a/jsonrpc.

        Args:
            method: The A2A method (e.g. 'message/send', 'tasks/get').
            params: The method parameters.

        Returns:
            The result from the JSON-RPC response.

        Raises:
            MCPError: If the call fails.
        """
        session = await self._get_session()
        request_id = str(uuid.uuid4())

        payload = {
            'jsonrpc': '2.0',
            'id': request_id,
            'method': method,
            'params': params,
        }

        logger.info(f'A2A call: {method} (id: {request_id})')

        try:
            headers = {'Content-Type': 'application/json'}
            token = await self._get_access_token()
            if token:
                headers['Authorization'] = f'Bearer {token}'

            async with session.post(
                self.a2a_url, json=payload, headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f'A2A {method} failed: HTTP {response.status}: {error_text}')
                    raise MCPError(f'HTTP {response.status}: {error_text}')

                result = await response.json()

                if 'error' in result and result['error'] is not None:
                    error = result['error']
                    logger.error(f'A2A {method} error: {error}')
                    raise MCPError(
                        message=error.get('message', 'Unknown error'),
                        code=error.get('code'),
                        data=error.get('data'),
                    )

                logger.info(f'A2A {method} completed successfully')
                return result.get('result', {})

        except aiohttp.ClientError as e:
            logger.error(f'Network error in A2A {method}: {e}')
            raise MCPError(f'Network error: {str(e)}')
        except asyncio.TimeoutError:
            logger.error(f'Timeout in A2A {method} (30s)')
            raise MCPError(f'Timeout calling {method}')

    async def a2a_send_message(
        self,
        text: str,
        role: str = 'user',
        configuration: Optional[Dict[str, Any]] = None,
    ) -> A2ATask:
        """Send a message via the A2A protocol (message/send).

        This is the primary A2A protocol method. It sends a message and returns
        a task that tracks the response lifecycle.

        Args:
            text: The message text to send.
            role: The message role ('user' or 'assistant').
            configuration: Optional A2A configuration (model preferences, etc.).

        Returns:
            An A2ATask representing the response.
        """
        params: Dict[str, Any] = {
            'message': {
                'role': role,
                'parts': [{'type': 'text', 'text': text}],
            },
        }
        if configuration:
            params['configuration'] = configuration

        result = await self._a2a_call('message/send', params)
        task_data = result.get('task', {})

        return A2ATask(
            id=task_data.get('id', ''),
            status=task_data.get('status', {}).get('state', 'pending'),
            context_id=task_data.get('contextId'),
            artifacts=task_data.get('artifacts'),
            history=task_data.get('history'),
            metadata=task_data.get('metadata'),
        )

    async def a2a_get_task(
        self, task_id: str, history_length: Optional[int] = None
    ) -> Optional[A2ATask]:
        """Get an A2A protocol task by ID (tasks/get).

        Args:
            task_id: The task ID.
            history_length: Optional number of history items to include.

        Returns:
            The A2ATask if found.
        """
        params: Dict[str, Any] = {'id': task_id}
        if history_length is not None:
            params['historyLength'] = history_length

        result = await self._a2a_call('tasks/get', params)
        task_data = result.get('task', {})

        if not task_data:
            return None

        return A2ATask(
            id=task_data.get('id', task_id),
            status=task_data.get('status', {}).get('state', 'pending'),
            context_id=task_data.get('contextId'),
            artifacts=task_data.get('artifacts'),
            history=task_data.get('history'),
            metadata=task_data.get('metadata'),
        )

    async def a2a_cancel_task(self, task_id: str) -> A2ATask:
        """Cancel an A2A protocol task (tasks/cancel).

        Args:
            task_id: The task ID to cancel.

        Returns:
            The updated A2ATask.
        """
        result = await self._a2a_call('tasks/cancel', {'id': task_id})
        task_data = result.get('task', {})

        return A2ATask(
            id=task_data.get('id', task_id),
            status=task_data.get('status', {}).get('state', 'cancelled'),
            context_id=task_data.get('contextId'),
            artifacts=task_data.get('artifacts'),
            metadata=task_data.get('metadata'),
        )

    async def send_message_async(
        self,
        message: str,
        codebase_id: str = 'global',
        model: Optional[str] = None,
        model_ref: Optional[str] = None,
        worker_personality: Optional[str] = None,
        priority: int = 0,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a message asynchronously (fire-and-forget with task tracking).

        Creates a task that workers will pick up. Returns task_id for polling.

        Args:
            message: The message/prompt for the agent.
            codebase_id: Target codebase ID.
            model: Friendly model name (e.g. 'claude-sonnet', 'gemini').
            model_ref: Normalized model ID (e.g. 'anthropic:claude-3.5-sonnet').
            worker_personality: Worker personality for routing.
            priority: Priority level.
            conversation_id: Optional conversation thread.

        Returns:
            Dict with task_id, run_id, status, conversation_id.
        """
        arguments: Dict[str, Any] = {
            'message': message,
            'codebase_id': codebase_id,
            'priority': priority,
        }
        if model:
            arguments['model'] = model
        if model_ref:
            arguments['model_ref'] = model_ref
        if worker_personality:
            arguments['worker_personality'] = worker_personality
        if conversation_id:
            arguments['conversation_id'] = conversation_id

        return await self.call_tool('send_message_async', arguments)

    async def send_to_agent(
        self,
        agent_name: str,
        message: str,
        model: Optional[str] = None,
        model_ref: Optional[str] = None,
        deadline_seconds: Optional[int] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a message to a specific named agent via A2A protocol.

        Args:
            agent_name: Target agent name.
            message: The message content.
            model: Friendly model name.
            model_ref: Normalized model identifier.
            deadline_seconds: Fail if not claimed within this time.
            conversation_id: Optional conversation thread.

        Returns:
            Dict with task_id, run_id, target_agent_name, status.
        """
        arguments: Dict[str, Any] = {
            'agent_name': agent_name,
            'message': message,
        }
        if model:
            arguments['model'] = model
        if model_ref:
            arguments['model_ref'] = model_ref
        if deadline_seconds is not None:
            arguments['deadline_seconds'] = deadline_seconds
        if conversation_id:
            arguments['conversation_id'] = conversation_id

        return await self.call_tool('send_to_agent', arguments)

    # =========================================================================
    # Agent Registration & Heartbeat
    # =========================================================================

    async def register_agent(
        self,
        name: str,
        description: str,
        url: str,
        capabilities: Optional[Dict[str, bool]] = None,
        models_supported: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Register this agent in the A2A network.

        Args:
            name: Unique agent name.
            description: Human-readable description.
            url: Base URL where this agent can be reached.
            capabilities: Streaming/push capabilities.
            models_supported: List of model identifiers.

        Returns:
            Registration result.
        """
        arguments: Dict[str, Any] = {
            'name': name,
            'description': description,
            'url': url,
        }
        if capabilities:
            arguments['capabilities'] = capabilities
        if models_supported:
            arguments['models_supported'] = models_supported

        return await self.call_tool('register_agent', arguments)

    async def refresh_heartbeat(self, agent_name: str) -> Dict[str, Any]:
        """Refresh the heartbeat for a registered agent.

        Args:
            agent_name: Name of the agent to refresh.

        Returns:
            Heartbeat result.
        """
        return await self.call_tool(
            'refresh_agent_heartbeat', {'agent_name': agent_name}
        )

    # =========================================================================
    # Codebase Operations
    # =========================================================================

    async def list_codebases(self) -> List[Codebase]:
        """List all registered codebases.

        Returns:
            A list of Codebase objects.
        """
        result = await self.call_tool('list_codebases', {})
        codebases = []
        for cb in result.get('codebases', []):
            codebases.append(
                Codebase(
                    id=cb.get('id', cb.get('codebase_id', '')),
                    name=cb.get('name', ''),
                    path=cb.get('path', ''),
                    status=cb.get('status', 'active'),
                    worker_id=cb.get('worker_id'),
                )
            )
        return codebases

    async def get_current_codebase(self) -> Optional[Codebase]:
        """Get the current/active codebase.

        Returns:
            The current Codebase, or None.
        """
        result = await self.call_tool('get_current_codebase', {})
        if not result or not result.get('codebase_id'):
            return None
        return Codebase(
            id=result.get('codebase_id', ''),
            name=result.get('name', ''),
            path=result.get('path', ''),
        )

    # =========================================================================
    # Task Updates (Polling)
    # =========================================================================

    async def get_task_updates(
        self,
        since_timestamp: Optional[str] = None,
        task_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Poll for recent task status changes.

        Args:
            since_timestamp: ISO timestamp to get updates since.
            task_ids: Specific task IDs to check.

        Returns:
            List of task update dicts.
        """
        arguments: Dict[str, Any] = {}
        if since_timestamp:
            arguments['since_timestamp'] = since_timestamp
        if task_ids:
            arguments['task_ids'] = task_ids

        result = await self.call_tool('get_task_updates', arguments)
        return result.get('tasks', result.get('updates', []))
