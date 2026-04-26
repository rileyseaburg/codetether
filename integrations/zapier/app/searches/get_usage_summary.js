'use strict';

const API_BASE = 'https://api.codetether.io';

const getUsageSummary = async (z, bundle) => {
    const params = {};

    if (bundle.inputData.month) {
        params.month = bundle.inputData.month;
    }

    const response = await z.request({
        url: `${API_BASE}/v1/billing/usage/summary`,
        method: 'GET',
        params,
    });

    if (response.status !== 200) {
        throw new z.errors.Error(
            `Failed to get usage summary: ${response.data.detail || response.statusText}`,
            'GetUsageSummaryError',
            response.status
        );
    }

    const data = response.data;

    return [
        {
            id: data.month || new Date().toISOString().slice(0, 7),
            month: data.month,
            total_tokens: data.total_tokens || 0,
            input_tokens: data.input_tokens || 0,
            output_tokens: data.output_tokens || 0,
            total_cost: data.total_cost || 0,
            total_requests: data.total_requests || 0,
            budget_remaining: data.budget_remaining,
            spending_limit: data.spending_limit,
        },
    ];
};

module.exports = {
    key: 'get_usage_summary',
    noun: 'Usage Summary',

    display: {
        label: 'Get Token Usage Summary',
        description:
            'Get aggregated token usage and billing summary for the current month or a specific month.',
    },

    operation: {
        inputFields: [
            {
                key: 'month',
                label: 'Month',
                type: 'string',
                required: false,
                helpText:
                    'Month as YYYY-MM (e.g., "2026-02"). Defaults to current month.',
            },
        ],

        perform: getUsageSummary,

        sample: {
            id: '2026-02',
            month: '2026-02',
            total_tokens: 1250000,
            input_tokens: 950000,
            output_tokens: 300000,
            total_cost: 4.25,
            total_requests: 142,
            budget_remaining: 45.75,
            spending_limit: 50.0,
        },

        outputFields: [
            { key: 'id', label: 'ID' },
            { key: 'month', label: 'Month' },
            { key: 'total_tokens', label: 'Total Tokens' },
            { key: 'input_tokens', label: 'Input Tokens' },
            { key: 'output_tokens', label: 'Output Tokens' },
            { key: 'total_cost', label: 'Total Cost ($)' },
            { key: 'total_requests', label: 'Total Requests' },
            { key: 'budget_remaining', label: 'Budget Remaining ($)' },
            { key: 'spending_limit', label: 'Spending Limit ($)' },
        ],
    },
};
