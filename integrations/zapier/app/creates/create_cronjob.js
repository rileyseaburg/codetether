'use strict';

const API_BASE = 'https://api.codetether.io';

const createCronjob = async (z, bundle) => {
    const body = {
        name: bundle.inputData.name,
        cron_expression: bundle.inputData.cron_expression,
        task_template: bundle.inputData.task_template,
    };

    if (bundle.inputData.description) {
        body.description = bundle.inputData.description;
    }
    if (bundle.inputData.timezone) {
        body.timezone = bundle.inputData.timezone;
    }
    if (bundle.inputData.enabled !== undefined) {
        body.enabled = bundle.inputData.enabled !== 'false';
    }

    const response = await z.request({
        url: `${API_BASE}/v1/cronjobs`,
        method: 'POST',
        body,
        headers: {
            'Content-Type': 'application/json',
        },
    });

    if (response.status !== 200 && response.status !== 201) {
        throw new z.errors.Error(
            `Failed to create cronjob: ${response.data.detail || response.statusText}`,
            'CreateCronjobError',
            response.status
        );
    }

    const job = response.data;

    return {
        id: job.id,
        name: job.name,
        description: job.description,
        cron_expression: job.cron_expression,
        timezone: job.timezone,
        enabled: job.enabled,
        next_run_at: job.next_run_at,
        created_at: job.created_at,
    };
};

module.exports = {
    key: 'create_cronjob',
    noun: 'Cron Job',

    display: {
        label: 'Create Cron Job',
        description:
            'Create a scheduled cron job that automatically triggers tasks on a recurring schedule.',
    },

    operation: {
        inputFields: [
            {
                key: 'name',
                label: 'Name',
                type: 'string',
                required: true,
                helpText: 'A descriptive name for the cron job.',
            },
            {
                key: 'cron_expression',
                label: 'Cron Expression',
                type: 'string',
                required: true,
                helpText:
                    'Standard cron expression (e.g., "0 9 * * 1-5" for weekdays at 9 AM, "*/30 * * * *" for every 30 minutes).',
            },
            {
                key: 'task_template',
                label: 'Task Template',
                type: 'text',
                required: true,
                helpText:
                    'The task message/prompt to run on each schedule. This is the instruction the agent will execute.',
            },
            {
                key: 'description',
                label: 'Description',
                type: 'text',
                required: false,
                helpText: 'Optional description of what this cron job does.',
            },
            {
                key: 'timezone',
                label: 'Timezone',
                type: 'string',
                required: false,
                default: 'UTC',
                helpText: 'Timezone for the cron expression (e.g., "America/New_York", "UTC").',
            },
            {
                key: 'enabled',
                label: 'Enabled',
                type: 'boolean',
                required: false,
                default: 'true',
                helpText: 'Whether the cron job should start enabled.',
            },
        ],

        perform: createCronjob,

        sample: {
            id: 'cj_abc123',
            name: 'Daily Code Review',
            description: 'Run automated code review every morning',
            cron_expression: '0 9 * * 1-5',
            timezone: 'America/New_York',
            enabled: true,
            next_run_at: '2026-02-11T14:00:00Z',
            created_at: '2026-02-10T10:30:00Z',
        },

        outputFields: [
            { key: 'id', label: 'ID' },
            { key: 'name', label: 'Name' },
            { key: 'description', label: 'Description' },
            { key: 'cron_expression', label: 'Cron Expression' },
            { key: 'timezone', label: 'Timezone' },
            { key: 'enabled', label: 'Enabled', type: 'boolean' },
            { key: 'next_run_at', label: 'Next Run At' },
            { key: 'created_at', label: 'Created At' },
        ],
    },
};
