export type MessageRole = 'user' | 'assistant';
export type MessageMode = 'build' | 'chat' | 'plan' | string;
export type TodoStatus = 'pending' | 'in_progress' | 'completed' | 'cancelled';
export type TodoPriority = 'high' | 'medium' | 'low';

// Known part types from OpenCode
export type PartType = 
  | 'text'           // Plain text content
  | 'tool'           // Tool call/result
  | 'tool_call'      // Tool invocation
  | 'tool_result'    // Tool response
  | 'web_search'     // Web search results
  | 'web_fetch'      // Fetched web content
  | 'file_read'      // File read operation
  | 'file_write'     // File write operation
  | 'file_edit'      // File edit operation
  | 'bash'           // Shell command execution
  | 'thinking'       // Reasoning/thinking content
  | 'error'          // Error content
  | string;          // Allow unknown types

export interface Timestamps {
  created: number;
  updated?: number;
}

export interface MessageTime {
  created: number;
  completed?: number;
}

export interface PartTime {
  start?: number;
  end?: number;
}

export interface SandboxConfig {
  [key: string]: any;
}

export interface Project {
  id: string;
  worktree: string;
  vcs?: string;
  time: {
    created: number;
    updated: number;
  };
  sandboxes: SandboxConfig[];
}

export interface SessionSummary {
  additions?: number;
  deletions?: number;
  files?: number;
}

export interface Session {
  id: string;
  slug?: string;
  version: string;
  projectID: string;
  directory: string;
  title: string;
  time: {
    created: number;
    updated: number;
  };
  summary?: SessionSummary;
}

export interface MessagePath {
  cwd?: string;
  root?: string;
}

export interface TokenCache {
  read?: number;
  write?: number;
}

export interface MessageTokens {
  input?: number;
  output?: number;
  reasoning?: number;
  cache?: TokenCache;
}

export interface MessageModel {
  providerID?: string;
  modelID?: string;
}

export interface MessageSummary {
  title?: string;
  diffs?: Diff[];
}

export interface Message {
  id: string;
  sessionID: string;
  role: MessageRole;
  time: MessageTime;
  summary?: MessageSummary;
  parentID?: string;
  modelID?: string;
  providerID?: string;
  mode?: MessageMode;
  path?: MessagePath;
  cost?: number;
  tokens?: MessageTokens;
  agent?: string;
  model?: MessageModel;
}

export interface Part {
  id: string;
  sessionID: string;
  messageID: string;
  type: PartType;
  text: string;
  time?: PartTime;
}

export interface Diff {
  file: string;
  before: string;
  after: string;
  additions: number;
  deletions: number;
}

export type SessionDiff = Diff[];

export interface Todo {
  id: string;
  content: string;
  status: TodoStatus;
  priority: TodoPriority;
}

export type TodoList = Todo[];

export interface ProjectID {
  value: string;
  format: 'hex_string';
}

export interface SessionID {
  value: string;
  format: 'ses_hex_string';
}

export interface MessageID {
  value: string;
  format: 'msg_hex_string';
}

export interface PartID {
  value: string;
  format: 'prt_hex_string';
}

export interface TodoID {
  value: string;
  format: 'sequential_string';
}

export interface OpenCodeStorage {
  projects: Map<string, Project>;
  sessions: Map<string, Session>;
  messages: Map<string, Message>;
  parts: Map<string, Part>;
  sessionDiffs: Map<string, SessionDiff>;
  todos: Map<string, TodoList>;
}

export const GLOBAL_PROJECT_ID = 'global';

export const SESSION_ID_PREFIX = 'ses_';
export const MESSAGE_ID_PREFIX = 'msg_';
export const PART_ID_PREFIX = 'prt_';

export function isSessionID(id: string): boolean {
  return id.startsWith(SESSION_ID_PREFIX);
}

export function isMessageID(id: string): boolean {
  return id.startsWith(MESSAGE_ID_PREFIX);
}

export function isPartID(id: string): boolean {
  return id.startsWith(PART_ID_PREFIX);
}

export function isGlobalProject(id: string): boolean {
  return id === GLOBAL_PROJECT_ID;
}

export interface StoragePaths {
  project: (id: string) => string;
  session: (projectId: string, sessionId: string) => string;
  sessionDir: (projectId: string) => string;
  message: (sessionId: string, messageId: string) => string;
  messageDir: (sessionId: string) => string;
  part: (messageId: string, partId: string) => string;
  partDir: (messageId: string) => string;
  sessionDiff: (sessionId: string) => string;
  todo: (sessionId: string) => string;
}

export const STORAGE_BASE_PATH = '/home/riley/.local/share/opencode/storage';

export const STORAGE_PATHS: StoragePaths = {
  project: (id) => `${STORAGE_BASE_PATH}/project/${id}.json`,
  session: (projectId, sessionId) => `${STORAGE_BASE_PATH}/session/${projectId}/${sessionId}.json`,
  sessionDir: (projectId) => `${STORAGE_BASE_PATH}/session/${projectId}`,
  message: (sessionId, messageId) => `${STORAGE_BASE_PATH}/message/${sessionId}/${messageId}.json`,
  messageDir: (sessionId) => `${STORAGE_BASE_PATH}/message/${sessionId}`,
  part: (messageId, partId) => `${STORAGE_BASE_PATH}/part/${messageId}/${partId}.json`,
  partDir: (messageId) => `${STORAGE_BASE_PATH}/part/${messageId}`,
  sessionDiff: (sessionId) => `${STORAGE_BASE_PATH}/session_diff/${sessionId}.json`,
  todo: (sessionId) => `${STORAGE_BASE_PATH}/todo/${sessionId}.json`,
};

// Part type detection utilities
export const KNOWN_PART_TYPES: PartType[] = [
  'text', 'tool', 'tool_call', 'tool_result',
  'web_search', 'web_fetch', 'file_read', 'file_write', 'file_edit',
  'bash', 'thinking', 'error'
];

export function isKnownPartType(type: string): type is PartType {
  return KNOWN_PART_TYPES.includes(type as PartType);
}

export function isToolPart(part: Part): boolean {
  return ['tool', 'tool_call', 'tool_result'].includes(part.type);
}

export function isWebPart(part: Part): boolean {
  return ['web_search', 'web_fetch'].includes(part.type);
}

export function isFilePart(part: Part): boolean {
  return ['file_read', 'file_write', 'file_edit'].includes(part.type);
}

export function isTextPart(part: Part): boolean {
  return part.type === 'text';
}

// Parse web search results from part text (if embedded as JSON or structured content)
export interface WebSearchResult {
  url: string;
  title?: string;
  snippet?: string;
}

export function parseWebSearchResults(part: Part): WebSearchResult[] | null {
  if (!isWebPart(part)) return null;
  
  try {
    // Try parsing as JSON array of results
    const parsed = JSON.parse(part.text);
    if (Array.isArray(parsed)) {
      return parsed.filter(r => r.url);
    }
    // Single result object
    if (parsed.url) {
      return [parsed];
    }
  } catch {
    // Not JSON - try extracting URLs from text
    const urlRegex = /https?:\/\/[^\s<>"{}|\\^`\[\]]+/g;
    const urls = part.text.match(urlRegex);
    if (urls) {
      return urls.map(url => ({ url }));
    }
  }
  
  return null;
}

// Categorize parts by type for rendering
export function categorizePartsByType(parts: Part[]): Map<PartType, Part[]> {
  const categories = new Map<PartType, Part[]>();
  
  for (const part of parts) {
    const existing = categories.get(part.type) || [];
    existing.push(part);
    categories.set(part.type, existing);
  }
  
  return categories;
}