import {
	IAuthenticateGeneric,
	ICredentialTestRequest,
	ICredentialType,
	INodeProperties,
} from 'n8n-workflow';

export class CodetetherApi implements ICredentialType {
	name = 'codetetherApi';
	displayName = 'CodeTether API';
	documentationUrl = 'https://codetether.io/docs/integrations/n8n';

	properties: INodeProperties[] = [
		{
			displayName: 'API Domain',
			name: 'domain',
			type: 'string',
			default: 'https://api.codetether.io',
			placeholder: 'https://api.codetether.io',
			description: 'CodeTether API base URL. Change for self-hosted instances.',
		},
		{
			displayName: 'API Key',
			name: 'apiKey',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
			description: 'Your CodeTether API key (starts with ct_)',
		},
	];

	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: {
			headers: {
				Authorization: '=Bearer {{$credentials.apiKey}}',
			},
		},
	};

	test: ICredentialTestRequest = {
		request: {
			baseURL: '={{$credentials.domain}}',
			url: '/v1/automation/me',
			method: 'GET',
		},
	};
}
