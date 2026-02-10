'use strict';

const API_BASE = 'https://api.codetether.io';

const listRalphRuns = async (z, bundle) => {
    const params = {};

    if (bundle.inputData.status) {
        params.status = bundle.inputData.status;
    }
    if (bundle.inputData.limit) {
        params.limit = parseInt(bundle.inputData.limit, 10);
    }

    const response = await z.request({
        url: `${API_BASE}/v1/ralph/runs`,
        method: 'GET',
        params,
    });

    if (response.status !== 200) {
        throw new z.errors.Error(
            `Failed to list Ralph runs: ${response.data.detail || response.statusText}`,
            'ListRalphRunsError',
            response.status
        );
    }

    const runs = response.data.runs || response.data || [];

    return runs.map((run) => ({
        id: run.id,
        run_id: run.id,
        project: run.prd ? run.prd.project : null,
        branch: run.prd ? run.prd.branchName : null,
        status: run.status,
        story_count: run.prd ? run.prd.userStories.length : 0,
        current_iteration: run.current_iteration,
        max_iterations: run.max_iterations,
        run_mode: run.run_mode,
        codebase_id: run.codebase_id,
        model: run.model,
        created_at: run.created_at,
        completed_at: run.completed_at,
    }));
};

module.exports = {
    key: 'list_ralph_runs',
    noun: 'Ralph Run',

    display: {
        label: 'Find Ralph Runs',
        description:
            'List Ralph runs, optionally filtered by status. Use to monitor autonomous development progress.',
    },

    operation: {
        inputFields: [
            {
                key: 'status',
                label: 'Status Filter',
                type: 'string',
                choices: ['pending', 'running', 'completed', 'failed', 'cancelled'],
                required: false,
                helpText: 'Only return runs with this status.',
            },
            {
                key: 'limit',
                label: 'Limit',
                type: 'integer',
                required: false,
                default: '20',
                helpText: 'Maximum number of runs to return.',
            },
        ],

        perform: listRalphRuns,

        sample: {
            id: 'run_abc123',
            run_id: 'run_abc123',
            project: 'MyApp',
            branch: 'ralph/new-feature',
            status: 'completed',
            story_count: 3,
            current_iteration: 1,
            max_iterations: 10,
            run_mode: 'sequential',
            codebase_id: null,
            model: 'anthropic:claude-sonnet-4',
            created_at: '2026-02-10T08:00:00Z',
            completed_at: '2026-02-10T08:15:00Z',
        },

        outputFields: [
            { key: 'id', label: 'ID' },
            { key: 'run_id', label: 'Run ID' },
            { key: 'project', label: 'Project' },
            { key: 'branch', label: 'Branch' },
            { key: 'status', label: 'Status' },
            { key: 'story_count', label: 'Story Count' },
            { key: 'current_iteration', label: 'Current Iteration' },
            { key: 'max_iterations', label: 'Max Iterations' },
            { key: 'run_mode', label: 'Run Mode' },
            { key: 'codebase_id', label: 'Codebase ID' },
            { key: 'model', label: 'Model' },
            { key: 'created_at', label: 'Created At' },
            { key: 'completed_at', label: 'Completed At' },
        ],
    },
};
