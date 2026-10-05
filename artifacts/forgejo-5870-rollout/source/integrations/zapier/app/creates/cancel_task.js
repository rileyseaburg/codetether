'use strict';

const API_BASE = 'https://api.codetether.io';

const cancelTask = async (z, bundle) => {
  const response = await z.request({
    url: `${API_BASE}/v1/tasks/${bundle.inputData.task_id}/cancel`,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (response.status === 404) {
    throw new z.errors.Error(
      `Task not found: ${bundle.inputData.task_id}`,
      'TaskNotFoundError',
      404
    );
  }

  if (response.status !== 200) {
    throw new z.errors.Error(
      `Failed to cancel task: ${response.data.detail || response.statusText}`,
      'CancelTaskError',
      response.status
    );
  }

  const task = response.data;
  
  return {
    id: task.task_id || task.id,
    task_id: task.task_id || task.id,
    title: task.title,
    status: task.status,
    cancelled: task.status === 'cancelled',
    cancelled_at: new Date().toISOString(),
  };
};

module.exports = {
  key: 'cancel_task',
  noun: 'Task',

  display: {
    label: 'Cancel Task',
    description: 'Cancels a pending or in-progress task.',
  },

  operation: {
    inputFields: [
      {
        key: 'task_id',
        label: 'Task ID',
        type: 'string',
        required: true,
        helpText: 'The ID of the task to cancel.',
        dynamic: 'new_task.id.title',
      },
      {
        key: 'confirm',
        label: 'Confirm Cancellation',
        type: 'copy',
        helpText: 'Warning: This action cannot be undone. The task will be permanently cancelled.',
      },
    ],

    perform: cancelTask,

    sample: {
      id: 'task_abc123',
      task_id: 'task_abc123',
      title: 'Fix authentication bug',
      status: 'cancelled',
      cancelled: true,
      cancelled_at: '2024-01-15T12:00:00Z',
    },

    outputFields: [
      { key: 'id', label: 'ID' },
      { key: 'task_id', label: 'Task ID' },
      { key: 'title', label: 'Title' },
      { key: 'status', label: 'Status' },
      { key: 'cancelled', label: 'Cancelled', type: 'boolean' },
      { key: 'cancelled_at', label: 'Cancelled At' },
    ],
  },
};
