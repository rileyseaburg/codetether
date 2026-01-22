# OpenCode Storage Schema Library

Complete type/schema definition library for OpenCode's local file-based storage system.

## Overview

This library provides comprehensive type definitions, validation schemas, and utilities for working with OpenCode's storage data format. OpenCode stores coding sessions, messages, projects, and related metadata in a structured JSON format on disk.

## Schema Documentation

**[Storage Schema Guide](/opencode-storage-schema.md)** - Complete human-readable documentation of all data types, relationships, and file structure.

## Core Type Definitions

### TypeScript Types (`opencode-storage-types.ts`)
Complete TypeScript interface definitions for all storage types:
- `Project` - Codebase/environment configuration
- `Session` - Complete coding conversation 
- `Message` - Individual chat messages
- `Part` - Message content blocks
- `Diff` - File changes
- `Todo` - Task tracking
- Plus helper types and constants

```typescript
import { Project, Session, Message } from './opencode-storage-types';

const project: Project = {
  id: 'abc123',
  worktree: '/path/to/project',
  time: { created: Date.now(), updated: Date.now() },
  sandboxes: []
};
```

### Zod Validation (`opencode-storage-zod.ts`)
Runtime validation using Zod schemas with safe parsing:

```typescript
import { validateProject, validateMessageSafe } from './opencode-storage-zod';

const project = validateProject(jsonData);
const result = validateMessageSafe(unknownData);
if (result.success) {
  console.log('Valid message:', result.data);
}
```

### JSON Schema (`opencode-storage-json-schema.ts`)
Standard JSON Schema definitions for integration with validators, API documentation tools, and code generators:

```typescript
import { JSONSchema } from './opencode-storage-json-schema';
// Use with ajv, json-schema-validator, etc.
```

## API Schemas

### GraphQL Schema (`opencode-storage-graphql.ts`)
Complete GraphQL type definitions and resolvers interface for building GraphQL APIs:

```graphql
type Query {
  project(id: ID!): Project
  sessions(projectId: ID): [Session!]!
  message(sessionId: ID!, messageId: ID!): Message
}

type Session {
  id: ID!
  title: String!
  messages: [Message!]!
  stats: SessionStats!
}
```

### OpenAPI Specification (`opencode-storage-openapi.ts`)
REST API specification in OpenAPI 3.0 format:

```yaml
paths:
  /projects:
    get:
      summary: List all projects
      responses:
        200:
          content:
            application/json:
              schema:
                type: array
                items: { $ref: '#/components/schemas/Project' }
```

### Prisma ORM Schema (`opencode-storage-prisma.ts`)
Database schema for Prisma ORM (PostgreSQL):

```prisma
model Session {
  id        String    @id
  projectId String
  project   Project   @relation(fields: [projectId])
  messages  Message[]
  diffs     Diff[]
  todos     Todo[]
}
```

Includes raw SQL migrations with proper indexes and foreign keys.

## Storage IO

### Reader/Writer Classes (`opencode-storage-reader-writer.ts`)
File system access classes for reading/writing OpenCode storage data:

```typescript
import { storageReader, storageWriter } from './opencode-storage-reader-writer';

const project = storageReader.readProject('global');
const sessions = storageReader.listSessions();
const stats = storageReader.getSessionStats(sessionId);

storageWriter.writeSession(newSession);
storageWriter.writeTodo(sessionId, todoList);
```

Includes helper methods:
- `readMessageDirectory()` - Get all messages in a session
- `getConversationThread()` - Build message threads
- `searchMessages()` - Keyword search
- `getSessionStats()` - Computed statistics
- `getTodoStats()` - Todo completion tracking

## Utilities

### Helper Functions (`opencode-storage-utils.ts`)
Common utilities for working with storage data:

```typescript
import {
  generateSessionId,
  createProject,
  formatDuration,
  getMessageThread,
  prioritizeTodos
} from './opencode-storage-utils';

const sessionId = generateSessionId(); // "ses_abc123..."
const project = createProject({ worktree: '/path' });
const duration = formatDuration(15000); // "15.00s"
const threads = getMessageThread(messages);
const sorted = prioritizeTodos(todos);
```

Features:
- **ID Generation**: `generateId()`, `generateSessionId()`, etc.
- **Factory Functions**: `createProject()`, `createSession()`, etc.
- **Time Utilities**: `formatTimestamp()`, `formatDuration()`, `parseTimestamp()`
- **Message Operations**: `getMessageThread()`, `mergeSessionDiffs()`, `getMessagesByRole()`
- **Todo Operations**: `getActiveTodos()`, `getCompletedTodos()`, `getTodoCompletionRate()`
- **Data Helpers**: `deepEqual()`, `clone()`, `sanitizeForJSON()`
- **Performance**: `debounce()`, `throttle()`

## File Structure

The storage directory has this layout:

```
/home/riley/.local/share/opencode/storage/
├── project/
│   └── ({project_id}|global).json
├── session/
│   └── {session_id}.json
├── message/
│   └── {session_id}/
│       └── {message_id}.json
├── part/
│   └── msg_{message_id}/
│       └── prt_{part_id}.json
├── session_diff/
│   └── {session_id}.json
└── todo/
    └── {session_id}.json
```

## ID Formats

- **Project**: `{random_uuid}`
- **Session**: `ses_{random_hex}`
- **Message**: `msg_{random_hex}`
- **Part**: `prt_{random_hex}`
- **Todo**: `{sequential_number}`

## Timestamp Format

All timestamps are Unix milliseconds since epoch (`number`, not string).

## Data Relationships

```
Project (1) ----> (*) Session (1) ----> (*) Message (1) ----> (*) Part
    |                                                |
    +---- (*) Diff                                   +---- (*) Message (children)
```

- `Project.projectID` → `Session.id`
- `Session.sessionID` → `Message.sessionID`  
- `Message.id` → `Part.messageID`
- `Message.parentID` → `Message.id` (threading)
- `Session.id` → `Diff[]`, `Todo[]`

## Usage Examples

### Reading Storage Data

```typescript
const reader = new OpenCodeStorageReader(storagePath);
const sessions = reader.listSessions();
const recent = reader.getRecentSessions(10);
for (const session of recent) {
  const messages = reader.readMessageDirectory(session.id);
  const stats = reader.getSessionStats(session.id);
  console.log(`${session.title}: ${stats.messageCount} messages`);
}
```

### Creating New Session

```typescript
import { createSession } from './opencode-storage-utils';
import { storageWriter } from './opencode-storage-reader-writer';

const session = createSession({
  projectId: 'my-project-id',
  directory: '/path/to/code',
  title: 'New Coding Session',
  version: '1.0.0'
});

storageWriter.writeSession(session);
```

### Building GraphQL API

```typescript
import { OpenCodeGraphQLSchema } from './opencode-storage-graphql';
const resolvers: OpenCodeGraphQLResolvers = {
  Query: {
    sessions: () => storageReader.listSessions()
  },
  Session: {
    messages: (session) => storageReader.readMessageDirectory(session.id)
  }
};
```

## Validation

### Type-Safe Parsing

```typescript
import { validateSession, isProject } from './opencode-storage-zod';

const session = validateSession(jsonData);

if (isProject(jsonData)) {
  console.log('Valid project:', jsonSchema.id);
}
```

### Runtime Validation

```typescript
const result = validateTodoListSafe(todos);
if (!result.success) {
  console.error('Validation errors:', result.error.issues);
}
```

## Cost Tracking

```typescript
import { calculateMessageCost, defaultCostRates } from './opencode-storage-utils';

const cost = calculateMessageCost(
  { input: 1000, output: 500, reasoning: 200 },
  defaultCostRates
);
console.log(`Message cost: $${cost.toFixed(6)}`);
```

## Search

```typescript
// Search messages by keyword
const results = reader.searchMessages('React', sessionId);

// Find session keywords
const keywords = findSessionKeywords(session);
```

## Testing

```typescript
import { deepEqual, clone } from './opencode-storage-utils';

const original = { id: '123', title: 'Test' };
const copy = clone(original);
const isSame = deepEqual(original, copy); // true
```

## Integration

### TypeScript Projects

Add files to your project and import as needed:

```json
{
  "include": [
    "opencode-storage-types.ts",
    "opencode-storage-*.ts"
  ]
}
```

### Node.js Backend

Use Reader/Writer classes for direct file access:

```typescript
import { storageReader } from './opencode-storage-reader-writer';
app.get('/api/sessions', async (req, res) => {
  const sessions = storageReader.listSessions();
  res.json(sessions);
});
```

### GraphQL Server

```typescript
import { makeExecutableSchema } from '@graphql-tools/schema';
import { OpenCodeGraphQLSchema, OpenCodeGraphQLResolvers } from '...';

const schema = makeExecutableSchema({
  typeDefs: OpenCodeGraphQLSchema,
  resolvers
});
```

### REST API (Express + OpenAPI)

```typescript
import { OpenCodeOpenAPISpec } from './opencode-storage-openapi';
import swaggerUi from 'swagger-ui-express';

app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(OpenCodeOpenAPISpec));
```

## Database Migration

To migrate from file storage to a database:

```typescript
import prismaOpenCodeStorageSchema from './opencode-storage-prisma';
// Or use the raw SQL migrations included
```

## Contributing

When modifying schema:
1. Update `opencode-storage-types.ts` (primary source)
2. Regenerate Zod/JSON schemas
3. Update documentation in `opencode-storage-schema.md`
4. Add validation tests

## License

Same as parent project.

## Files Summary

| File | Purpose |
|------|---------|
| `opencode-storage-schema.md` | Documentation |
| `opencode-storage-types.ts` | TypeScript types |
| `opencode-storage-zod.ts` | Zod validation |
| `opencode-storage-json-schema.ts` | JSON Schema |
| `opencode-storage-graphql.ts` | GraphQL API |
| `opencode-storage-openapi.ts` | REST API spec |
| `opencode-storage-prisma.ts` | Database schema |
| `opencode-storage-reader-writer.ts` | File I/O |
| `opencode-storage-utils.ts` | Helpers |
| `opencode-storage-library.md` | This file |