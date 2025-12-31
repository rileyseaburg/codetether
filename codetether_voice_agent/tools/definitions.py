from typing import Any, Dict, List

CREATE_TASK_SCHEMA = {
    'name': 'create_task',
    'description': 'Create a new task in the CodeTether system. Use this when the user wants to create and assign a new task.',
    'parameters': {
        'type': 'object',
        'properties': {
            'title': {
                'type': 'string',
                'description': 'The title or name of the task',
            },
            'description': {
                'type': 'string',
                'description': 'A detailed description of what the task involves',
            },
            'codebase_id': {
                'type': 'string',
                'description': "The ID of the codebase to associate with this task. Defaults to 'global' if not specified.",
            },
            'agent_type': {
                'type': 'string',
                'description': "The type of agent to handle this task (e.g., 'build', 'test', 'review', 'documentation'). Defaults to 'build'.",
            },
            'priority': {
                'type': 'integer',
                'description': 'The priority level of the task (0-10, where 10 is highest priority). Defaults to 0.',
            },
        },
        'required': ['title'],
    },
}

LIST_TASKS_SCHEMA = {
    'name': 'list_tasks',
    'description': 'List tasks in the CodeTether system with optional filtering. Use this to show the user what tasks exist.',
    'parameters': {
        'type': 'object',
        'properties': {
            'status': {
                'type': 'string',
                'description': "Filter tasks by their status (e.g., 'pending', 'running', 'completed', 'failed', 'cancelled')",
            },
            'codebase_id': {
                'type': 'string',
                'description': 'Filter tasks by codebase ID',
            },
        },
        'required': [],
    },
}

GET_TASK_SCHEMA = {
    'name': 'get_task',
    'description': 'Get detailed information about a specific task by its ID. Use this when the user asks about a particular task.',
    'parameters': {
        'type': 'object',
        'properties': {
            'task_id': {
                'type': 'string',
                'description': 'The unique identifier of the task',
            },
        },
        'required': ['task_id'],
    },
}

CANCEL_TASK_SCHEMA = {
    'name': 'cancel_task',
    'description': 'Cancel a running or pending task. Use this when the user wants to stop a task that is in progress.',
    'parameters': {
        'type': 'object',
        'properties': {
            'task_id': {
                'type': 'string',
                'description': 'The unique identifier of the task to cancel',
            },
        },
        'required': ['task_id'],
    },
}

GET_SESSION_HISTORY_SCHEMA = {
    'name': 'get_session_history',
    'description': 'Retrieve the message history for a specific session. Use this when the user wants to review previous conversation context.',
    'parameters': {
        'type': 'object',
        'properties': {
            'session_id': {
                'type': 'string',
                'description': 'The unique identifier of the session',
            },
        },
        'required': ['session_id'],
    },
}

DISCOVER_AGENTS_SCHEMA = {
    'name': 'discover_agents',
    'description': 'Discover available CodeTether agents that can be messaged. Use this to show the user what agents are available.',
    'parameters': {
        'type': 'object',
        'properties': {},
        'required': [],
    },
}

SEND_MESSAGE_SCHEMA = {
    'name': 'send_message',
    'description': 'Send a message to a specific CodeTether agent. Use this for agent-to-agent communication.',
    'parameters': {
        'type': 'object',
        'properties': {
            'agent_name': {
                'type': 'string',
                'description': 'The name of the agent to send the message to',
            },
            'message': {
                'type': 'string',
                'description': 'The message content to send to the agent',
            },
        },
        'required': ['agent_name', 'message'],
    },
}

ALL_TOOL_SCHEMAS: List[Dict[str, Any]] = [
    CREATE_TASK_SCHEMA,
    LIST_TASKS_SCHEMA,
    GET_TASK_SCHEMA,
    CANCEL_TASK_SCHEMA,
    GET_SESSION_HISTORY_SCHEMA,
    DISCOVER_AGENTS_SCHEMA,
    SEND_MESSAGE_SCHEMA,
]
