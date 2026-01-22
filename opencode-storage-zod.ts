import * as z from 'zod';

export const MessageRoleSchema = z.enum(['user', 'assistant']);
export const MessageModeSchema = z.enum(['build', 'chat', 'plan']);
export const TodoStatusSchema = z.enum(['pending', 'in_progress', 'completed', 'cancelled']);
export const TodoPrioritySchema = z.enum(['high', 'medium', 'low']);

export const TimestampsSchema = z.object({
  created: z.number(),
  updated: z.number().optional(),
});

export const MessageTimeSchema = z.object({
  created: z.number(),
  completed: z.number().optional(),
});

export const PartTimeSchema = z.object({
  start: z.number().optional(),
  end: z.number().optional(),
});

export const SandboxConfigSchema = z.record(z.unknown());

export const ProjectSchema = z.object({
  id: z.string(),
  worktree: z.string(),
  vcs: z.string().optional(),
  time: z.object({
    created: z.number(),
    updated: z.number(),
  }),
  sandboxes: z.array(SandboxConfigSchema),
});

export const SessionSummarySchema = z.object({
  additions: z.number().optional(),
  deletions: z.number().optional(),
  files: z.number().optional(),
});

export const SessionSchema = z.object({
  id: z.string(),
  version: z.string(),
  projectID: z.string(),
  directory: z.string(),
  title: z.string(),
  time: z.object({
    created: z.number(),
    updated: z.number(),
  }),
  summary: SessionSummarySchema.optional(),
});

export const MessagePathSchema = z.object({
  cwd: z.string().optional(),
  root: z.string().optional(),
});

export const TokenCacheSchema = z.object({
  read: z.number().optional(),
  write: z.number().optional(),
});

export const MessageTokensSchema = z.object({
  input: z.number().optional(),
  output: z.number().optional(),
  reasoning: z.number().optional(),
  cache: TokenCacheSchema.optional(),
});

export const MessageModelSchema = z.object({
  providerID: z.string().optional(),
  modelID: z.string().optional(),
});

export const DiffSchema = z.object({
  file: z.string(),
  before: z.string(),
  after: z.string(),
  additions: z.number(),
  deletions: z.number(),
});

export const MessageSummarySchema = z.object({
  title: z.string().optional(),
  diffs: z.array(DiffSchema).optional(),
});

export const MessageSchema = z.object({
  id: z.string(),
  sessionID: z.string(),
  role: MessageRoleSchema,
  time: MessageTimeSchema,
  summary: MessageSummarySchema.optional(),
  parentID: z.string().optional(),
  modelID: z.string().optional(),
  providerID: z.string().optional(),
  mode: z.string().optional(),
  path: MessagePathSchema.optional(),
  cost: z.number().optional(),
  tokens: MessageTokensSchema.optional(),
  agent: z.string().optional(),
  model: MessageModelSchema.optional(),
});

export const PartSchema = z.object({
  id: z.string(),
  sessionID: z.string(),
  messageID: z.string(),
  type: z.string(),
  text: z.string(),
  time: PartTimeSchema.optional(),
});

export const SessionDiffSchema = z.array(DiffSchema);

export const TodoSchema = z.object({
  id: z.string(),
  content: z.string(),
  status: TodoStatusSchema,
  priority: TodoPrioritySchema,
});

export const TodoListSchema = z.array(TodoSchema);

export type ValidatedProject = z.infer<typeof ProjectSchema>;
export type ValidatedSession = z.infer<typeof SessionSchema>;
export type ValidatedMessage = z.infer<typeof MessageSchema>;
export type ValidatedPart = z.infer<typeof PartSchema>;
export type ValidatedSessionDiff = z.infer<typeof SessionDiffSchema>;
export type ValidatedTodo = z.infer<typeof TodoSchema>;
export type ValidatedTodoList = z.infer<typeof TodoListSchema>;

export function validateProject(data: unknown): ValidatedProject {
  return ProjectSchema.parse(data);
}

export function validateProjectSafe(data: unknown): z.SafeParseReturnType<unknown, ValidatedProject> {
  return ProjectSchema.safeParse(data);
}

export function validateSession(data: unknown): ValidatedSession {
  return SessionSchema.parse(data);
}

export function validateSessionSafe(data: unknown): z.SafeParseReturnType<unknown, ValidatedSession> {
  return SessionSchema.safeParse(data);
}

export function validateMessage(data: unknown): ValidatedMessage {
  return MessageSchema.parse(data);
}

export function validateMessageSafe(data: unknown): z.SafeParseReturnType<unknown, ValidatedMessage> {
  return MessageSchema.safeParse(data);
}

export function validatePart(data: unknown): ValidatedPart {
  return PartSchema.parse(data);
}

export function validatePartSafe(data: unknown): z.SafeParseReturnType<unknown, ValidatedPart> {
  return PartSchema.safeParse(data);
}

export function validateSessionDiff(data: unknown): ValidatedSessionDiff {
  return SessionDiffSchema.parse(data);
}

export function validateSessionDiffSafe(data: unknown): z.SafeParseReturnType<unknown, ValidatedSessionDiff> {
  return SessionDiffSchema.safeParse(data);
}

export function validateTodo(data: unknown): ValidatedTodo {
  return TodoSchema.parse(data);
}

export function validateTodoSafe(data: unknown): z.SafeParseReturnType<unknown, ValidatedTodo> {
  return TodoSchema.safeParse(data);
}

export function validateTodoList(data: unknown): ValidatedTodoList {
  return TodoListSchema.parse(data);
}

export function validateTodoListSafe(data: unknown): z.SafeParseReturnType<unknown, ValidatedTodoList> {
  return TodoListSchema.safeParse(data);
}

export function isProject(data: unknown): data is ValidatedProject {
  return ProjectSchema.safeParse(data).success;
}

export function isSession(data: unknown): data is ValidatedSession {
  return SessionSchema.safeParse(data).success;
}

export function isMessage(data: unknown): data is ValidatedMessage {
  return MessageSchema.safeParse(data).success;
}

export function isPart(data: unknown): data is ValidatedPart {
  return PartSchema.safeParse(data).success;
}

export function isSessionDiff(data: unknown): data is ValidatedSessionDiff {
  return SessionDiffSchema.safeParse(data).success;
}

export function isTodo(data: unknown): data is ValidatedTodo {
  return TodoSchema.safeParse(data).success;
}

export function isTodoList(data: unknown): data is ValidatedTodoList {
  return TodoListSchema.safeParse(data).success;
}