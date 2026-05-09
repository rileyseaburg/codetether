'use strict';

const API_BASE = 'https://api.codetether.io';

const createTask = async (z, bundle) => {
  const response = await z.request({
    url: `${API_BASE}/v1/tasks`,
    method: 'POST',
    body: {
      title: bundle.inputData.title,
      description: bundle.inputData.description,
      priority: bundle.inputData.priority || 0,
      agent_type: bundle.inputData.agent_type || 'build',
      codebase_id: bundle.inputData.codebase_id,
      model: bundle.inputData.model,
    },
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (response.status !== 200 && response.status !== 201) {
    throw new z.errors.Error(
      `Failed to create task: ${response.data.detail || response.statusText}`,
      'CreateTaskError',
      response.status
    );
  }

  const task = response.data;
  
  return {
    id: task.task_id || task.id,
    task_id: task.task_id || task.id,
    title: task.title,
    description: task.description,
    status: task.status,
    priority: task.priority,
    agent_type: task.agent_type,
    codebase_id: task.codebase_id,
    created_at: task.created_at,
  };
};

module.exports = {
  key: 'create_task',
  noun: 'Task',

  display: {
    label: 'Create Task',
    description: 'Creates a new task in the CodeTether queue for an AI agent to pick up.',
  },

  operation: {
    inputFields: [
      {
        key: 'title',
        label: 'Title',
        type: 'string',
        required: true,
        helpText: 'A short, descriptive title for the task.',
      },
      {
        key: 'description',
        label: 'Description',
        type: 'text',
        required: false,
        helpText: 'Detailed description of what the task should accomplish.',
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
        key: 'agent_type',
        label: 'Agent Type',
        type: 'string',
        choices: ['build', 'plan', 'general', 'explore'],
        required: false,
        default: 'build',
        helpText: 'Type of AI agent to handle this task.',
      },
      {
        key: 'codebase_id',
        label: 'Codebase ID',
        type: 'string',
        required: false,
        helpText: 'Target codebase ID (defaults to global).',
      },
      {
        key: 'model',
        label: 'AI Model',
        type: 'string',
        choices: ['default', 'claude-sonnet', 'claude-opus', 'gpt-4', 'gemini-pro'],
        required: false,
        helpText: 'AI model to use for this task.',
      },
    ],

    perform: createTask,

    sample: {
      id: 'task_abc123',
      task_id: 'task_abc123',
      title: 'Fix authentication bug',
      description: 'The OAuth2 refresh token flow is failing.',
      status: 'pending',
      priority: 5,
      agent_type: 'build',
      codebase_id: 'global',
      created_at: '2024-01-15T10:30:00Z',
    },

    outputFields: [
      { key: 'id', label: 'ID' },
      { key: 'task_id', label: 'Task ID' },
      { key: 'title', label: 'Title' },
      { key: 'description', label: 'Description' },
      { key: 'status', label: 'Status' },
      { key: 'priority', label: 'Priority' },
      { key: 'agent_type', label: 'Agent Type' },
      { key: 'codebase_id', label: 'Codebase ID' },
      { key: 'created_at', label: 'Created At' },
    ],
  },
};
