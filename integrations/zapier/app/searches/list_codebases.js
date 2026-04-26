'use strict';

const API_BASE = 'https://api.codetether.io';

const listCodebases = async (z, bundle) => {
    const response = await z.request({
        url: `${API_BASE}/v1/codebases`,
        method: 'GET',
    });

    if (response.status !== 200) {
        throw new z.errors.Error(
            `Failed to list codebases: ${response.data.detail || response.statusText}`,
            'ListCodebasesError',
            response.status
        );
    }

    const codebases = response.data.codebases || response.data || [];

    // If filtering by name
    if (bundle.inputData.name) {
        const filtered = codebases.filter(
            (cb) =>
                cb.name &&
                cb.name.toLowerCase().includes(bundle.inputData.name.toLowerCase())
        );
        return filtered.map((cb) => ({
            id: cb.id || cb.codebase_id,
            codebase_id: cb.id || cb.codebase_id,
            name: cb.name,
            path: cb.path,
            description: cb.description,
            worker_id: cb.worker_id,
            status: cb.status,
        }));
    }

    return codebases.map((cb) => ({
        id: cb.id || cb.codebase_id,
        codebase_id: cb.id || cb.codebase_id,
        name: cb.name,
        path: cb.path,
        description: cb.description,
        worker_id: cb.worker_id,
        status: cb.status,
    }));
};

module.exports = {
    key: 'list_codebases',
    noun: 'Codebase',

    display: {
        label: 'Find Codebase',
        description: 'Find registered codebases to target for tasks and Ralph runs.',
    },

    operation: {
        inputFields: [
            {
                key: 'name',
                label: 'Codebase Name',
                type: 'string',
                required: false,
                helpText:
                    'Search for codebases by name (partial match). Leave empty to list all.',
            },
        ],

        perform: listCodebases,

        sample: {
            id: 'cb_abc123',
            codebase_id: 'cb_abc123',
            name: 'marketing-site',
            path: '/home/user/projects/marketing-site',
            description: 'Company marketing website',
            worker_id: 'worker_001',
            status: 'active',
        },

        outputFields: [
            { key: 'id', label: 'ID' },
            { key: 'codebase_id', label: 'Codebase ID' },
            { key: 'name', label: 'Name' },
            { key: 'path', label: 'Path' },
            { key: 'description', label: 'Description' },
            { key: 'worker_id', label: 'Worker ID' },
            { key: 'status', label: 'Status' },
        ],
    },
};
