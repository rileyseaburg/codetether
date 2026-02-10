'use strict';

const API_BASE = 'https://api.codetether.io';

const prdChat = async (z, bundle) => {
    const body = {
        message: bundle.inputData.message,
    };

    if (bundle.inputData.conversation_id) {
        body.conversation_id = bundle.inputData.conversation_id;
    }
    if (bundle.inputData.codebase_id) {
        body.codebase_id = bundle.inputData.codebase_id;
    }

    const response = await z.request({
        url: `${API_BASE}/v1/prd/chat`,
        method: 'POST',
        body,
        headers: {
            'Content-Type': 'application/json',
        },
    });

    if (response.status !== 200 && response.status !== 201) {
        throw new z.errors.Error(
            `Failed to chat with PRD generator: ${response.data.detail || response.statusText}`,
            'PRDChatError',
            response.status
        );
    }

    const data = response.data;

    return {
        id: data.conversation_id || data.id,
        conversation_id: data.conversation_id,
        response: data.response || data.message,
        has_prd: data.has_prd || false,
        prd_json: data.prd ? JSON.stringify(data.prd) : null,
        timestamp: data.timestamp || new Date().toISOString(),
    };
};

module.exports = {
    key: 'prd_chat',
    noun: 'PRD Chat',

    display: {
        label: 'Generate PRD via Chat',
        description:
            'Chat with AI to generate a Product Requirements Document (PRD). Describe your project and the AI creates structured user stories. Use conversation_id to continue refining.',
    },

    operation: {
        inputFields: [
            {
                key: 'message',
                label: 'Message',
                type: 'text',
                required: true,
                helpText:
                    'Describe your project or answer AI questions to generate a PRD with user stories.',
            },
            {
                key: 'conversation_id',
                label: 'Conversation ID',
                type: 'string',
                required: false,
                helpText: 'Continue an existing PRD chat session.',
            },
            {
                key: 'codebase_id',
                label: 'Codebase ID',
                type: 'string',
                required: false,
                helpText: 'Target codebase for the PRD.',
            },
        ],

        perform: prdChat,

        sample: {
            id: 'conv_prd_abc123',
            conversation_id: 'conv_prd_abc123',
            response:
                'I have generated a PRD with 5 user stories for your authentication system...',
            has_prd: true,
            prd_json:
                '{"project":"Auth System","branchName":"ralph/auth","userStories":[...]}',
            timestamp: '2026-02-10T10:30:00Z',
        },

        outputFields: [
            { key: 'id', label: 'ID' },
            { key: 'conversation_id', label: 'Conversation ID' },
            { key: 'response', label: 'AI Response' },
            { key: 'has_prd', label: 'PRD Generated', type: 'boolean' },
            { key: 'prd_json', label: 'PRD (JSON)' },
            { key: 'timestamp', label: 'Timestamp' },
        ],
    },
};
