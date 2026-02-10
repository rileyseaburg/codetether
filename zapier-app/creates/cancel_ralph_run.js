'use strict';

const API_BASE = 'https://api.codetether.io';

const cancelRalphRun = async (z, bundle) => {
    const response = await z.request({
        url: `${API_BASE}/v1/ralph/runs/${bundle.inputData.run_id}/cancel`,
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
    });

    if (response.status === 404) {
        throw new z.errors.Error(
            `Ralph run not found: ${bundle.inputData.run_id}`,
            'RalphRunNotFoundError',
            404
        );
    }

    if (response.status !== 200) {
        throw new z.errors.Error(
            `Failed to cancel Ralph run: ${response.data.detail || response.statusText}`,
            'CancelRalphRunError',
            response.status
        );
    }

    const run = response.data;

    return {
        id: run.id || bundle.inputData.run_id,
        run_id: run.id || bundle.inputData.run_id,
        status: run.status || 'cancelled',
        cancelled: true,
        cancelled_at: new Date().toISOString(),
    };
};

module.exports = {
    key: 'cancel_ralph_run',
    noun: 'Ralph Run',

    display: {
        label: 'Cancel Ralph Run',
        description:
            'Cancel a running Ralph run. The run will stop after the current iteration completes.',
    },

    operation: {
        inputFields: [
            {
                key: 'run_id',
                label: 'Run ID',
                type: 'string',
                required: true,
                helpText: 'The ID of the Ralph run to cancel.',
            },
        ],

        perform: cancelRalphRun,

        sample: {
            id: 'run_abc123',
            run_id: 'run_abc123',
            status: 'cancelled',
            cancelled: true,
            cancelled_at: '2026-02-10T12:00:00Z',
        },

        outputFields: [
            { key: 'id', label: 'ID' },
            { key: 'run_id', label: 'Run ID' },
            { key: 'status', label: 'Status' },
            { key: 'cancelled', label: 'Cancelled', type: 'boolean' },
            { key: 'cancelled_at', label: 'Cancelled At' },
        ],
    },
};
