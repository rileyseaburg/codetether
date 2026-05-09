'use strict';

const API_BASE = 'https://api.codetether.io';

const discoverAgents = async (z, bundle) => {
    const response = await z.request({
        url: `${API_BASE}/v1/agents`,
        method: 'GET',
    });

    if (response.status !== 200) {
        throw new z.errors.Error(
            `Failed to discover agents: ${response.data.detail || response.statusText}`,
            'DiscoverAgentsError',
            response.status
        );
    }

    const agents = response.data.agents || response.data || [];

    // If filtering by name
    if (bundle.inputData.name) {
        const filtered = agents.filter(
            (a) =>
                a.name &&
                a.name.toLowerCase().includes(bundle.inputData.name.toLowerCase())
        );
        return filtered.map((agent) => ({
            id: agent.name,
            name: agent.name,
            description: agent.description,
            url: agent.url,
            streaming: agent.capabilities ? agent.capabilities.streaming : false,
            push_notifications: agent.capabilities
                ? agent.capabilities.push_notifications
                : false,
            models_supported: agent.models_supported
                ? agent.models_supported.join(', ')
                : '',
            last_seen: agent.last_seen,
        }));
    }

    return agents.map((agent) => ({
        id: agent.name,
        name: agent.name,
        description: agent.description,
        url: agent.url,
        streaming: agent.capabilities ? agent.capabilities.streaming : false,
        push_notifications: agent.capabilities
            ? agent.capabilities.push_notifications
            : false,
        models_supported: agent.models_supported
            ? agent.models_supported.join(', ')
            : '',
        last_seen: agent.last_seen,
    }));
};

module.exports = {
    key: 'discover_agents',
    noun: 'Agent',

    display: {
        label: 'Find Agent',
        description: 'Find registered worker agents in the network.',
    },

    operation: {
        inputFields: [
            {
                key: 'name',
                label: 'Agent Name',
                type: 'string',
                required: false,
                helpText:
                    'Search for agents by name (partial match). Leave empty to list all.',
            },
        ],

        perform: discoverAgents,

        sample: {
            id: 'codetether-builder',
            name: 'codetether-builder',
            description: 'CodeTether build agent for autonomous development',
            url: 'https://agent.codetether.io',
            streaming: true,
            push_notifications: false,
            models_supported: 'anthropic:claude-sonnet-4, openai:gpt-4.1',
            last_seen: '2026-02-10T10:30:00Z',
        },

        outputFields: [
            { key: 'id', label: 'ID' },
            { key: 'name', label: 'Name' },
            { key: 'description', label: 'Description' },
            { key: 'url', label: 'URL' },
            { key: 'streaming', label: 'Supports Streaming', type: 'boolean' },
            {
                key: 'push_notifications',
                label: 'Push Notifications',
                type: 'boolean',
            },
            { key: 'models_supported', label: 'Models Supported' },
            { key: 'last_seen', label: 'Last Seen' },
        ],
    },
};
