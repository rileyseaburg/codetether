export const OpenCodeOpenAPISpec = {
  openapi: '3.0.0',
  info: {
    title: 'OpenCode Storage API',
    version: '1.0.0',
    description: 'RESTful API for managing OpenCode storage data including projects, sessions, messages, and todos',
  },
  servers: [
    {
      url: 'http://localhost:3000/api',
      description: 'Development server',
    },
  ],
  paths: {
    '/projects': {
      get: {
        summary: 'List all projects',
        tags: ['Projects'],
        responses: {
          '200': {
            description: 'Successful response',
            content: {
              'application/json': {
                schema: {
                  type: 'array',
                  items: { $ref: '#/components/schemas/Project' },
                },
              },
            },
          },
        },
      },
      post: {
        summary: 'Create a new project',
        tags: ['Projects'],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: { $ref: '#/components/schemas/ProjectInput' },
            },
          },
        },
        responses: {
          '201': {
            description: 'Project created',
            content: {
              'application/json': {
                schema: { $ref: '#/components/schemas/Project' },
              },
            },
          },
        },
      },
    },
    '/projects/{id}': {
      get: {
        summary: 'Get project by ID',
        tags: ['Projects'],
        parameters: [
          {
            name: 'id',
            in: 'path',
            required: true,
            schema: { type: 'string' },
          },
        ],
        responses: {
          '200': {
            description: 'Successful response',
            content: {
              'application/json': {
                schema: { $ref: '#/components/schemas/Project' },
              },
            },
          },
          '404': {
            description: 'Project not found',
          },
        },
      },
      put: {
        summary: 'Update project',
        tags: ['Projects'],
        parameters: [
          {
            name: 'id',
            in: 'path',
            required: true,
            schema: { type: 'string' },
          },
        ],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: { $ref: '#/components/schemas/ProjectUpdate' },
            },
          },
        },
        responses: {
          '200': {
            description: 'Project updated',
            content: {
              'application/json': {
                schema: { $ref: '#/components/schemas/Project' },
              },
            },
          },
        },
      },
      delete: {
        summary: 'Delete project',
        tags: ['Projects'],
        parameters: [
          {
            name: 'id',
            in: 'path',
            required: true,
            schema: { type: 'string' },
          },
        ],
        responses: {
          '204': {
            description: 'Project deleted',
          },
        },
      },
    },
    '/projects/{id}/sessions': {
      get: {
        summary: 'List sessions for a project',
        tags: ['Projects', 'Sessions'],
        parameters: [
          {
            name: 'id',
            in: 'path',
            required: true,
            schema: { type: 'string' },
          },
        ],
        responses: {
          '200': {
            description: 'Successful response',
            content: {
              'application/json': {
                schema: {
                  type: 'array',
                  items: { $ref: '#/components/schemas/Session' },
                },
              },
            },
          },
        },
      },
    },
    '/sessions': {
      get: {
        summary: 'List all sessions',
        tags: ['Sessions'],
        parameters: [
          {
            name: 'projectId',
            in: 'query',
            schema: { type: 'string' },
          },
          {
            name: 'limit',
            in: 'query',
            schema: { type: 'integer', default: 100 },
          },
          {
            name: 'offset',
            in: 'query',
            schema: { type: 'integer', default: 0 },
          },
        ],
        responses: {
          '200': {
            description: 'Successful response',
            content: {
              'application/json': {
                schema: {
                  type: 'array',
                  items: { $ref: '#/components/schemas/Session' },
                },
              },
            },
          },
        },
      },
      post: {
        summary: 'Create a new session',
        tags: ['Sessions'],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: { $ref: '#/components/schemas/SessionInput' },
            },
          },
        },
        responses: {
          '201': {
            description: 'Session created',
            content: {
              'application/json': {
                schema: { $ref: '#/components/schemas/Session' },
              },
            },
          },
        },
      },
    },
    '/sessions/{id}': {
      get: {
        summary: 'Get session by ID',
        tags: ['Sessions'],
        parameters: [
          {
            name: 'id',
            in: 'path',
            required: true,
            schema: { type: 'string' },
          },
        ],
        responses: {
          '200': {
            description: 'Successful response',
            content: {
              'application/json': {
                schema: { $ref: '#/components/schemas/Session' },
              },
            },
          },
          '404': {
            description: 'Session not found',
          },
        },
      },
      put: {
        summary: 'Update session',
        tags: ['Sessions'],
        parameters: [
          {
            name: 'id',
            in: 'path',
            required: true,
            schema: { type: 'string' },
          },
        ],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: { $ref: '#/components/schemas/SessionUpdate' },
            },
          },
        },
        responses: {
          '200': {
            description: 'Session updated',
            content: {
              'application/json': {
                schema: { $ref: '#/components/schemas/Session' },
              },
            },
          },
        },
      },
      delete: {
        summary: 'Delete session',
        tags: ['Sessions'],
        parameters: [
          {
            name: 'id',
            in: 'path',
            required: true,
            schema: { type: 'string' },
          },
        ],
        responses: {
          '204': {
            description: 'Session deleted',
          },
        },
      },
    },
    '/sessions/{id}/messages': {
      get: {
        summary: 'List messages for a session',
        tags: ['Sessions', 'Messages'],
        parameters: [
          {
            name: 'id',
            in: 'path',
            required: true,
            schema: { type: 'string' },
          },
        ],
        responses: {
          '200': {
            description: 'Successful response',
            content: {
              'application/json': {
                schema: {
                  type: 'array',
                  items: { $ref: '#/components/schemas/Message' },
                },
              },
            },
          },
        },
      },
    },
    '/sessions/{id}/stats': {
      get: {
        summary: 'Get session statistics',
        tags: ['Sessions'],
        parameters: [
          {
            name: 'id',
            in: 'path',
            required: true,
            schema: { type: 'string' },
          },
        ],
        responses: {
          '200': {
            description: 'Successful response',
            content: {
              'application/json': {
                schema: { $ref: '#/components/schemas/SessionStats' },
              },
            },
          },
        },
      },
    },
    '/sessions/{id}/diff': {
      get: {
        summary: 'Get session diff (file changes)',
        tags: ['Sessions', 'Diffs'],
        parameters: [
          {
            name: 'id',
            in: 'path',
            required: true,
            schema: { type: 'string' },
          },
        ],
        responses: {
          '200': {
            description: 'Successful response',
            content: {
              'application/json': {
                schema: {
                  type: 'array',
                  items: { $ref: '#/components/schemas/Diff' },
                },
              },
            },
          },
        },
      },
    },
    '/sessions/{id}/todo': {
      get: {
        summary: 'Get todos for a session',
        tags: ['Sessions', 'Todos'],
        parameters: [
          {
            name: 'id',
            in: 'path',
            required: true,
            schema: { type: 'string' },
          },
        ],
        responses: {
          '200': {
            description: 'Successful response',
            content: {
              'application/json': {
                schema: {
                  type: 'array',
                  items: { $ref: '#/components/schemas/Todo' },
                },
              },
            },
          },
        },
      },
      put: {
        summary: 'Update todos for a session',
        tags: ['Sessions', 'Todos'],
        parameters: [
          {
            name: 'id',
            in: 'path',
            required: true,
            schema: { type: 'string' },
          },
        ],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: {
                type: 'array',
                items: { $ref: '#/components/schemas/TodoInput' },
              },
            },
          },
        },
        responses: {
          '200': {
            description: 'Todos updated',
            content: {
              'application/json': {
                schema: {
                  type: 'array',
                  items: { $ref: '#/components/schemas/Todo' },
                },
              },
            },
          },
        },
      },
    },
    '/messages': {
      post: {
        summary: 'Create a new message',
        tags: ['Messages'],
        requestBody: {
          required: true,
          content: {
            'application/json': {
              schema: { $ref: '#/components/schemas/MessageInput' },
            },
          },
        },
        responses: {
          '201': {
            description: 'Message created',
            content: {
              'application/json': {
                schema: { $ref: '#/components/schemas/Message' },
              },
            },
          },
        },
      },
    },
    '/messages/{sessionId}/{messageId}': {
      get: {
        summary: 'Get a specific message',
        tags: ['Messages'],
        parameters: [
          {
            name: 'sessionId',
            in: 'path',
            required: true,
            schema: { type: 'string' },
          },
          {
            name: 'messageId',
            in: 'path',
            required: true,
            schema: { type: 'string' },
          },
        ],
        responses: {
          '200': {
            description: 'Successful response',
            content: {
              'application/json': {
                schema: { $ref: '#/components/schemas/Message' },
              },
            },
          },
        },
      },
    },
    '/messages/{messageId}/parts': {
      get: {
        summary: 'Get parts for a message',
        tags: ['Messages', 'Parts'],
        parameters: [
          {
            name: 'messageId',
            in: 'path',
            required: true,
            schema: { type: 'string' },
          },
        ],
        responses: {
          '200': {
            description: 'Successful response',
            content: {
              'application/json': {
                schema: {
                  type: 'array',
                  items: { $ref: '#/components/schemas/Part' },
                },
              },
            },
          },
        },
      },
    },
    '/search': {
      get: {
        summary: 'Search messages by keyword',
        tags: ['Search'],
        parameters: [
          {
            name: 'q',
            in: 'query',
            required: true,
            schema: { type: 'string' },
            description: 'Search keyword',
          },
          {
            name: 'sessionId',
            in: 'query',
            schema: { type: 'string' },
            description: 'Optional session ID to limit search',
          },
        ],
        responses: {
          '200': {
            description: 'Successful response',
            content: {
              'application/json': {
                schema: {
                  type: 'array',
                  items: { $ref: '#/components/schemas/Message' },
                },
              },
            },
          },
        },
      },
    },
  },
  components: {
    schemas: {
      Project: {
        type: 'object',
        required: ['id', 'worktree', 'time', 'sandboxes'],
        properties: {
          id: { type: 'string' },
          worktree: { type: 'string' },
          vcs: { type: 'string' },
          time: { $ref: '#/components/schemas/TimeRange' },
          sandboxes: { type: 'array', items: {} },
        },
      },
      ProjectInput: {
        type: 'object',
        required: ['id', 'worktree'],
        properties: {
          id: { type: 'string' },
          worktree: { type: 'string' },
          vcs: { type: 'string' },
        },
      },
      ProjectUpdate: {
        type: 'object',
        properties: {
          worktree: { type: 'string' },
          vcs: { type: 'string' },
        },
      },
      Session: {
        type: 'object',
        required: ['id', 'version', 'projectID', 'directory', 'title', 'time'],
        properties: {
          id: { type: 'string' },
          version: { type: 'string' },
          projectID: { type: 'string' },
          directory: { type: 'string' },
          title: { type: 'string' },
          time: { $ref: '#/components/schemas/TimeRange' },
          summary: { $ref: '#/components/schemas/SessionSummary' },
        },
      },
      SessionInput: {
        type: 'object',
        required: ['id', 'version', 'projectID', 'directory', 'title'],
        properties: {
          id: { type: 'string' },
          version: { type: 'string' },
          projectID: { type: 'string' },
          directory: { type: 'string' },
          title: { type: 'string' },
        },
      },
      SessionUpdate: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          summary: { $ref: '#/components/schemas/SessionSummary' },
        },
      },
      Message: {
        type: 'object',
        required: ['id', 'sessionID', 'role', 'time'],
        properties: {
          id: { type: 'string' },
          sessionID: { type: 'string' },
          role: { type: 'string', enum: ['user', 'assistant'] },
          time: { $ref: '#/components/schemas/MessageTime' },
          summary: { $ref: '#/components/schemas/MessageSummary' },
          parentID: { type: 'string' },
          modelID: { type: 'string' },
          providerID: { type: 'string' },
          mode: { type: 'string' },
          path: { $ref: '#/components/schemas/MessagePath' },
          cost: { type: 'number' },
          tokens: { $ref: '#/components/schemas/MessageTokens' },
          agent: { type: 'string' },
          model: { $ref: '#/components/schemas/MessageModel' },
        },
      },
      MessageInput: {
        type: 'object',
        required: ['id', 'sessionID', 'role'],
        properties: {
          id: { type: 'string' },
          sessionID: { type: 'string' },
          role: { type: 'string', enum: ['user', 'assistant'] },
          parentID: { type: 'string' },
          modelID: { type: 'string' },
          providerID: { type: 'string' },
          mode: { type: 'string' },
          path: { $ref: '#/components/schemas/MessagePath' },
          cost: { type: 'number' },
          tokens: { $ref: '#/components/schemas/MessageTokens' },
          agent: { type: 'string' },
        },
      },
      Part: {
        type: 'object',
        required: ['id', 'sessionID', 'messageID', 'type', 'text'],
        properties: {
          id: { type: 'string' },
          sessionID: { type: 'string' },
          messageID: { type: 'string' },
          type: { type: 'string' },
          text: { type: 'string' },
          time: { $ref: '#/components/schemas/PartTime' },
        },
      },
      Diff: {
        type: 'object',
        required: ['file', 'before', 'after', 'additions', 'deletions'],
        properties: {
          file: { type: 'string' },
          before: { type: 'string' },
          after: { type: 'string' },
          additions: { type: 'integer' },
          deletions: { type: 'integer' },
        },
      },
      Todo: {
        type: 'object',
        required: ['id', 'content', 'status', 'priority'],
        properties: {
          id: { type: 'string' },
          content: { type: 'string' },
          status: { type: 'string', enum: ['pending', 'in_progress', 'completed', 'cancelled'] },
          priority: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
      },
      TodoInput: {
        type: 'object',
        required: ['id', 'content', 'status', 'priority'],
        properties: {
          id: { type: 'string' },
          content: { type: 'string' },
          status: { type: 'string', enum: ['pending', 'in_progress', 'completed', 'cancelled'] },
          priority: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
      },
      TimeRange: {
        type: 'object',
        required: ['created', 'updated'],
        properties: {
          created: { type: 'number' },
          updated: { type: 'number' },
        },
      },
      MessageTime: {
        type: 'object',
        required: ['created'],
        properties: {
          created: { type: 'number' },
          completed: { type: 'number' },
        },
      },
      PartTime: {
        type: 'object',
        properties: {
          start: { type: 'number' },
          end: { type: 'number' },
        },
      },
      SessionSummary: {
        type: 'object',
        properties: {
          additions: { type: 'integer' },
          deletions: { type: 'integer' },
          files: { type: 'integer' },
        },
      },
      MessageSummary: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          diffs: { type: 'array', items: { $ref: '#/components/schemas/Diff' } },
        },
      },
      MessagePath: {
        type: 'object',
        properties: {
          cwd: { type: 'string' },
          root: { type: 'string' },
        },
      },
      TokenCache: {
        type: 'object',
        properties: {
          read: { type: 'number' },
          write: { type: 'number' },
        },
      },
      MessageTokens: {
        type: 'object',
        properties: {
          input: { type: 'number' },
          output: { type: 'number' },
          reasoning: { type: 'number' },
          cache: { $ref: '#/components/schemas/TokenCache' },
        },
      },
      MessageModel: {
        type: 'object',
        properties: {
          providerID: { type: 'string' },
          modelID: { type: 'string' },
        },
      },
      SessionStats: {
        type: 'object',
        properties: {
          messageCount: { type: 'integer' },
          userMessageCount: { type: 'integer' },
          assistantMessageCount: { type: 'integer' },
          totalTime: { type: 'number' },
          totalCost: { type: 'number' },
          totalTokens: { type: 'integer' },
        },
      },
    },
  },
};