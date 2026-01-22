# Zapier App Manifest for CodeTether

Comprehensive Zapier platform app following Zapier best practices for create, search, and delete actions.

## Quick Start

```bash
npm install -g zapier-platform-cli
zapier init codetether-app
cd codetether-app
zapier push
zapier promote
```

## Authentication

Uses API key (Bearer token starting with `ct_`) for quick setup.

**Alternative:** OAuth 2.0 for production integrations.

## Best Practices Followed

1. ✅ Create actions return objects with individual fields
2. ✅ Search actions return sorted arrays  
3. ✅ Delete actions include Copy field for irreversible operations
4. ✅ 4xx errors returned directly, 2xx fixed in API layer
5. ✅ Support for dynamic domain (self-hosted instances)
6. ✅ poll_task action for Looping by Zapier

## Project Structure

```
codetether-app/
├── index.js                 # Main app entry point
├── package.json             # App metadata
├── creates/
│   └── create_task.js      # Create task action
├── searches/
│   ├── get_task_status.js    # Search for task by ID
│   ├── get_task_list.js      # Search for list of tasks
│   └── poll_task.js         # Poll task until complete
└── deletes/
    └── cancel_task.js      # Cancel task action
```

## index.js

```javascript
const getTaskStatus = require('./searches/get_task_status');
const getTaskList = require('./searches/get_task_list');
const pollTask = require('./searches/poll_task');
const createTask = require('./creates/create_task');
const cancelTask = require('./deletes/cancel_task');

module.exports = {
  version: require('./package.json').version,
  platformVersion: require('zapier-platform-core').version,

  authentication: {
    type: 'session',
    test: {
      url: 'https://{{bundle.authData.domain}}/v1/automation',
    },
    fields: [
      {
        key: 'domain',
        label: 'API Domain',
        type: 'string',
        required: false,
        default: 'https://api.codetether.io'
      },
      {
        key: 'apiKey',
        label: 'API Key',
        type: 'password',
        required: true
      }
    ]
  },

  beforeRequest: [
    (request, z, bundle) => {
      request.headers.Authorization = `Bearer ${bundle.authData.apiKey}`;
      return request;
    }
  ],

  searches: {
    get_task_status: getTaskStatus,
    get_task_list: getTaskList,
    poll_task: pollTask
  },

  creates: {
    create_task: createTask
  },

  deletes: {
    cancel_task: cancelTask
  }
};
```

## creates/create_task.js

Returns object with individual fields (Zapier best practice).

```javascript
module.exports = {
  key: 'create_task',
  noun: 'Task',
  display: {
    label: 'Create Task',
    description: 'Create a new AI automation task in CodeTether'
  },
  operation: {
    inputFields: [
      {
        key: 'title',
        label: 'Title',
        type: 'string',
        required: true,
        helpText: 'Brief title (max 200 chars)',
        placeholder: 'e.g., Analyze customer feedback'
      },
      {
        key: 'description',
        label: 'Description',
        type: 'text',
        required: true,
        helpText: 'Task prompt for AI (max 10000 chars)'
      },
      {
        key: 'codebase_id',
        label: 'Codebase ID',
        type: 'string',
        required: false,
        default: 'global',
        helpText: 'For codebase parameter'
      },
      {
        key: 'agent_type',
        label: 'Agent Type',
        type: 'string',
        required: false,
        choices: ['build', 'plan', 'general', 'explore'],
        default: 'general'
      },
      {
        key: 'model',
        label: 'Model',
        type: 'string',
        required: false,
        choices: ['claude-sonnet', 'gpt-4o', 'gemini-2.5-pro'],
        default: 'claude-sonnet'
      },
      {
        key: 'priority',
        label: 'Priority',
        type: 'integer',
        required: false,
        default: 0,
        min: 0,
        max: 100
      },
      {
        key: 'webhook_url',
        label: 'Webhook URL',
        type: 'string',
        required: false
      }
    ],
    perform: (z, bundle) => {
      const data = {
        title: bundle.inputData.title,
        description: bundle.inputData.description,
        codebase_id: bundle.inputData.codebase_id || 'global',
        agent_type: bundle.inputData.agent_type || 'general',
        model: bundle.inputData.model || 'claude-sonnet',
        priority: bundle.inputData.priority || 0
      };
      if (bundle.inputData.webhook_url) data.webhook_url = bundle.inputData.webhook_url;

      return z.request({
        method: 'POST',
        url: `https://{{bundle.authData.domain}}/v1/automation/tasks`,
        json: data
      }).then((response) => {
        const result = response.json;
        return {
          task_id: result.task_id,
          run_id: result.run_id,
          status: result.status,
          title: result.title,
          created_at: result.created_at,
          model: result.model
        };
      });
    }
  }
};
```

## searches/get_task_status.js

Search action returns single task object.

```javascript
module.exports = {
  key: 'get_task_status',
  noun: 'Task Status',
  display: {
    label: 'Get Task Status',
    description: 'Get current status of a specific task'
  },
  operation: {
    inputFields: [
      {
        key: 'task_id',
        label: 'Task ID',
        type: 'string',
        required: true
      }
    ],
    perform: (z, bundle) => {
      return z.request({
        url: `https://{{bundle.authData.domain}}/v1/automation/tasks/${bundle.inputData.task_id}`
      }).then((response) => {
        return response.json;
      });
    }
  }
};
```

## searches/get_task_list.js

Search action returns sorted array.

```javascript
module.exports = {
  key: 'get_task_list',
  noun: 'Tasks',
  display: {
    label: 'List Tasks',
    description: 'List tasks with optional filtering by status'
  },
  operation: {
    inputFields: [
      {
        key: 'status',
        label: 'Status Filter',
        type: 'string',
        required: false,
        choices: ['queued', 'running', 'completed', 'failed']
      },
      {
        key: 'limit',
        label: 'Limit',
        type: 'integer',
        required: false,
        default: 50
      }
    ],
    perform: (z, bundle) => {
      const params = {};
      if (bundle.inputData.status) params.status = bundle.inputData.status;
      if (bundle.inputData.limit) params.limit = bundle.inputData.limit;

      return z.request({
        url: `https://{{bundle.authData.domain}}/v1/automation/tasks`,
        params: params
      }).then((response) => {
        return response.json.tasks || [];
      });
    }
  }
};
```

## searches/poll_task.js

Polling search for Zapier Looping.

```javascript
module.exports = {
  key: 'poll_task',
  noun: 'Task Poll',
  display: {
    label: 'Poll Task',
    description: 'Poll task status until completion (use with Looping by Zapier)'
  },
  operation: {
    inputFields: [
      {
        key: 'task_id',
        label: 'Task ID',
        type: 'string',
        required: true
      }
    ],
    perform: (z, bundle) => {
      return z.request({
        url: `https://{{bundle.authData.domain}}/v1/automation/tasks/${bundle.inputData.task_id}`
      }).then((response) => {
        const task = response.json;
        const isComplete = ['completed', 'failed', 'cancelled'].includes(task.status);
        return isComplete ? [task] : [];
      });
    }
  }
};
```

## deletes/cancel_task.js

Delete action with Copy field for irreversible operations.

```javascript
module.exports = {
  key: 'cancel_task',
  noun: 'Task',
  display: {
    label: 'Cancel Task',
    description: 'Cancel a queued or running task'
  },
  operation: {
    inputFields: [
      {
        key: 'task_id',
        label: 'Task ID',
        type: 'string',
        required: true
      },
      {
        key: 'confirm',
        label: 'Confirm',
        type: 'string',
        required: true,
        choices: ['yes', 'no'],
        dynamic: 'confirm_value'
      }
    ],
    perform: (z, bundle) => {
      if (bundle.inputData.confirm !== 'yes') {
        throw new z.errors.HaltedError('Please type "yes" to confirm cancellation');
      }

      return z.request({
        method: 'DELETE',
        url: `https://{{bundle.authData.domain}}/v1/automation/tasks/${bundle.inputData.task_id}`,
        headers: { 'X-Copy': 'Cancel is irreversible' }
      }).then(() => {
        return { task_id: bundle.inputData.task_id, status: 'cancelled' };
      });
    }
  }
};
```

## Deploy

```bash
zapier push
zapier promote
zapier submit
```

