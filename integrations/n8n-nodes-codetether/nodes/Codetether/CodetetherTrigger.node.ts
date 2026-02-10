import {
    IDataObject,
    IHookFunctions,
    IWebhookFunctions,
    INodeType,
    INodeTypeDescription,
    IWebhookResponseData,
} from 'n8n-workflow';

export class CodetetherTrigger implements INodeType {
    description: INodeTypeDescription = {
        displayName: 'CodeTether Trigger',
        name: 'codetetherTrigger',
        icon: 'file:codetether.svg',
        group: ['trigger'],
        version: 1,
        subtitle: '=on {{$parameter["event"]}}',
        description: 'Starts a workflow when a CodeTether task event occurs',
        defaults: {
            name: 'CodeTether Trigger',
        },
        inputs: [],
        outputs: ['main'],
        credentials: [
            {
                name: 'codetetherApi',
                required: false,
            },
        ],
        webhooks: [
            {
                name: 'default',
                httpMethod: 'POST',
                responseMode: 'onReceived',
                path: 'codetether',
            },
        ],
        properties: [
            {
                displayName: 'Event',
                name: 'event',
                type: 'options',
                options: [
                    {
                        name: 'Task Completed',
                        value: 'task_completed',
                        description: 'Triggers when a task finishes successfully',
                    },
                    {
                        name: 'Task Failed',
                        value: 'task_failed',
                        description: 'Triggers when a task fails',
                    },
                    {
                        name: 'Task Started',
                        value: 'task_started',
                        description: 'Triggers when a task begins execution',
                    },
                    {
                        name: 'Any Event',
                        value: 'any',
                        description: 'Triggers on any task event',
                    },
                ],
                default: 'task_completed',
                description: 'Which event to listen for',
            },
            {
                displayName: 'Verify Signature',
                name: 'verifySignature',
                type: 'boolean',
                default: false,
                description: 'Whether to verify the X-CodeTether-Signature HMAC header',
            },
            {
                displayName: 'Webhook Secret',
                name: 'webhookSecret',
                type: 'string',
                typeOptions: { password: true },
                default: '',
                displayOptions: { show: { verifySignature: [true] } },
                description: 'HMAC secret for verifying webhook signatures',
            },
        ],
    };

    webhookMethods = {
        default: {
            async checkExists(this: IHookFunctions): Promise<boolean> {
                // Webhook is always available via n8n's webhook URL
                return true;
            },
            async create(this: IHookFunctions): Promise<boolean> {
                return true;
            },
            async delete(this: IHookFunctions): Promise<boolean> {
                return true;
            },
        },
    };

    async webhook(this: IWebhookFunctions): Promise<IWebhookResponseData> {
        const req = this.getRequestObject();
        const body = this.getBodyData() as IDataObject;

        // Filter by event type if not "any"
        const expectedEvent = this.getNodeParameter('event') as string;
        const receivedEvent = body.event as string | undefined;

        if (expectedEvent !== 'any' && receivedEvent !== expectedEvent) {
            // Acknowledge but don't trigger the workflow
            return { noWebhookResponse: true };
        }

        // Verify HMAC signature if enabled
        const verifySignature = this.getNodeParameter('verifySignature', false) as boolean;
        if (verifySignature) {
            const secret = this.getNodeParameter('webhookSecret', '') as string;
            const signature = req.headers['x-codetether-signature'] as string | undefined;

            if (!signature || !secret) {
                return { noWebhookResponse: true };
            }

            const crypto = require('crypto');
            const rawBody = JSON.stringify(body);
            const expected = 'sha256=' + crypto.createHmac('sha256', secret).update(rawBody).digest('hex');

            if (!crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(expected))) {
                return { noWebhookResponse: true };
            }
        }

        return {
            workflowData: [
                this.helpers.returnJsonArray(body as IDataObject),
            ],
        };
    }
}
