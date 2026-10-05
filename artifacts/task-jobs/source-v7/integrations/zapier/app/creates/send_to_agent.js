'use strict';

const API_BASE = 'https://api.codetether.io';

const sendToAgent = async (z, bundle) => {
    const body = {
        agent_name: bundle.inputData.agent_name,
        message: bundle.inputData.message,
    };

    if (bundle.inputData.conversation_id) {
        body.conversation_id = bundle.inputData.conversation_id;
    }
    if (bundle.inputData.codebase_id) {
        body.codebase_id = bundle.inputData.codebase_id;
    }
    if (bundle.inputData.priority) {
        body.priority = parseInt(bundle.inputData.priority, 10);
    }
    if (bundle.inputData.deadline_seconds) {
        body.deadline_seconds = parseInt(bundle.inputData.deadline_seconds, 10);
    }
    if (bundle.inputData.notify_email) {
        body.notify_email = bundle.inputData.notify_email;
    }
    if (bundle.inputData.model) {
        body.model = bundle.inputData.model;
    }
    if (bundle.inputData.model_ref) {
        body.model_ref = bundle.inputData.model_ref;
    }

    const response = await z.request({
        url: `${API_BASE}/v1/agents/send`,
        method: 'POST',
        body,
        headers: {
            'Content-Type': 'application/json',
        },
    });

    if (response.status !== 200 && response.status !== 201) {
        throw new z.errors.Error(
            `Failed to send to agent: ${response.data.detail || response.statusText}`,
            'SendToAgentError',
            response.status
        );
    }

    const data = response.data;

    return {
        id: data.task_id || data.id,
        task_id: data.task_id,
        run_id: data.run_id,
        target_agent_name: data.target_agent_name || bundle.inputData.agent_name,
        status: data.status || 'pending',
        timestamp: data.timestamp || new Date().toISOString(),
    };
};

module.exports = {
    key: 'send_to_agent',
    noun: 'Agent Message',

    display: {
        label: 'Send to Specific Agent',
        description:
            'Send a message to a specific named agent. The task queues until that agent is available.',
    },

    operation: {
        inputFields: [
            {
                key: 'agent_name',
                label: 'Agent Name',
                type: 'string',
                required: true,
                helpText:
                    'Name of the target agent (must match the name used during worker registration).',
                dynamic: 'discover_agents.name.name',
            },
            {
                key: 'message',
                label: 'Message',
                type: 'text',
                required: true,
                helpText: 'The message/prompt for the agent to process.',
            },
            {
                key: 'conversation_id',
                label: 'Conversation ID',
                type: 'string',
                required: false,
                helpText: 'Optional conversation ID for message threading.',
            },
            {
                key: 'codebase_id',
                label: 'Codebase ID',
                type: 'string',
                required: false,
                helpText: 'Target codebase ID (defaults to global).',
            },
            {
                key: 'priority',
                label: 'Priority',
                type: 'integer',
                required: false,
                default: '0',
                helpText: 'Higher numbers = more urgent.',
            },
            {
                key: 'deadline_seconds',
                label: 'Deadline (seconds)',
                type: 'integer',
                required: false,
                helpText:
                    'Fail if not claimed within this many seconds. Leave empty for unlimited.',
            },
            {
                key: 'notify_email',
                label: 'Notification Email',
                type: 'string',
                required: false,
                helpText: 'Email to notify when task completes.',
            },
            {
                key: 'model',
                label: 'AI Model',
                type: 'string',
                choices: [
                    'default',
                    'claude-sonnet',
                    'claude-opus',
                    'gpt-4',
                    'gpt-4.1',
                    'gemini-pro',
                    'minimax',
                ],
                required: false,
                helpText: 'AI model to use.',
            },
            {
                key: 'model_ref',
                label: 'Model Reference',
                type: 'string',
                required: false,
                helpText:
                    'Normalized model ID (provider:model format). Takes precedence over Model.',
            },
        ],

        perform: sendToAgent,

        sample: {
            id: 'task_abc123',
            task_id: 'task_abc123',
            run_id: 'run_abc123',
            target_agent_name: 'codetether-builder',
            status: 'pending',
            timestamp: '2026-02-10T10:30:00Z',
        },

        outputFields: [
            { key: 'id', label: 'ID' },
            { key: 'task_id', label: 'Task ID' },
            { key: 'run_id', label: 'Run ID' },
            { key: 'target_agent_name', label: 'Target Agent' },
            { key: 'status', label: 'Status' },
            { key: 'timestamp', label: 'Timestamp' },
        ],
    },
};
