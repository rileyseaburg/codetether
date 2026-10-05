'use strict';

const API_BASE = 'https://api.codetether.io';

const findTask = async (z, bundle) => {
  // If task_id is provided, fetch directly
  if (bundle.inputData.task_id) {
    const response = await z.request({
      url: `${API_BASE}/v1/tasks/${bundle.inputData.task_id}`,
    });

    if (response.status === 404) {
      return []; // No match found
    }

    if (response.status !== 200) {
      throw new z.errors.Error(
        `Failed to find task: ${response.data.detail || response.statusText}`,
        'FindTaskError',
        response.status
      );
    }

    const task = response.data;
    return [{
      id: task.task_id || task.id,
      task_id: task.task_id || task.id,
      title: task.title,
      description: task.description,
      status: task.status,
      priority: task.priority,
      agent_type: task.agent_type,
      codebase_id: task.codebase_id,
      created_at: task.created_at,
      updated_at: task.updated_at,
    }];
  }

  // Otherwise, search by status
  const params = { limit: 1 };
  if (bundle.inputData.status) {
    params.status = bundle.inputData.status;
  }

  const response = await z.request({
    url: `${API_BASE}/v1/tasks`,
    params,
  });

  const tasks = response.data.tasks || response.data || [];
  
  return tasks.slice(0, 1).map(task => ({
    id: task.task_id || task.id,
    task_id: task.task_id || task.id,
    title: task.title,
    description: task.description,
    status: task.status,
    priority: task.priority,
    agent_type: task.agent_type,
    codebase_id: task.codebase_id,
    created_at: task.created_at,
    updated_at: task.updated_at,
  }));
};

module.exports = {
  key: 'find_task',
  noun: 'Task',

  display: {
    label: 'Find Task',
    description: 'Finds an existing task by ID or status.',
  },

  operation: {
    inputFields: [
      {
        key: 'task_id',
        label: 'Task ID',
        type: 'string',
        required: false,
        helpText: 'The specific task ID to look up.',
      },
      {
        key: 'status',
        label: 'Status',
        type: 'string',
        choices: ['pending', 'working', 'completed', 'failed', 'cancelled'],
        required: false,
        helpText: 'Find the most recent task with this status.',
      },
    ],

    perform: findTask,

    sample: {
      id: 'task_abc123',
      task_id: 'task_abc123',
      title: 'Fix authentication bug',
      description: 'The OAuth2 refresh token flow is failing.',
      status: 'completed',
      priority: 5,
      agent_type: 'build',
      codebase_id: 'global',
      created_at: '2024-01-15T10:30:00Z',
      updated_at: '2024-01-15T11:45:00Z',
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
      { key: 'updated_at', label: 'Updated At' },
    ],
  },
};
