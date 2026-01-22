export const prismaOpenCodeStorageSchema = `
// OpenCode Storage Prisma Schema

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model Project {
  id        String        @id
  worktree  String
  vcs       String?
  createdAt DateTime      @default(now())
  updatedAt DateTime      @updatedAt
  sandboxes Json
  sessions  Session[]

  @@map("projects")
}

model Session {
  id          String    @id
  version     String
  projectId   String
  project     Project   @relation(fields: [projectId], references: [id])
  directory   String
  title       String
  createdAt   DateTime  @default(now())
  updatedAt   DateTime  @updatedAt
  summary     Json?
  messages    Message[]
  diff        Diff[]
  todos       Todo[]

  @@index([projectId])
  @@index([updatedAt])
  @@map("sessions")
}

model Message {
  id          String        @id
  sessionId   String
  session     Session       @relation(fields: [sessionId], references: [id], onDelete: Cascade)
  role        MessageRole
  createdAt   DateTime      @default(now())
  completedAt DateTime?
  summary     Json?
  parentId    String?
  parent      Message?      @relation("MessageThread", fields: [parentId], references: [id], onDelete: SetNull)
  children    Message[]     @relation("MessageThread")
  modelId     String?
  providerId  String?
  mode        String?
  path        Json?
  cost        Decimal?      @db.Decimal(10, 6)
  tokens      Json?
  agent       String?
  model       Json?
  parts       Part[]

  @@index([sessionId])
  @@index([parentId])
  @@index([createdAt])
  @@map("messages")
}

model Part {
  id          String    @id
  sessionId   String
  messageId   String
  message     Message   @relation(fields: [messageId], references: [id], onDelete: Cascade)
  type        String
  text        String    @db.Text
  startedAt   DateTime?
  endedAt     DateTime?

  @@index([messageId])
  @@map("parts")
}

model Diff {
  id         Int64    @id @default(autoincrement())
  sessionId  String
  session    Session  @relation(fields: [sessionId], references: [id], onDelete: Cascade)
  file       String
  before     String   @db.Text
  after      String   @db.Text
  additions  Int
  deletions  Int

  @@index([sessionId])
  @@index([file])
  @@map("diffs")
}

model Todo {
  id        Int64       @id @default(autoincrement())
  sessionId String
  session   Session     @relation(fields: [sessionId], references: [id], onDelete: Cascade)
  content   String      @db.Text
  status    TodoStatus
  priority  TodoPriority
  createdAt DateTime    @default(now())
  updatedAt DateTime    @updatedAt

  @@index([sessionId])
  @@index([status])
  @@map("todos")
}

enum MessageRole {
  user
  assistant
}

enum TodoStatus {
  pending
  in_progress
  completed
  cancelled
}

enum TodoPriority {
  low
  medium
  high
}
`;

export const prismaSchemaRaw = `
CREATE TYPE message_role AS ENUM ('user', 'assistant');
CREATE TYPE todo_status AS ENUM ('pending', 'in_progress', 'completed', 'cancelled');
CREATE TYPE todo_priority AS ENUM ('low', 'medium', 'high');

CREATE TABLE projects (
  id VARCHAR(255) PRIMARY KEY,
  worktree VARCHAR(1024) NOT NULL,
  vcs VARCHAR(100),
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  sandboxes JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE sessions (
  id VARCHAR(255) PRIMARY KEY,
  version VARCHAR(100) NOT NULL,
  project_id VARCHAR(255) NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  directory VARCHAR(1024) NOT NULL,
  title VARCHAR(512) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  summary JSONB
);

CREATE INDEX idx_sessions_project_id ON sessions(project_id);
CREATE INDEX idx_sessions_updated_at ON sessions(updated_at DESC);

CREATE TABLE messages (
  id VARCHAR(255) PRIMARY KEY,
  session_id VARCHAR(255) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  role message_role NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMP,
  summary JSONB,
  parent_id VARCHAR(255) REFERENCES messages(id) ON DELETE SET NULL,
  model_id VARCHAR(255),
  provider_id VARCHAR(255),
  mode VARCHAR(100),
  path JSONB,
  cost DECIMAL(10, 6),
  tokens JSONB,
  agent VARCHAR(100),
  model JSONB
);

CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_messages_parent_id ON messages(parent_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);

CREATE TABLE parts (
  id VARCHAR(255) PRIMARY KEY,
  session_id VARCHAR(255) NOT NULL,
  message_id VARCHAR(255) NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  type VARCHAR(100) NOT NULL,
  text TEXT NOT NULL,
  started_at TIMESTAMP,
  ended_at TIMESTAMP
);

CREATE INDEX idx_parts_message_id ON parts(message_id);

CREATE TABLE diffs (
  id BIGSERIAL PRIMARY KEY,
  session_id VARCHAR(255) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  file VARCHAR(1024) NOT NULL,
  before TEXT,
  after TEXT,
  additions INTEGER NOT NULL,
  deletions INTEGER NOT NULL
);

CREATE INDEX idx_diffs_session_id ON diffs(session_id);
CREATE INDEX idx_diffs_file ON diffs(file);

CREATE TABLE todos (
  id BIGSERIAL PRIMARY KEY,
  session_id VARCHAR(255) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  status todo_status NOT NULL DEFAULT 'pending',
  priority todo_priority NOT NULL DEFAULT 'medium',
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_todos_session_id ON todos(session_id);
CREATE INDEX idx_todos_status ON todos(status);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sessions_updated_at BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_todos_updated_at BEFORE UPDATE ON todos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
`;
