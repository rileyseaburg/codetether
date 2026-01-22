import { Project, Session, Message, Part, Todo } from './opencode-storage-types';
import * as crypto from 'crypto';

export function generateId(prefix: string): string {
  const randomBytes = crypto.randomBytes(16);
  const hexString = randomBytes.toString('hex');
  return `${prefix}${hexString}`;
}

export function generateProjectId(): string {
  return crypto.randomUUID();
}

export function generateSessionId(): string {
  return generateId('ses_');
}

export function generateMessageId(): string {
  return generateId('msg_');
}

export function generatePartId(): string {
  return generateId('prt_');
}

export function generateTodoId(lastTodoId?: string): string {
  if (!lastTodoId) return '1';
  const num = parseInt(lastTodoId, 10);
  if (isNaN(num)) return '1';
  return String(num + 1);
}

export function createProject(data: Omit<Project, 'id' | 'time' | 'sandboxes'>): Project {
  const now = Date.now();
  return {
    id: generateProjectId(),
    ...data,
    time: {
      created: now,
      updated: now,
    },
    sandboxes: [],
  };
}

export function createSession(data: Omit<Session, 'id' | 'time'>): Session {
  const now = Date.now();
  return {
    id: generateSessionId(),
    ...data,
    time: {
      created: now,
      updated: now,
    },
  };
}

export function createMessage(data: Omit<Message, 'id' | 'time'>): Message {
  const now = Date.now();
  return {
    id: generateMessageId(),
    time: {
      created: now,
    },
    ...data,
  };
}

export function createPart(data: Omit<Part, 'id' | 'time'>): Part {
  return {
    id: generatePartId(),
    ...data,
  };
}

export function createMessageContent(parts: Part[]): string {
  return parts.map(p => p.text).join('\n');
}

export function formatTimestamp(ms: number): string {
  const date = new Date(ms);
  return date.toISOString();
}

export function parseTimestamp(value: string | number): number {
  if (typeof value === 'number') return value;
  return new Date(value).getTime();
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(2)}s`;
  if (ms < 3600000) return `${(ms / 60000).toFixed(2)}m`;
  return `${(ms / 3600000).toFixed(2)}h`;
}

export function calculateMessageCost(
  tokens: { input?: number; output?: number; reasoning?: number },
  rates: { inputTokenCost: number; outputTokenCost: number; reasoningTokenCost?: number }
): number {
  const inputCost = (tokens.input || 0) * rates.inputTokenCost;
  const outputCost = (tokens.output || 0) * rates.outputTokenCost;
  const reasoningCost = rates.reasoningTokenCost ? (tokens.reasoning || 0) * rates.reasoningTokenCost : 0;
  return inputCost + outputCost + reasoningCost;
}

export function getMessageThread(messages: Message[]): Message[][] {
  const threadMap = new Map<string, Message>();
  messages.forEach(m => threadMap.set(m.id, m));
  const threads: Message[][] = [];
  const visited = new Set<string>();

  function buildThread(messageId: string): Message[] {
    const thread: Message[] = [];
    let currentId: string | undefined = messageId;

    while (currentId) {
      const message = threadMap.get(currentId);
      if (!message || visited.has(currentId)) break;

      visited.add(currentId);
      thread.unshift(message);

      const parent = threadMap.get(message.parentID || '');
      currentId = parent?.id;
    }

    return thread;
  }

  for (const message of messages) {
    if (!visited.has(message.id) && !message.parentID) {
      threads.push(buildThread(message.id));
    }
  }

  return threads;
}

export function findSessionKeywords(session: Session): string[] {
  const keywords: string[] = [];
  keywords.push(...session.title.toLowerCase().split(/\s+/));

  if (session.summary) {
    const summaryStr = JSON.stringify(session.summary).toLowerCase();
    keywords.push(...summaryStr.split(/\s+/));
  }

  return keywords.filter(k => k.length > 3);
}

export function mergeSessionDiffs(diffs: Diff[][], fileFilter?: string): Diff[] {
  const mergeMap = new Map<string, Diff>();

  for (const diffArray of diffs) {
    for (const diff of diffArray) {
      if (fileFilter && !diff.file.includes(fileFilter)) continue;

      const existing = mergeMap.get(diff.file);
      if (existing) {
        existing.after = diff.after;
        existing.additions += diff.additions;
        existing.deletions += diff.deletions;
      } else {
        mergeMap.set(diff.file, { ...diff });
      }
    }
  }

  return Array.from(mergeMap.values());
}

export function getMessagesByRole(messages: Message[]): { user: Message[]; assistant: Message[] } {
  return {
    user: messages.filter(m => m.role === 'user'),
    assistant: messages.filter(m => m.role === 'assistant'),
  };
}

export function getActiveTodos(todos: Todo[]): Todo[] {
  return todos.filter(t => t.status === 'pending' || t.status === 'in_progress');
}

export function getCompletedTodos(todos: Todo[]): Todo[] {
  return todos.filter(t => t.status === 'completed');
}

export function getTodoCompletionRate(todos: Todo[]): number {
  if (todos.length === 0) return 0;
  const completed = todos.filter(t => t.status === 'completed').length;
  return (completed / todos.length) * 100;
}

export function prioritizeTodos(todos: Todo[]): Todo[] {
  const priorityOrder = { high: 0, medium: 1, low: 2 };
  return [...todos].sort((a, b) => {
    const aPriority = priorityOrder[a.priority as keyof typeof priorityOrder] ?? 999;
    const bPriority = priorityOrder[b.priority as keyof typeof priorityOrder] ?? 999;
    return aPriority - bPriority;
  });
}

export function sanitizeForJSON(data: any): any {
  if (data === null || data === undefined) return null;
  if (typeof data === 'string' || typeof data === 'number' || typeof data === 'boolean') {
    return data;
  }
  if (Array.isArray(data)) {
    return data.map(item => sanitizeForJSON(item));
  }
  if (typeof data === 'object') {
    const result: Record<string, any> = {};
    for (const [key, value] of Object.entries(data)) {
      result[key] = sanitizeForJSON(value);
    }
    return result;
  }
  return null;
}

export function deepEqual(a: any, b: any): boolean {
  if (a === b) return true;
  if (a == null || b == null) return a === b;
  if (typeof a !== typeof b) return false;

  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    return a.every((item, i) => deepEqual(item, b[i]));
  }

  if (typeof a === 'object' && typeof b === 'object') {
    const keysA = Object.keys(a);
    const keysB = Object.keys(b);
    if (keysA.length !== keysB.length) return false;
    return keysA.every(key => deepEqual(a[key], b[key]));
  }

  return false;
}

export function clone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj));
}

export function debounce<T extends (...args: any[]) => any>(func: T, wait: number): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

export function throttle<T extends (...args: any[]) => any>(func: T, limit: number): (...args: Parameters<T>) => void {
  let inThrottle: boolean;
  return (...args: Parameters<T>) => {
    if (!inThrottle) {
      func(...args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}

export const defaultCostRates = {
  inputTokenCost: 0.000003,
  outputTokenCost: 0.000015,
  reasoningTokenCost: 0.00001,
};

export const timestampConstants = {
  SECOND: 1000,
  MINUTE: 60000,
  HOUR: 3600000,
  DAY: 86400000,
  WEEK: 604800000,
  MONTH: 2592000000,
  YEAR: 31536000000,
};