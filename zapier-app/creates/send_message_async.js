'use strict';

const API_BASE = 'https://api.codetether.io';

const sendMessageAsync = async (z, bundle) => {
    const body = {
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
        url: `${API_BASE}/v1/messages/async`,
        method: 'POST',
        body,
        headers: {
            'Content-Type': 'application/json',
        },
    });

    if (response.status !== 200 && response.status !== 201) {
        throw new z.errors.Error(
            `Failed to send async message: ${response.data.detail || response.statusText}`,
            'SendMessageAsyncError',
            response.status
        );
    }

    const data = response.data;

    return {
        id: data.task_id || data.id,
        task_id: data.task_id,
        run_id: data.run_id,
        status: data.status || 'pending',
        conversation_id: data.conversation_id,
        timestamp: data.timestamp || new Date().toISOString(),
    };
};

module.exports = {
    key: 'send_message_async',
    noun: 'Async Message',

    display: {
        label: 'Send Async Message',
        description:
            'Send a message asynchronously. Creates a task that workers will pick up. Returns immediately with a task_id for tracking.',
    },

    operation: {
        inputFields: [
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
                helpText: 'Optional conversation ID to continue an existing thread.',
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
                helpText: 'Higher numbers = more urgent. Default is 0.',
            },
            {
                key: 'notify_email',
                label: 'Notification Email',
                type: 'string',
                required: false,
                helpText: 'Email address to notify when the task completes.',
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
                helpText: 'AI model to use for processing.',
            },
            {
                key: 'model_ref',
                label: 'Model Reference',
                type: 'string',
                required: false,
                helpText:
                    'Normalized model ID (provider:model format, e.g., "openai:gpt-4.1"). Takes precedence over Model.',
            },
        ],

        perform: sendMessageAsync,

        sample: {
            id: 'task_abc123',
            task_id: 'task_abc123',
            run_id: 'run_abc123',
            status: 'pending',
            conversation_id: 'conv_abc123',
            timestamp: '2026-02-10T10:30:00Z',
        },

        outputFields: [
            { key: 'id', label: 'ID' },
            { key: 'task_id', label: 'Task ID' },
            { key: 'run_id', label: 'Run ID' },
            { key: 'status', label: 'Status' },
            { key: 'conversation_id', label: 'Conversation ID' },
            { key: 'timestamp', label: 'Timestamp' },
        ],
    },
};
