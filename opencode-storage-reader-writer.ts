import {
  Project,
  Session,
  Message,
  Part,
  Diff,
  Todo,
  TodoList,
  SessionDiff,
  MessageRole,
  MessageMode,
  TodoStatus,
  TodoPriority,
  STORAGE_PATHS,
  STORAGE_BASE_PATH,
  MESSAGE_ID_PREFIX,
  SESSION_ID_PREFIX,
  PART_ID_PREFIX,
} from './opencode-storage-types';
import * as fs from 'fs';
import * as path from 'path';

export class OpenCodeStorageReader {
  private basePath: string;

  constructor(basePath: string = STORAGE_BASE_PATH) {
    this.basePath = basePath;
  }

  private readJSON<T>(filePath: string): T | null {
    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      return JSON.parse(content);
    } catch (error) {
      return null;
    }
  }

  readProject(id: string): Project | null {
    const filePath = path.join(this.basePath, 'project', `${id}.json`);
    return this.readJSON<Project>(filePath);
  }

  readSession(id: string): Session | null {
    const filePath = path.join(this.basePath, 'session', `${id}.json`);
    return this.readJSON<Session>(filePath);
  }

  readMessage(sessionId: string, messageId: string): Message | null {
    const filePath = path.join(this.basePath, 'message', sessionId, `${messageId}.json`);
    return this.readJSON<Message>(filePath);
  }

  readMessageDirectory(sessionId: string): Message[] {
    const dirPath = path.join(this.basePath, 'message', sessionId);
    if (!fs.existsSync(dirPath)) return [];

    const files = fs.readdirSync(dirPath).filter(f => f.endsWith('.json'));
    const messages: Message[] = [];

    for (const file of files) {
      const content = this.readJSON<Message>(path.join(dirPath, file));
      if (content) messages.push(content);
    }

    return messages.sort((a, b) => a.time.created - b.time.created);
  }

  readPartsForMessage(messageId: string): Part[] {
    const dirName = `msg_${messageId}`;
    const dirPath = path.join(this.basePath, 'part', dirName);

    if (!fs.existsSync(dirPath)) return [];

    const files = fs.readdirSync(dirPath).filter(f => f.startsWith('prt_') && f.endsWith('.json'));
    const parts: Part[] = [];

    for (const file of files) {
      const content = this.readJSON<Part>(path.join(dirPath, file));
      if (content) parts.push(content);
    }

    return parts.sort((a, b) => (a.time?.start || 0) - (b.time?.start || 0));
  }

  readSessionDiff(sessionId: string): SessionDiff | null {
    const filePath = path.join(this.basePath, 'session_diff', `${sessionId}.json`);
    const content = this.readJSON<SessionDiff>(filePath);

    if (!content) return null;

    if (!Array.isArray(content)) return [];

    return content;
  }

  readTodo(sessionId: string): TodoList | null {
    const filePath = path.join(this.basePath, 'todo', `${sessionId}.json`);
    return this.readJSON<TodoList>(filePath);
  }

  listProjects(): Project[] {
    const dirPath = path.join(this.basePath, 'project');
    if (!fs.existsSync(dirPath)) return [];

    const files = fs.readdirSync(dirPath).filter(f => f.endsWith('.json'));
    const projects: Project[] = [];

    for (const file of files) {
      const project = this.readJSON<Project>(path.join(dirPath, file));
      if (project) projects.push(project);
    }

    return projects;
  }

  listSessions(): Session[] {
    const dirPath = path.join(this.basePath, 'session');
    if (!fs.existsSync(dirPath)) return [];

    const files = fs.readdirSync(dirPath).filter(f => f.endsWith('.json'));
    const sessions: Session[] = [];

    for (const file of files) {
      const session = this.readJSON<Session>(path.join(dirPath, file));
      if (session) sessions.push(session);
    }

    return sessions.sort((a, b) => b.time.updated - a.time.updated);
  }

  listSessionsForProject(projectId: string): Session[] {
    const allSessions = this.listSessions();
    return allSessions.filter(s => s.projectID === projectId);
  }

  getGlobalProject(): Project | null {
    return this.readProject('global');
  }

  getSessionStats(sessionId: string): {
    messageCount: number;
    userMessageCount: number;
    assistantMessageCount: number;
    totalTime: number;
    totalCost: number;
    totalTokens: number;
  } | null {
    const session = this.readSession(sessionId);
    if (!session) return null;

    const messages = this.readMessageDirectory(sessionId);

    const userMessages = messages.filter(m => m.role === 'user');
    const assistantMessages = messages.filter(m => m.role === 'assistant');

    const totalTime = messages.reduce((sum, m) => {
      const duration = m.time.completed ? m.time.completed - m.time.created : 0;
      return sum + duration;
    }, 0);

    const totalCost = messages.reduce((sum, m) => sum + (m.cost || 0), 0);

    const totalTokens = messages.reduce((sum, m) => {
      const input = m.tokens?.input || 0;
      const output = m.tokens?.output || 0;
      const reasoning = m.tokens?.reasoning || 0;
      return sum + input + output + reasoning;
    }, 0);

    return {
      messageCount: messages.length,
      userMessageCount: userMessages.length,
      assistantMessageCount: assistantMessages.length,
      totalTime,
      totalCost,
      totalTokens,
    };
  }

  getTodoStats(sessionId: string): {
    total: number;
    completed: number;
    pending: number;
    inProgress: number;
    cancelled: number;
  } | null {
    const todos = this.readTodo(sessionId);
    if (!todos) return null;

    return {
      total: todos.length,
      completed: todos.filter(t => t.status === 'completed').length,
      pending: todos.filter(t => t.status === 'pending').length,
      inProgress: todos.filter(t => t.status === 'in_progress').length,
      cancelled: todos.filter(t => t.status === 'cancelled').length,
    };
  }

  getRecentSessions(limit: number = 10): Session[] {
    const sessions = this.listSessions();
    return sessions.slice(0, limit);
  }

  getActiveTodos(sessionId: string): Todo[] {
    const todos = this.readTodo(sessionId);
    if (!todos) return [];

    return todos.filter(t => t.status === 'pending' || t.status === 'in_progress');
  }
}

export class OpenCodeStorageWriter {
  private basePath: string;

  constructor(basePath: string = STORAGE_BASE_PATH) {
    this.basePath = basePath;
  }

  private ensureDirectory(dirPath: string): void {
    if (!fs.existsSync(dirPath)) {
      fs.mkdirSync(dirPath, { recursive: true });
    }
  }

  private writeJSON<T>(filePath: string, data: T): boolean {
    try {
      this.ensureDirectory(path.dirname(filePath));
      fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
      return true;
    } catch (error) {
      console.error(`Failed to write JSON to ${filePath}:`, error);
      return false;
    }
  }

  writeProject(project: Project): boolean {
    const filePath = path.join(this.basePath, 'project', `${project.id}.json`);
    return this.writeJSON(filePath, project);
  }

  writeSession(session: Session): boolean {
    const filePath = path.join(this.basePath, 'session', `${session.id}.json`);
    return this.writeJSON(filePath, session);
  }

  writeMessage(sessionId: string, message: Message): boolean {
    const filePath = path.join(this.basePath, 'message', sessionId, `${message.id}.json`);
    return this.writeJSON(filePath, message);
  }

  writePart(messageId: string, part: Part): boolean {
    const fileName = `msg_${messageId}`;
    const partFileName = `prt_${part.id}.json`;
    const filePath = path.join(this.basePath, 'part', fileName, partFileName);
    return this.writeJSON(filePath, part);
  }

  writeSessionDiff(sessionId: string, diff: SessionDiff): boolean {
    const filePath = path.join(this.basePath, 'session_diff', `${sessionId}.json`);
    return this.writeJSON(filePath, diff);
  }

  writeTodo(sessionId: string, todoList: TodoList): boolean {
    const filePath = path.join(this.basePath, 'todo', `${sessionId}.json`);
    return this.writeJSON(filePath, todoList);
  }
}

export const storageReader = new OpenCodeStorageReader();
export const storageWriter = new OpenCodeStorageWriter();
