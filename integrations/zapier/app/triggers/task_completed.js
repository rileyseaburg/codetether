'use strict';

const API_BASE = 'https://api.codetether.io';

const listCompletedTasks = async (z, bundle) => {
    const params = {
        status: 'completed',
        limit: 50,
    };

    const response = await z.request({
        url: `${API_BASE}/v1/tasks`,
        params,
    });

    const tasks = response.data.tasks || response.data || [];

    return tasks.map((task) => ({
        id: task.task_id || task.id,
        task_id: task.task_id || task.id,
        title: task.title,
        description: task.description,
        status: task.status,
        priority: task.priority,
        agent_type: task.agent_type,
        codebase_id: task.codebase_id,
        model: task.model,
        result: task.result,
        created_at: task.created_at,
        updated_at: task.updated_at,
        completed_at: task.completed_at || task.updated_at,
    }));
};

module.exports = {
    key: 'task_completed',
    noun: 'Completed Task',

    display: {
        label: 'Task Completed',
        description:
            'Triggers when a task finishes (status becomes completed). Use to chain follow-up actions.',
    },

    operation: {
        inputFields: [],

        perform: listCompletedTasks,

        sample: {
            id: 'task_abc123',
            task_id: 'task_abc123',
            title: 'Fix authentication bug',
            description: 'The OAuth2 refresh token flow was failing.',
            status: 'completed',
            priority: 5,
            agent_type: 'build',
            codebase_id: 'global',
            model: 'anthropic:claude-sonnet-4',
            result: 'Fixed the refresh token flow by updating the token expiry check.',
            created_at: '2026-02-10T10:30:00Z',
            updated_at: '2026-02-10T11:45:00Z',
            completed_at: '2026-02-10T11:45:00Z',
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
            { key: 'model', label: 'Model' },
            { key: 'result', label: 'Result' },
            { key: 'created_at', label: 'Created At' },
            { key: 'updated_at', label: 'Updated At' },
            { key: 'completed_at', label: 'Completed At' },
        ],
    },
};
