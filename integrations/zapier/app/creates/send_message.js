'use strict';

const API_BASE = 'https://api.codetether.io';

const sendMessage = async (z, bundle) => {
  const response = await z.request({
    url: `${API_BASE}/v1/messages`,
    method: 'POST',
    body: {
      message: bundle.inputData.message,
      conversation_id: bundle.inputData.conversation_id,
    },
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (response.status !== 200 && response.status !== 201) {
    throw new z.errors.Error(
      `Failed to send message: ${response.data.detail || response.statusText}`,
      'SendMessageError',
      response.status
    );
  }

  const data = response.data;
  
  return {
    id: data.conversation_id || data.id,
    conversation_id: data.conversation_id,
    response: data.response,
    success: data.success !== false,
    timestamp: data.timestamp || new Date().toISOString(),
  };
};

module.exports = {
  key: 'send_message',
  noun: 'Message',

  display: {
    label: 'Send Message to Agent',
    description: 'Sends a message to a CodeTether AI agent and receives a response.',
  },

  operation: {
    inputFields: [
      {
        key: 'message',
        label: 'Message',
        type: 'text',
        required: true,
        helpText: 'The message or prompt to send to the AI agent.',
      },
      {
        key: 'conversation_id',
        label: 'Conversation ID',
        type: 'string',
        required: false,
        helpText: 'Optional conversation ID to continue an existing thread.',
      },
    ],

    perform: sendMessage,

    sample: {
      id: 'conv_abc123',
      conversation_id: 'conv_abc123',
      response: 'I have analyzed the codebase and found 3 potential issues...',
      success: true,
      timestamp: '2024-01-15T10:30:00Z',
    },

    outputFields: [
      { key: 'id', label: 'ID' },
      { key: 'conversation_id', label: 'Conversation ID' },
      { key: 'response', label: 'Agent Response' },
      { key: 'success', label: 'Success' },
      { key: 'timestamp', label: 'Timestamp' },
    ],
  },
};
