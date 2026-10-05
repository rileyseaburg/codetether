/** Reject unavailable or malformed task data instead of inventing an empty queue. */
export function readTaskQueue(data: unknown): Record<string, unknown>[] {
  const rows = Array.isArray(data)
    ? data
    : data && typeof data === 'object' && 'tasks' in data
      ? data.tasks
      : undefined
  if (
    !Array.isArray(rows) ||
    !rows.every(
      (row) =>
        row &&
        typeof row === 'object' &&
        typeof row.id === 'string' &&
        row.id.trim().length > 0 &&
        typeof row.status === 'string' &&
        (row.agent_type == null || typeof row.agent_type === 'string') &&
        typeof row.created_at === 'string' &&
        ['title', 'prompt', 'result', 'error'].every(
          (key) => row[key] == null || typeof row[key] === 'string',
        ),
    )
  ) {
    throw new Error(
      'The task service returned an unreadable response. Please retry.',
    )
  }
  return rows
}

/** API errors can contain validation arrays or objects; keep feedback renderable. */
export function taskRequestError(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message
  if (error && typeof error === 'object' && 'detail' in error) {
    const detail = error.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail)) {
      const messages = detail.flatMap((item) =>
        item && typeof item.msg === 'string' ? [item.msg] : [],
      )
      if (messages.length) return messages.join('; ')
    }
  }
  return fallback
}
