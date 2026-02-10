import {
    IDataObject,
    IExecuteFunctions,
    INodeExecutionData,
    INodeType,
    INodeTypeDescription,
    NodeOperationError,
} from 'n8n-workflow';

export class Codetether implements INodeType {
    description: INodeTypeDescription = {
        displayName: 'CodeTether',
        name: 'codetether',
        icon: 'file:codetether.svg',
        group: ['transform'],
        version: 1,
        subtitle: '={{$parameter["operation"] + ": " + $parameter["resource"]}}',
        description: 'Create, monitor, and manage AI automation tasks with CodeTether',
        defaults: {
            name: 'CodeTether',
        },
        inputs: ['main'],
        outputs: ['main'],
        credentials: [
            {
                name: 'codetetherApi',
                required: true,
            },
        ],
        properties: [
            // ------ Resource ------
            {
                displayName: 'Resource',
                name: 'resource',
                type: 'options',
                noDataExpression: true,
                options: [
                    { name: 'Task', value: 'task' },
                ],
                default: 'task',
            },

            // ------ Operations ------
            {
                displayName: 'Operation',
                name: 'operation',
                type: 'options',
                noDataExpression: true,
                displayOptions: { show: { resource: ['task'] } },
                options: [
                    {
                        name: 'Create',
                        value: 'create',
                        description: 'Create and queue a new AI task',
                        action: 'Create a task',
                    },
                    {
                        name: 'Get',
                        value: 'get',
                        description: 'Get current status of a task',
                        action: 'Get a task',
                    },
                    {
                        name: 'Get Many',
                        value: 'getAll',
                        description: 'List tasks with optional filtering',
                        action: 'Get many tasks',
                    },
                    {
                        name: 'Wait for Completion',
                        value: 'poll',
                        description: 'Poll a task until it finishes (use with Loop node)',
                        action: 'Wait for task completion',
                    },
                    {
                        name: 'Cancel',
                        value: 'cancel',
                        description: 'Cancel a queued or running task',
                        action: 'Cancel a task',
                    },
                ],
                default: 'create',
            },

            // ------ Create fields ------
            {
                displayName: 'Title',
                name: 'title',
                type: 'string',
                default: '',
                required: true,
                displayOptions: { show: { resource: ['task'], operation: ['create'] } },
                description: 'Brief title for the task (max 200 chars)',
                placeholder: 'e.g., Analyze customer feedback',
            },
            {
                displayName: 'Description',
                name: 'description',
                type: 'string',
                typeOptions: { rows: 4 },
                default: '',
                required: true,
                displayOptions: { show: { resource: ['task'], operation: ['create'] } },
                description: 'Full prompt / instructions for the AI agent (10-10000 chars)',
            },
            {
                displayName: 'Additional Fields',
                name: 'additionalFields',
                type: 'collection',
                placeholder: 'Add Field',
                default: {},
                displayOptions: { show: { resource: ['task'], operation: ['create'] } },
                options: [
                    {
                        displayName: 'Agent Type',
                        name: 'agent_type',
                        type: 'options',
                        options: [
                            { name: 'Build', value: 'build' },
                            { name: 'Plan', value: 'plan' },
                            { name: 'General', value: 'general' },
                            { name: 'Explore', value: 'explore' },
                        ],
                        default: 'build',
                        description: 'Type of agent to execute the task',
                    },
                    {
                        displayName: 'Codebase ID',
                        name: 'codebase_id',
                        type: 'string',
                        default: 'global',
                        description: 'Codebase context for the task',
                    },
                    {
                        displayName: 'Model',
                        name: 'model',
                        type: 'options',
                        options: [
                            { name: 'Default', value: 'default' },
                            { name: 'Claude Sonnet 4', value: 'claude-sonnet-4' },
                            { name: 'Claude Opus', value: 'claude-opus' },
                            { name: 'Claude Haiku', value: 'claude-haiku' },
                            { name: 'GPT-4o', value: 'gpt-4o' },
                            { name: 'GPT-4.1', value: 'gpt-4.1' },
                            { name: 'Gemini 2.5 Pro', value: 'gemini-2.5-pro' },
                            { name: 'Gemini 2.5 Flash', value: 'gemini-2.5-flash' },
                            { name: 'Grok 3', value: 'grok-3' },
                            { name: 'MiniMax M2.1', value: 'minimax-m2.1' },
                            { name: 'o3', value: 'o3' },
                            { name: 'o3-mini', value: 'o3-mini' },
                        ],
                        default: 'default',
                        description: 'AI model to use for execution',
                    },
                    {
                        displayName: 'Notify Email',
                        name: 'notify_email',
                        type: 'string',
                        default: '',
                        placeholder: 'user@example.com',
                        description: 'Email address to notify on completion',
                    },
                    {
                        displayName: 'Priority',
                        name: 'priority',
                        type: 'number',
                        typeOptions: { minValue: 0, maxValue: 100 },
                        default: 0,
                        description: 'Priority (0-100, higher = more urgent)',
                    },
                    {
                        displayName: 'Webhook URL',
                        name: 'webhook_url',
                        type: 'string',
                        default: '',
                        placeholder: 'https://your-n8n-instance.com/webhook/...',
                        description: 'URL to receive a POST callback when the task completes',
                    },
                ],
            },

            // ------ Idempotency ------
            {
                displayName: 'Idempotency Key',
                name: 'idempotencyKey',
                type: 'string',
                default: '',
                displayOptions: { show: { resource: ['task'], operation: ['create'] } },
                description: 'Optional unique key to prevent duplicate tasks on retry (e.g., a UUID)',
                placeholder: 'e.g., {{$json.id}}-create',
            },

            // ------ Get / Poll / Cancel fields ------
            {
                displayName: 'Task ID',
                name: 'taskId',
                type: 'string',
                default: '',
                required: true,
                displayOptions: { show: { resource: ['task'], operation: ['get', 'poll', 'cancel'] } },
                description: 'The task ID returned from the Create operation',
            },

            // ------ GetAll fields ------
            {
                displayName: 'Status Filter',
                name: 'statusFilter',
                type: 'options',
                displayOptions: { show: { resource: ['task'], operation: ['getAll'] } },
                options: [
                    { name: 'All', value: '' },
                    { name: 'Queued', value: 'queued' },
                    { name: 'Running', value: 'running' },
                    { name: 'Completed', value: 'completed' },
                    { name: 'Failed', value: 'failed' },
                    { name: 'Cancelled', value: 'cancelled' },
                ],
                default: '',
                description: 'Filter tasks by status',
            },
            {
                displayName: 'Limit',
                name: 'limit',
                type: 'number',
                typeOptions: { minValue: 1, maxValue: 100 },
                default: 50,
                displayOptions: { show: { resource: ['task'], operation: ['getAll'] } },
                description: 'Max number of results to return',
            },
        ],
    };

    async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
        const items = this.getInputData();
        const returnData: INodeExecutionData[] = [];

        const credentials = await this.getCredentials('codetetherApi');
        const baseUrl = (credentials.domain as string).replace(/\/$/, '');

        for (let i = 0; i < items.length; i++) {
            try {
                const resource = this.getNodeParameter('resource', i) as string;
                const operation = this.getNodeParameter('operation', i) as string;

                if (resource === 'task') {
                    if (operation === 'create') {
                        const title = this.getNodeParameter('title', i) as string;
                        const description = this.getNodeParameter('description', i) as string;
                        const additionalFields = this.getNodeParameter('additionalFields', i) as {
                            agent_type?: string;
                            codebase_id?: string;
                            model?: string;
                            notify_email?: string;
                            priority?: number;
                            webhook_url?: string;
                        };
                        const idempotencyKey = this.getNodeParameter('idempotencyKey', i, '') as string;

                        const body: Record<string, unknown> = {
                            title,
                            description,
                            ...additionalFields,
                        };

                        const headers: Record<string, string> = {};
                        if (idempotencyKey) {
                            headers['Idempotency-Key'] = idempotencyKey;
                        }

                        const response = await this.helpers.httpRequestWithAuthentication.call(
                            this,
                            'codetetherApi',
                            {
                                method: 'POST',
                                url: `${baseUrl}/v1/automation/tasks`,
                                body,
                                json: true,
                                headers,
                            },
                        );

                        returnData.push({ json: response as IDataObject });
                    }

                    if (operation === 'get' || operation === 'poll') {
                        const taskId = this.getNodeParameter('taskId', i) as string;

                        const response = await this.helpers.httpRequestWithAuthentication.call(
                            this,
                            'codetetherApi',
                            {
                                method: 'GET',
                                url: `${baseUrl}/v1/automation/tasks/${encodeURIComponent(taskId)}`,
                                json: true,
                            },
                        );

                        const task = response as IDataObject;

                        if (operation === 'poll') {
                            const terminalStates = ['completed', 'failed', 'cancelled'];
                            if (!terminalStates.includes(task.status as string)) {
                                // Return empty to signal "not done yet" for Loop node
                                returnData.push({ json: { _polling: true, status: task.status as string } });
                            } else {
                                returnData.push({ json: task });
                            }
                        } else {
                            returnData.push({ json: task });
                        }
                    }

                    if (operation === 'getAll') {
                        const statusFilter = this.getNodeParameter('statusFilter', i, '') as string;
                        const limit = this.getNodeParameter('limit', i, 50) as number;

                        const qs: Record<string, string | number> = { limit };
                        if (statusFilter) qs.status = statusFilter;

                        const response = await this.helpers.httpRequestWithAuthentication.call(
                            this,
                            'codetetherApi',
                            {
                                method: 'GET',
                                url: `${baseUrl}/v1/automation/tasks`,
                                qs,
                                json: true,
                            },
                        );

                        const respBody = response as { tasks?: IDataObject[] };
                        const tasks = respBody.tasks ?? [];
                        for (const task of tasks) {
                            returnData.push({ json: task });
                        }
                    }

                    if (operation === 'cancel') {
                        const taskId = this.getNodeParameter('taskId', i) as string;

                        await this.helpers.httpRequestWithAuthentication.call(
                            this,
                            'codetetherApi',
                            {
                                method: 'DELETE',
                                url: `${baseUrl}/v1/automation/tasks/${encodeURIComponent(taskId)}`,
                                json: true,
                            },
                        );

                        returnData.push({ json: { task_id: taskId, status: 'cancelled' } });
                    }
                }
            } catch (error) {
                if (this.continueOnFail()) {
                    returnData.push({
                        json: { error: (error as Error).message },
                        pairedItem: { item: i },
                    });
                    continue;
                }
                throw error;
            }
        }

        return [returnData];
    }
}
