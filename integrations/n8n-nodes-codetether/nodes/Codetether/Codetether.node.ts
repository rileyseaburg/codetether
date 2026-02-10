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
        description: 'Create AI tasks, generate video ads, and run campaigns with CodeTether',
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
                    { name: 'Video Ad (YouTube)', value: 'videoAd' },
                    { name: 'Video Ad (Facebook)', value: 'facebookVideoAd' },
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
                            { name: 'Claude Opus 4.6', value: 'claude-opus-4-6' },
                            { name: 'Claude Opus 4.5', value: 'claude-opus-4-5' },
                            { name: 'Claude Sonnet 4', value: 'claude-sonnet-4' },
                            { name: 'Claude Haiku', value: 'claude-haiku' },
                            { name: 'GPT-5.2', value: 'gpt-5.2' },
                            { name: 'GPT-4.1', value: 'gpt-4.1' },
                            { name: 'GPT-4.1 Mini', value: 'gpt-4.1-mini' },
                            { name: 'Gemini 3 Pro', value: 'gemini-3-pro' },
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

            // ====== Video Ad Operations ======
            {
                displayName: 'Operation',
                name: 'operation',
                type: 'options',
                noDataExpression: true,
                displayOptions: { show: { resource: ['videoAd'] } },
                options: [
                    {
                        name: 'Generate',
                        value: 'generate',
                        description: 'Generate a video ad with Creatify AI',
                        action: 'Generate a video ad',
                    },
                    {
                        name: 'Generate and Launch',
                        value: 'generateAndLaunch',
                        description: 'Generate video → upload to YouTube → create Google Ads campaign',
                        action: 'Generate and launch a video ad',
                    },
                    {
                        name: 'Check Status',
                        value: 'checkStatus',
                        description: 'Check Creatify video generation status',
                        action: 'Check video generation status',
                    },
                    {
                        name: 'Launch',
                        value: 'launch',
                        description: 'Launch a Google Ads campaign from an existing YouTube video',
                        action: 'Launch video ad campaign',
                    },
                    {
                        name: 'Report',
                        value: 'report',
                        description: 'Get video campaign performance metrics',
                        action: 'Get video ad report',
                    },
                    {
                        name: 'Credits',
                        value: 'credits',
                        description: 'Check remaining Creatify credits',
                        action: 'Check video credits',
                    },
                ],
                default: 'generate',
            },

            // ------ Generate / GenerateAndLaunch fields ------
            {
                displayName: 'Video Source',
                name: 'videoSource',
                type: 'options',
                displayOptions: { show: { resource: ['videoAd'], operation: ['generate', 'generateAndLaunch'] } },
                options: [
                    { name: 'CodeTether Pre-built Script', value: 'script' },
                    { name: 'Custom URL', value: 'url' },
                ],
                default: 'script',
                description: 'Generate from a pre-built CodeTether script or a custom URL',
            },
            {
                displayName: 'Script Style',
                name: 'scriptStyle',
                type: 'options',
                displayOptions: { show: { resource: ['videoAd'], operation: ['generate', 'generateAndLaunch'], videoSource: ['script'] } },
                options: [
                    { name: 'Problem Focused', value: 'problem_focused' },
                    { name: 'Result Focused', value: 'result_focused' },
                    { name: 'Comparison', value: 'comparison' },
                ],
                default: 'problem_focused',
                description: 'Pre-written ad script style',
            },
            {
                displayName: 'URL',
                name: 'videoUrl',
                type: 'string',
                default: '',
                required: true,
                displayOptions: { show: { resource: ['videoAd'], operation: ['generate', 'generateAndLaunch'], videoSource: ['url'] } },
                description: 'Product or landing page URL to generate video from',
                placeholder: 'https://codetether.io',
            },
            {
                displayName: 'Custom Script',
                name: 'videoScript',
                type: 'string',
                typeOptions: { rows: 4 },
                default: '',
                displayOptions: { show: { resource: ['videoAd'], operation: ['generate', 'generateAndLaunch'], videoSource: ['url'] } },
                description: 'Optional custom script for the video narration',
            },
            {
                displayName: 'Aspect Ratio',
                name: 'aspectRatio',
                type: 'options',
                displayOptions: { show: { resource: ['videoAd'], operation: ['generate', 'generateAndLaunch'] } },
                options: [
                    { name: '16:9 (YouTube / Horizontal)', value: '16:9' },
                    { name: '9:16 (Stories / Vertical)', value: '9:16' },
                    { name: '1:1 (Square)', value: '1:1' },
                ],
                default: '16:9',
                description: 'Video aspect ratio',
            },

            // ------ Launch-specific fields ------
            {
                displayName: 'YouTube Video ID',
                name: 'youtubeVideoId',
                type: 'string',
                default: '',
                required: true,
                displayOptions: { show: { resource: ['videoAd'], operation: ['launch'] } },
                description: 'YouTube video ID (e.g., dQw4w9WgXcQ)',
            },

            // ------ Campaign fields (launch + generateAndLaunch) ------
            {
                displayName: 'Campaign Options',
                name: 'campaignOptions',
                type: 'collection',
                placeholder: 'Add Option',
                default: {},
                displayOptions: { show: { resource: ['videoAd'], operation: ['launch', 'generateAndLaunch'] } },
                options: [
                    {
                        displayName: 'Campaign Name',
                        name: 'campaignName',
                        type: 'string',
                        default: '',
                        description: 'Name for the Google Ads campaign',
                    },
                    {
                        displayName: 'Daily Budget ($)',
                        name: 'dailyBudgetDollars',
                        type: 'number',
                        typeOptions: { minValue: 1 },
                        default: 25,
                        description: 'Daily budget in dollars',
                    },
                    {
                        displayName: 'Ad Type',
                        name: 'adType',
                        type: 'options',
                        options: [
                            { name: 'In-Stream (Skippable)', value: 'IN_STREAM' },
                            { name: 'Bumper (6s Non-Skippable)', value: 'BUMPER' },
                        ],
                        default: 'IN_STREAM',
                        description: 'Video ad format',
                    },
                    {
                        displayName: 'Final URL',
                        name: 'finalUrl',
                        type: 'string',
                        default: 'https://codetether.run',
                        description: 'Landing page URL when viewer clicks',
                    },
                    {
                        displayName: 'Headline',
                        name: 'headline',
                        type: 'string',
                        default: 'AI Agents That Actually Deliver',
                        description: 'Ad headline text',
                    },
                    {
                        displayName: 'Call to Action',
                        name: 'callToAction',
                        type: 'string',
                        default: 'Start Free',
                        description: 'CTA button text',
                    },
                ],
            },

            // ------ Check Status field ------
            {
                displayName: 'Creatify Video ID',
                name: 'creatifyVideoId',
                type: 'string',
                default: '',
                required: true,
                displayOptions: { show: { resource: ['videoAd'], operation: ['checkStatus'] } },
                description: 'The Creatify video ID returned from the Generate operation',
            },

            // ------ Report fields ------
            {
                displayName: 'Report Days',
                name: 'reportDays',
                type: 'number',
                typeOptions: { minValue: 1, maxValue: 365 },
                default: 30,
                displayOptions: { show: { resource: ['videoAd', 'facebookVideoAd'], operation: ['report'] } },
                description: 'Number of days to include in the report',
            },

            // ====== Facebook Video Ad Operations ======
            {
                displayName: 'Operation',
                name: 'operation',
                type: 'options',
                noDataExpression: true,
                displayOptions: { show: { resource: ['facebookVideoAd'] } },
                options: [
                    {
                        name: 'Generate and Launch',
                        value: 'generateAndLaunch',
                        description: 'Generate video with Creatify → upload to Facebook → create campaign',
                        action: 'Generate and launch Facebook video ad',
                    },
                    {
                        name: 'Launch',
                        value: 'launch',
                        description: 'Upload existing video URL to Facebook and create campaign',
                        action: 'Launch Facebook video ad',
                    },
                    {
                        name: 'Check Video Status',
                        value: 'checkVideo',
                        description: 'Check Facebook video processing status',
                        action: 'Check Facebook video status',
                    },
                    {
                        name: 'Report',
                        value: 'report',
                        description: 'Get Facebook video campaign performance',
                        action: 'Get Facebook video report',
                    },
                    {
                        name: 'List Campaigns',
                        value: 'listCampaigns',
                        description: 'List Facebook ad campaigns',
                        action: 'List Facebook campaigns',
                    },
                ],
                default: 'generateAndLaunch',
            },

            // ------ Facebook Generate fields ------
            {
                displayName: 'Video Source',
                name: 'fbVideoSource',
                type: 'options',
                displayOptions: { show: { resource: ['facebookVideoAd'], operation: ['generateAndLaunch'] } },
                options: [
                    { name: 'CodeTether Pre-built Script', value: 'script' },
                    { name: 'Custom URL', value: 'url' },
                    { name: 'Existing Video URL', value: 'existing' },
                ],
                default: 'script',
                description: 'How to source the video',
            },
            {
                displayName: 'Script Style',
                name: 'fbScriptStyle',
                type: 'options',
                displayOptions: { show: { resource: ['facebookVideoAd'], operation: ['generateAndLaunch'], fbVideoSource: ['script'] } },
                options: [
                    { name: 'Problem Focused', value: 'problem_focused' },
                    { name: 'Result Focused', value: 'result_focused' },
                    { name: 'Comparison', value: 'comparison' },
                ],
                default: 'problem_focused',
            },
            {
                displayName: 'URL',
                name: 'fbUrl',
                type: 'string',
                default: '',
                required: true,
                displayOptions: { show: { resource: ['facebookVideoAd'], operation: ['generateAndLaunch'], fbVideoSource: ['url'] } },
                description: 'Product URL to generate video from',
                placeholder: 'https://codetether.io',
            },
            {
                displayName: 'Video URL',
                name: 'fbExistingVideoUrl',
                type: 'string',
                default: '',
                required: true,
                displayOptions: { show: { resource: ['facebookVideoAd'], operation: ['generateAndLaunch'], fbVideoSource: ['existing'] } },
                description: 'Direct URL to an existing video file',
            },

            // ------ Facebook Launch fields ------
            {
                displayName: 'Video URL',
                name: 'fbVideoUrl',
                type: 'string',
                default: '',
                required: true,
                displayOptions: { show: { resource: ['facebookVideoAd'], operation: ['launch'] } },
                description: 'Public URL to the video file to upload to Facebook',
            },

            // ------ Facebook Campaign Options ------
            {
                displayName: 'Campaign Options',
                name: 'fbCampaignOptions',
                type: 'collection',
                placeholder: 'Add Option',
                default: {},
                displayOptions: { show: { resource: ['facebookVideoAd'], operation: ['launch', 'generateAndLaunch'] } },
                options: [
                    {
                        displayName: 'Campaign Name',
                        name: 'campaignName',
                        type: 'string',
                        default: '',
                        description: 'Name for the Facebook campaign',
                    },
                    {
                        displayName: 'Daily Budget ($)',
                        name: 'dailyBudgetDollars',
                        type: 'number',
                        typeOptions: { minValue: 1 },
                        default: 25,
                        description: 'Daily budget in dollars',
                    },
                    {
                        displayName: 'Landing URL',
                        name: 'landingUrl',
                        type: 'string',
                        default: 'https://codetether.run',
                        description: 'Landing page URL',
                    },
                    {
                        displayName: 'Ad Message',
                        name: 'message',
                        type: 'string',
                        typeOptions: { rows: 3 },
                        default: '',
                        description: 'Primary text for the ad post',
                    },
                    {
                        displayName: 'Headline',
                        name: 'headline',
                        type: 'string',
                        default: 'AI Agents That Actually Deliver',
                        description: 'Ad headline',
                    },
                    {
                        displayName: 'CTA Type',
                        name: 'ctaType',
                        type: 'options',
                        options: [
                            { name: 'Learn More', value: 'LEARN_MORE' },
                            { name: 'Sign Up', value: 'SIGN_UP' },
                            { name: 'Get Started', value: 'GET_STARTED' },
                            { name: 'Try It Now', value: 'TRY_IT' },
                        ],
                        default: 'LEARN_MORE',
                        description: 'Call-to-action button type',
                    },
                ],
            },

            // ------ Facebook Check Video field ------
            {
                displayName: 'Facebook Video ID',
                name: 'facebookVideoId',
                type: 'string',
                default: '',
                required: true,
                displayOptions: { show: { resource: ['facebookVideoAd'], operation: ['checkVideo'] } },
                description: 'Facebook video ID to check processing status',
            },

            // ------ Facebook Aspect Ratio ------
            {
                displayName: 'Aspect Ratio',
                name: 'fbAspectRatio',
                type: 'options',
                displayOptions: { show: { resource: ['facebookVideoAd'], operation: ['generateAndLaunch'], fbVideoSource: ['script', 'url'] } },
                options: [
                    { name: '1:1 (Square / Feed)', value: '1:1' },
                    { name: '9:16 (Stories / Reels)', value: '9:16' },
                    { name: '16:9 (Horizontal)', value: '16:9' },
                ],
                default: '1:1',
                description: 'Video aspect ratio (1:1 recommended for Facebook)',
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

                if (resource === 'videoAd') {
                    // Video pipeline endpoint
                    const pipelineUrl = `${baseUrl.replace(/\/v1\/.*$/, '')}/api/google/video-pipeline`;

                    if (operation === 'generate' || operation === 'generateAndLaunch') {
                        const videoSource = this.getNodeParameter('videoSource', i) as string;
                        const aspectRatio = this.getNodeParameter('aspectRatio', i, '16:9') as string;

                        const pipelineBody: Record<string, unknown> = {
                            action: operation === 'generateAndLaunch' ? 'generate_and_launch' : 'generate',
                            aspectRatio,
                        };

                        if (videoSource === 'script') {
                            pipelineBody.scriptStyle = this.getNodeParameter('scriptStyle', i, 'problem_focused') as string;
                        } else {
                            pipelineBody.url = this.getNodeParameter('videoUrl', i) as string;
                            const script = this.getNodeParameter('videoScript', i, '') as string;
                            if (script) pipelineBody.script = script;
                        }

                        if (operation === 'generateAndLaunch') {
                            const campaignOptions = this.getNodeParameter('campaignOptions', i, {}) as Record<string, unknown>;
                            Object.assign(pipelineBody, campaignOptions);
                        }

                        const response = await this.helpers.httpRequestWithAuthentication.call(
                            this,
                            'codetetherApi',
                            {
                                method: 'POST',
                                url: pipelineUrl,
                                body: pipelineBody,
                                json: true,
                            },
                        );

                        returnData.push({ json: response as IDataObject });
                    }

                    if (operation === 'checkStatus') {
                        const creatifyVideoId = this.getNodeParameter('creatifyVideoId', i) as string;

                        const response = await this.helpers.httpRequestWithAuthentication.call(
                            this,
                            'codetetherApi',
                            {
                                method: 'POST',
                                url: pipelineUrl,
                                body: { action: 'check_status', creatifyVideoId },
                                json: true,
                            },
                        );

                        returnData.push({ json: response as IDataObject });
                    }

                    if (operation === 'launch') {
                        const youtubeVideoId = this.getNodeParameter('youtubeVideoId', i) as string;
                        const campaignOptions = this.getNodeParameter('campaignOptions', i, {}) as Record<string, unknown>;

                        const response = await this.helpers.httpRequestWithAuthentication.call(
                            this,
                            'codetetherApi',
                            {
                                method: 'POST',
                                url: pipelineUrl,
                                body: { action: 'launch', youtubeVideoId, ...campaignOptions },
                                json: true,
                            },
                        );

                        returnData.push({ json: response as IDataObject });
                    }

                    if (operation === 'report') {
                        const days = this.getNodeParameter('reportDays', i, 30) as number;

                        const response = await this.helpers.httpRequestWithAuthentication.call(
                            this,
                            'codetetherApi',
                            {
                                method: 'POST',
                                url: pipelineUrl,
                                body: { action: 'report', days },
                                json: true,
                            },
                        );

                        returnData.push({ json: response as IDataObject });
                    }

                    if (operation === 'credits') {
                        const response = await this.helpers.httpRequestWithAuthentication.call(
                            this,
                            'codetetherApi',
                            {
                                method: 'POST',
                                url: pipelineUrl,
                                body: { action: 'credits' },
                                json: true,
                            },
                        );

                        returnData.push({ json: response as IDataObject });
                    }
                }

                if (resource === 'facebookVideoAd') {
                    const fbPipelineUrl = `${baseUrl.replace(/\/v1\/.*$/, '')}/api/facebook/video-pipeline`;

                    if (operation === 'generateAndLaunch') {
                        const videoSource = this.getNodeParameter('fbVideoSource', i) as string;
                        const fbBody: Record<string, unknown> = { action: 'generate_and_launch' };

                        if (videoSource === 'script') {
                            fbBody.scriptStyle = this.getNodeParameter('fbScriptStyle', i, 'problem_focused') as string;
                            fbBody.aspectRatio = this.getNodeParameter('fbAspectRatio', i, '1:1') as string;
                        } else if (videoSource === 'url') {
                            fbBody.url = this.getNodeParameter('fbUrl', i) as string;
                            fbBody.aspectRatio = this.getNodeParameter('fbAspectRatio', i, '1:1') as string;
                        } else {
                            fbBody.creatifyVideoUrl = this.getNodeParameter('fbExistingVideoUrl', i) as string;
                        }

                        const campaignOptions = this.getNodeParameter('fbCampaignOptions', i, {}) as Record<string, unknown>;
                        Object.assign(fbBody, campaignOptions);

                        const response = await this.helpers.httpRequestWithAuthentication.call(
                            this,
                            'codetetherApi',
                            { method: 'POST', url: fbPipelineUrl, body: fbBody, json: true },
                        );
                        returnData.push({ json: response as IDataObject });
                    }

                    if (operation === 'launch') {
                        const videoUrl = this.getNodeParameter('fbVideoUrl', i) as string;
                        const campaignOptions = this.getNodeParameter('fbCampaignOptions', i, {}) as Record<string, unknown>;

                        const response = await this.helpers.httpRequestWithAuthentication.call(
                            this,
                            'codetetherApi',
                            {
                                method: 'POST',
                                url: fbPipelineUrl,
                                body: { action: 'launch', videoUrl, ...campaignOptions },
                                json: true,
                            },
                        );
                        returnData.push({ json: response as IDataObject });
                    }

                    if (operation === 'checkVideo') {
                        const facebookVideoId = this.getNodeParameter('facebookVideoId', i) as string;

                        const response = await this.helpers.httpRequestWithAuthentication.call(
                            this,
                            'codetetherApi',
                            {
                                method: 'POST',
                                url: fbPipelineUrl,
                                body: { action: 'check_video', facebookVideoId },
                                json: true,
                            },
                        );
                        returnData.push({ json: response as IDataObject });
                    }

                    if (operation === 'report') {
                        const days = this.getNodeParameter('reportDays', i, 30) as number;

                        const response = await this.helpers.httpRequestWithAuthentication.call(
                            this,
                            'codetetherApi',
                            {
                                method: 'POST',
                                url: fbPipelineUrl,
                                body: { action: 'report', days },
                                json: true,
                            },
                        );
                        returnData.push({ json: response as IDataObject });
                    }

                    if (operation === 'listCampaigns') {
                        const response = await this.helpers.httpRequestWithAuthentication.call(
                            this,
                            'codetetherApi',
                            {
                                method: 'POST',
                                url: fbPipelineUrl,
                                body: { action: 'list' },
                                json: true,
                            },
                        );
                        returnData.push({ json: response as IDataObject });
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
