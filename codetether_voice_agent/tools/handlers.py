import logging
from typing import Any, Dict, Optional

try:
    from codetether_voice_agent.codetether_mcp import CodeTetherMCP
except ImportError:
    from codetether_mcp import CodeTetherMCP

logger = logging.getLogger(__name__)


async def create_task_handler(
    mcp_client: CodeTetherMCP,
    title: str,
    description: str = '',
    codebase_id: str = 'global',
    agent_type: str = 'build',
    priority: int = 0,
) -> str:
    """Create a new task and return a human-readable response.

    Args:
        mcp_client: The CodeTether MCP client instance.
        title: The title of the task.
        description: A detailed description of the task.
        codebase_id: The codebase ID to associate with the task.
        agent_type: The type of agent to handle the task.
        priority: The priority level of the task (0-10).

    Returns:
        A string suitable for voice output describing the created task.
    """
    try:
        task = await mcp_client.create_task(
            title=title,
            description=description,
            codebase_id=codebase_id,
            agent_type=agent_type,
            priority=priority,
        )

        priority_label = 'low'
        if priority >= 7:
            priority_label = 'high'
        elif priority >= 4:
            priority_label = 'medium'

        return (
            f"I've created a new task titled '{task.title}'. "
            f"The task ID is {task.id} and it's set to {task.status} status. "
            f"It's assigned to a {task.agent_type} agent with {priority_label} priority."
        )
    except Exception as e:
        logger.error(f'Failed to create task: {e}')
        return f"I'm sorry, I couldn't create the task. An error occurred: {str(e)}"


async def list_tasks_handler(
    mcp_client: CodeTetherMCP,
    status: Optional[str] = None,
    codebase_id: Optional[str] = None,
) -> str:
    """List tasks with optional filtering and return a human-readable response.

    Args:
        mcp_client: The CodeTether MCP client instance.
        status: Optional status filter.
        codebase_id: Optional codebase ID filter.

    Returns:
        A string suitable for voice output describing the tasks.
    """
    try:
        tasks = await mcp_client.list_tasks(
            status=status, codebase_id=codebase_id
        )

        if not tasks:
            if status:
                return f"There are no tasks with status '{status}'."
            return 'There are no tasks in the system.'

        task_count = len(tasks)
        status_msg = f" with status '{status}'" if status else ''
        codebase_msg = f" in codebase '{codebase_id}'" if codebase_id else ''

        response = f'There are {task_count} task{"" if task_count == 1 else "s"}{status_msg}{codebase_msg}. '

        if task_count <= 3:
            task_details = []
            for task in tasks:
                task_details.append(f"'{task.title}' ({task.status})")
            response += 'They are: ' + ', '.join(task_details) + '.'
        else:
            pending_count = sum(1 for t in tasks if t.status == 'pending')
            running_count = sum(1 for t in tasks if t.status == 'running')
            completed_count = sum(1 for t in tasks if t.status == 'completed')

            response += f'Summary: {pending_count} pending, {running_count} running, {completed_count} completed. '
            response += f"The first one is '{tasks[0].title}' with {tasks[0].status} status."

        return response
    except Exception as e:
        logger.error(f'Failed to list tasks: {e}')
        return f"I'm sorry, I couldn't retrieve the tasks. An error occurred: {str(e)}"


async def get_task_handler(
    mcp_client: CodeTetherMCP,
    task_id: str,
) -> str:
    """Get details of a specific task and return a human-readable response.

    Args:
        mcp_client: The CodeTether MCP client instance.
        task_id: The unique identifier of the task.

    Returns:
        A string suitable for voice output describing the task details.
    """
    try:
        task = await mcp_client.get_task(task_id)

        if task is None:
            return f"I couldn't find a task with ID '{task_id}'."

        priority_label = 'low'
        if task.priority >= 7:
            priority_label = 'high'
        elif task.priority >= 4:
            priority_label = 'medium'

        response = f"Task '{task.title}' has ID {task.id}. "
        response += f"It's currently {task.status} and assigned to a {task.agent_type} agent. "
        response += f'Priority is {priority_label} (level {task.priority}).'

        if task.description:
            response += f' The description is: {task.description}.'

        if task.result:
            response += ' The task has completed with a result.'
        elif task.error:
            response += f' However, there was an error: {task.error}'

        return response
    except Exception as e:
        logger.error(f'Failed to get task: {e}')
        return f"I'm sorry, I couldn't retrieve the task details. An error occurred: {str(e)}"


async def cancel_task_handler(
    mcp_client: CodeTetherMCP,
    task_id: str,
) -> str:
    """Cancel a task and return a human-readable response.

    Args:
        mcp_client: The CodeTether MCP client instance.
        task_id: The unique identifier of the task to cancel.

    Returns:
        A string suitable for voice output describing the cancellation result.
    """
    try:
        success = await mcp_client.cancel_task(task_id)

        if success:
            return f"I've successfully cancelled task {task_id}."
        else:
            return f"I wasn't able to cancel task {task_id}. It may have already been completed or cancelled."
    except Exception as e:
        logger.error(f'Failed to cancel task: {e}')
        return f"I'm sorry, I couldn't cancel the task. An error occurred: {str(e)}"


async def get_conversation_history_handler(
    mcp_client: CodeTetherMCP,
    conversation_id: str,
) -> str:
    """Get conversation history from the A2A monitoring system.

    Note: This retrieves logged messages from the A2A server's monitoring system,
    NOT the current voice conversation with the user.

    Args:
        mcp_client: The CodeTether MCP client instance.
        conversation_id: The unique identifier of the conversation thread.

    Returns:
        A string suitable for voice output describing the conversation history.
    """
    try:
        messages = await mcp_client.get_session_messages(conversation_id)

        if not messages:
            return f"I couldn't find any messages for conversation '{conversation_id}'. The conversation may not exist or may be empty."

        message_count = len(messages)
        response = f'This conversation contains {message_count} message{"" if message_count == 1 else "s"}. '

        user_messages = [m for m in messages if m.role == 'user']
        assistant_messages = [
            m for m in messages if m.role in ('assistant', 'agent')
        ]

        if user_messages:
            response += f'It includes {len(user_messages)} from users and {len(assistant_messages)} from agents. '

        if message_count <= 5:
            response += "Here's what was discussed: "
            for i, msg in enumerate(messages[:5]):
                role = msg.role.capitalize()
                content = (
                    msg.content[:100] + '...'
                    if len(msg.content) > 100
                    else msg.content
                )
                response += f'{role}: {content}. '
        else:
            response += f"The most recent message is from {messages[-1].role}: '{messages[-1].content[:100]}...'"

        return response
    except Exception as e:
        logger.error(f'Failed to get conversation history: {e}')
        return f"I'm sorry, I couldn't retrieve the conversation history. An error occurred: {str(e)}"


async def get_monitor_messages_handler(
    mcp_client: CodeTetherMCP,
    limit: int = 20,
) -> str:
    """Get recent messages from the A2A monitoring system.

    Args:
        mcp_client: The CodeTether MCP client instance.
        limit: Maximum number of messages to retrieve.

    Returns:
        A string suitable for voice output describing recent activity.
    """
    try:
        messages = await mcp_client.get_monitor_messages(limit=limit)

        if not messages:
            return 'No recent messages in the monitoring system.'

        message_count = len(messages)
        response = f'Found {message_count} recent message{"" if message_count == 1 else "s"} in the monitoring system. '

        # Summarize by agent
        agents = {}
        for msg in messages:
            agent = msg.get('agent_name', 'unknown')
            agents[agent] = agents.get(agent, 0) + 1

        if agents:
            agent_summary = ', '.join(
                [f'{name}: {count}' for name, count in list(agents.items())[:3]]
            )
            response += f'Activity by agent: {agent_summary}. '

        # Show most recent
        if messages:
            recent = messages[-1]
            content = recent.get('content', '')[:100]
            agent = recent.get('agent_name', 'unknown')
            response += f'Most recent from {agent}: {content}'

        return response
    except Exception as e:
        logger.error(f'Failed to get monitor messages: {e}')
        return f"I'm sorry, I couldn't retrieve the monitoring messages. An error occurred: {str(e)}"


async def discover_agents_handler(
    mcp_client: CodeTetherMCP,
) -> str:
    """Discover available agents and return a human-readable response.

    Args:
        mcp_client: The CodeTether MCP client instance.

    Returns:
        A string suitable for voice output listing the available agents.
    """
    try:
        agents = await mcp_client.discover_agents()

        if not agents:
            return 'There are no agents currently available in the system.'

        agent_count = len(agents)
        response = f'I found {agent_count} available agent{"" if agent_count == 1 else "s"}: '

        agent_names = [agent.name for agent in agents]
        agent_descriptions = [
            agent.description for agent in agents if agent.description
        ]

        response += ', '.join(agent_names) + '. '

        if agent_descriptions:
            response += 'Notable agents include: '
            for i, (name, desc) in enumerate(
                zip(agent_names[:3], agent_descriptions[:3])
            ):
                response += f'{name} - {desc}. '

        return response
    except Exception as e:
        logger.error(f'Failed to discover agents: {e}')
        return f"I'm sorry, I couldn't discover available agents. An error occurred: {str(e)}"


async def send_message_handler(
    mcp_client: CodeTetherMCP,
    agent_name: str,
    message: str,
) -> str:
    """Send a message to an agent and return a human-readable response.

    Args:
        mcp_client: The CodeTether MCP client instance.
        agent_name: The name of the agent to send the message to.
        message: The message content to send.

    Returns:
        A string suitable for voice output describing the message sending result.
    """
    try:
        result = await mcp_client.send_message(
            agent_name=agent_name, message=message
        )

        response = f'Message sent to {agent_name}. '

        if isinstance(result, dict):
            if result.get('success'):
                response += 'The agent has received your message.'
            if 'response' in result:
                response += f' They responded: {result["response"][:200]}...'
            if 'error' in result:
                response += f' However, there was an issue: {result["error"]}'
        else:
            response += 'The message was delivered successfully.'

        return response
    except Exception as e:
        logger.error(f'Failed to send message: {e}')
        return f"I'm sorry, I couldn't send the message to {agent_name}. An error occurred: {str(e)}"


async def register_all_tools(
    mcp_client: CodeTetherMCP,
) -> Dict[str, Any]:
    """Register all tool handlers with their schemas for the voice agent.

    Args:
        mcp_client: The CodeTether MCP client instance.

    Returns:
        A dictionary mapping tool names to their handler functions.
    """
    from .definitions import (
        CREATE_TASK_SCHEMA,
        LIST_TASKS_SCHEMA,
        GET_TASK_SCHEMA,
        CANCEL_TASK_SCHEMA,
        GET_CONVERSATION_HISTORY_SCHEMA,
        GET_MONITOR_MESSAGES_SCHEMA,
        DISCOVER_AGENTS_SCHEMA,
        SEND_MESSAGE_SCHEMA,
    )

    tools = {
        'create_task': {
            'schema': CREATE_TASK_SCHEMA,
            'handler': lambda args: create_task_handler(
                mcp_client,
                title=args.get('title', ''),
                description=args.get('description', ''),
                codebase_id=args.get('codebase_id', 'global'),
                agent_type=args.get('agent_type', 'build'),
                priority=args.get('priority', 0),
            ),
        },
        'list_tasks': {
            'schema': LIST_TASKS_SCHEMA,
            'handler': lambda args: list_tasks_handler(
                mcp_client,
                status=args.get('status'),
                codebase_id=args.get('codebase_id'),
            ),
        },
        'get_task': {
            'schema': GET_TASK_SCHEMA,
            'handler': lambda args: get_task_handler(
                mcp_client,
                task_id=args.get('task_id', ''),
            ),
        },
        'cancel_task': {
            'schema': CANCEL_TASK_SCHEMA,
            'handler': lambda args: cancel_task_handler(
                mcp_client,
                task_id=args.get('task_id', ''),
            ),
        },
        'get_conversation_history': {
            'schema': GET_CONVERSATION_HISTORY_SCHEMA,
            'handler': lambda args: get_conversation_history_handler(
                mcp_client,
                conversation_id=args.get('conversation_id', ''),
            ),
        },
        'get_monitor_messages': {
            'schema': GET_MONITOR_MESSAGES_SCHEMA,
            'handler': lambda args: get_monitor_messages_handler(
                mcp_client,
                limit=args.get('limit', 20),
            ),
        },
        'discover_agents': {
            'schema': DISCOVER_AGENTS_SCHEMA,
            'handler': lambda args: discover_agents_handler(mcp_client),
        },
        'send_message': {
            'schema': SEND_MESSAGE_SCHEMA,
            'handler': lambda args: send_message_handler(
                mcp_client,
                agent_name=args.get('agent_name', ''),
                message=args.get('message', ''),
            ),
        },
    }

    logger.info(f'Registered {len(tools)} tools for voice agent')
    return tools
