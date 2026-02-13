from typing import Any, Dict, List

# ─── A2A Protocol Tool Schemas ──────────────────────────────────────

A2A_SEND_MESSAGE_SCHEMA = {
    'name': 'a2a_send_message',
    'description': 'Send a message via the A2A protocol. Creates a task that a worker agent processes and returns artifacts with results.',
    'parameters': {
        'type': 'object',
        'properties': {
            'message': {
                'type': 'string',
                'description': 'The message to send for processing',
            },
            'model': {
                'type': 'string',
                'description': "Optional model name (e.g., 'claude-sonnet', 'gemini', 'gpt-4')",
            },
            'model_ref': {
                'type': 'string',
                'description': "Optional normalized model ID (e.g., 'anthropic:claude-3.5-sonnet')",
            },
        },
        'required': ['message'],
    },
}

A2A_SEND_TO_AGENT_SCHEMA = {
    'name': 'a2a_send_to_agent',
    'description': 'Send a message to a specific named agent via A2A protocol. The task queues until that agent claims it.',
    'parameters': {
        'type': 'object',
        'properties': {
            'agent_name': {
                'type': 'string',
                'description': 'Name of the target agent',
            },
            'message': {
                'type': 'string',
                'description': 'The message to send',
            },
            'model': {
                'type': 'string',
                'description': 'Optional model name',
            },
            'model_ref': {
                'type': 'string',
                'description': 'Optional normalized model ID',
            },
            'deadline_seconds': {
                'type': 'integer',
                'description': 'Optional: fail if not claimed within this many seconds',
            },
        },
        'required': ['agent_name', 'message'],
    },
}

A2A_GET_TASK_SCHEMA = {
    'name': 'a2a_get_task',
    'description': 'Get the status and artifacts of an A2A task. Use after a2a_send_message to check results.',
    'parameters': {
        'type': 'object',
        'properties': {
            'task_id': {
                'type': 'string',
                'description': 'The A2A task ID',
            },
        },
        'required': ['task_id'],
    },
}

A2A_CANCEL_TASK_SCHEMA = {
    'name': 'a2a_cancel_task',
    'description': 'Cancel an in-progress A2A task.',
    'parameters': {
        'type': 'object',
        'properties': {
            'task_id': {
                'type': 'string',
                'description': 'The A2A task ID to cancel',
            },
        },
        'required': ['task_id'],
    },
}

# ─── Task Queue Schemas ─────────────────────────────────────────────

CREATE_TASK_SCHEMA = {
    'name': 'create_task',
    'description': 'Create a new task in the queue with optional model selection. Workers claim pending tasks via SSE.',
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
            'priority': {
                'type': 'integer',
                'description': 'Priority level (0-10, where 10 is highest). Defaults to 0.',
            },
            'model': {
                'type': 'string',
                'description': "Model to use (e.g., 'claude-sonnet', 'gemini', 'gpt-4', 'minimax')",
            },
            'model_ref': {
                'type': 'string',
                'description': "Normalized model ID (e.g., 'anthropic:claude-3.5-sonnet')",
            },
        },
        'required': ['title'],
    },
}

LIST_TASKS_SCHEMA = {
    'name': 'list_tasks',
    'description': 'List tasks in the queue. Filter by status (pending, working, completed, failed, cancelled).',
    'parameters': {
        'type': 'object',
        'properties': {
            'status': {
                'type': 'string',
                'description': "Filter by status (e.g., 'pending', 'working', 'completed')",
            },
        },
        'required': [],
    },
}

GET_TASK_SCHEMA = {
    'name': 'get_task',
    'description': 'Get details about a specific task by its ID from the task queue.',
    'parameters': {
        'type': 'object',
        'properties': {
            'task_id': {
                'type': 'string',
                'description': 'The unique task ID',
            },
        },
        'required': ['task_id'],
    },
}

CANCEL_TASK_SCHEMA = {
    'name': 'cancel_task',
    'description': 'Cancel a running or pending task from the queue.',
    'parameters': {
        'type': 'object',
        'properties': {
            'task_id': {
                'type': 'string',
                'description': 'The task ID to cancel',
            },
        },
        'required': ['task_id'],
    },
}

# ─── Agent Discovery Schemas ────────────────────────────────────────

DISCOVER_AGENTS_SCHEMA = {
    'name': 'discover_agents',
    'description': 'Find what agents are registered and online in the A2A network.',
    'parameters': {
        'type': 'object',
        'properties': {},
        'required': [],
    },
}

SEND_MESSAGE_SCHEMA = {
    'name': 'send_message',
    'description': 'Send a direct message to a registered agent.',
    'parameters': {
        'type': 'object',
        'properties': {
            'agent_name': {
                'type': 'string',
                'description': 'The name of the agent to message',
            },
            'message': {
                'type': 'string',
                'description': 'The message content',
            },
        },
        'required': ['agent_name', 'message'],
    },
}

# ─── Codebase Schemas ───────────────────────────────────────────────

LIST_CODEBASES_SCHEMA = {
    'name': 'list_codebases',
    'description': 'List all registered project codebases that workers operate on.',
    'parameters': {
        'type': 'object',
        'properties': {},
        'required': [],
    },
}

GET_CURRENT_CODEBASE_SCHEMA = {
    'name': 'get_current_codebase',
    'description': 'Get the currently active codebase context.',
    'parameters': {
        'type': 'object',
        'properties': {},
        'required': [],
    },
}

# ─── Monitoring Schemas ─────────────────────────────────────────────

GET_MONITOR_MESSAGES_SCHEMA = {
    'name': 'get_monitor_messages',
    'description': 'Get recent activity from all agents in the monitoring system.',
    'parameters': {
        'type': 'object',
        'properties': {
            'limit': {
                'type': 'integer',
                'description': 'Maximum number of messages to retrieve (default: 20)',
            },
        },
        'required': [],
    },
}

GET_CONVERSATION_HISTORY_SCHEMA = {
    'name': 'get_conversation_history',
    'description': 'Get message history for a specific conversation thread by ID.',
    'parameters': {
        'type': 'object',
        'properties': {
            'conversation_id': {
                'type': 'string',
                'description': 'The conversation thread ID',
            },
        },
        'required': ['conversation_id'],
    },
}

GET_TASK_UPDATES_SCHEMA = {
    'name': 'get_task_updates',
    'description': 'Poll for recent task status changes. Optionally filter by timestamp.',
    'parameters': {
        'type': 'object',
        'properties': {
            'since_timestamp': {
                'type': 'string',
                'description': 'ISO timestamp to get updates since (optional)',
            },
        },
        'required': [],
    },
}

ALL_TOOL_SCHEMAS: List[Dict[str, Any]] = [
    # A2A Protocol
    A2A_SEND_MESSAGE_SCHEMA,
    A2A_SEND_TO_AGENT_SCHEMA,
    A2A_GET_TASK_SCHEMA,
    A2A_CANCEL_TASK_SCHEMA,
    # Task Queue
    CREATE_TASK_SCHEMA,
    LIST_TASKS_SCHEMA,
    GET_TASK_SCHEMA,
    CANCEL_TASK_SCHEMA,
    # Agent Discovery
    DISCOVER_AGENTS_SCHEMA,
    SEND_MESSAGE_SCHEMA,
    # Codebases
    LIST_CODEBASES_SCHEMA,
    GET_CURRENT_CODEBASE_SCHEMA,
    # Monitoring
    GET_MONITOR_MESSAGES_SCHEMA,
    GET_CONVERSATION_HISTORY_SCHEMA,
    GET_TASK_UPDATES_SCHEMA,
]
