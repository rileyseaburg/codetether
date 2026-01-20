'use strict';

const API_BASE = 'https://api.codetether.io';

const listTasks = async (z, bundle) => {
  const params = {
    limit: 50,
  };

  // Filter by status if provided
  if (bundle.inputData.status) {
    params.status = bundle.inputData.status;
  }

  const response = await z.request({
    url: `${API_BASE}/v1/tasks`,
    params,
  });

  // Zapier triggers expect an array sorted by newest first
  // Each item should have a unique 'id' field
  const tasks = response.data.tasks || response.data || [];
  
  return tasks.map(task => ({
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
  key: 'new_task',
  noun: 'Task',

  display: {
    label: 'New Task',
    description: 'Triggers when a new task is created in CodeTether.',
  },

  operation: {
    inputFields: [
      {
        key: 'status',
        label: 'Status Filter',
        type: 'string',
        choices: ['pending', 'working', 'completed', 'failed', 'cancelled'],
        required: false,
        helpText: 'Only trigger for tasks with this status.',
      },
    ],

    perform: listTasks,

    sample: {
      id: 'task_abc123',
      task_id: 'task_abc123',
      title: 'Fix authentication bug',
      description: 'The OAuth2 refresh token flow is failing for Zapier users.',
      status: 'pending',
      priority: 5,
      agent_type: 'build',
      codebase_id: 'codebase_xyz789',
      created_at: '2024-01-15T10:30:00Z',
      updated_at: '2024-01-15T10:30:00Z',
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
