'use strict';

const API_BASE = 'https://api.codetether.io';

const listModels = async (z, bundle) => {
    const params = {};

    if (bundle.inputData.provider) {
        params.provider = bundle.inputData.provider;
    }
    if (bundle.inputData.search) {
        params.search = bundle.inputData.search;
    }

    const response = await z.request({
        url: `${API_BASE}/v1/models`,
        method: 'GET',
        params,
    });

    if (response.status !== 200) {
        throw new z.errors.Error(
            `Failed to list models: ${response.data.detail || response.statusText}`,
            'ListModelsError',
            response.status
        );
    }

    const models = response.data.models || response.data || [];

    return models.map((model, index) => ({
        id: model.model_ref || model.id || `model_${index}`,
        model_ref: model.model_ref,
        name: model.name || model.friendly_name,
        provider: model.provider,
        workers_available: model.workers_available || 0,
        worker_names: model.worker_names
            ? model.worker_names.join(', ')
            : '',
    }));
};

module.exports = {
    key: 'list_models',
    noun: 'AI Model',

    display: {
        label: 'Find AI Models',
        description:
            'List available AI models from registered workers. Use to discover which models you can select for tasks.',
    },

    operation: {
        inputFields: [
            {
                key: 'provider',
                label: 'Provider',
                type: 'string',
                choices: [
                    'anthropic',
                    'openai',
                    'google',
                    'openrouter',
                    'minimax',
                    'xai',
                ],
                required: false,
                helpText: 'Filter models by provider. Leave empty to list all.',
            },
            {
                key: 'search',
                label: 'Search',
                type: 'string',
                required: false,
                helpText:
                    'Filter models by name (case-insensitive substring match).',
            },
        ],

        perform: listModels,

        sample: {
            id: 'anthropic:claude-sonnet-4',
            model_ref: 'anthropic:claude-sonnet-4',
            name: 'Claude Sonnet 4',
            provider: 'anthropic',
            workers_available: 2,
            worker_names: 'codetether-builder, codetether-reviewer',
        },

        outputFields: [
            { key: 'id', label: 'ID' },
            { key: 'model_ref', label: 'Model Reference' },
            { key: 'name', label: 'Name' },
            { key: 'provider', label: 'Provider' },
            { key: 'workers_available', label: 'Workers Available' },
            { key: 'worker_names', label: 'Worker Names' },
        ],
    },
};
