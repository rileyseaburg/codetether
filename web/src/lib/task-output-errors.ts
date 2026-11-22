/** Classify transport failures so permanent contract errors never retry. */
export class OutputError extends Error {
  constructor(message: string, readonly permanent = false) { super(message) }
}

/** A gap ends the current stream; retry only when the server offers replay. */
export function outputGapError(payload: unknown, taskId: string): OutputError {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return new OutputError('Task output stream has an invalid gap event.', true)
  }
  const gap = payload as Record<string, unknown>
  if (gap.task_id !== taskId || gap.error !== 'output_gap' ||
      typeof gap.replay_available !== 'boolean' ||
      typeof gap.skipped_bus_events !== 'number' ||
      !Number.isSafeInteger(gap.skipped_bus_events) || gap.skipped_bus_events <= 0) {
    return new OutputError('Task output stream has an invalid gap event.', true)
  }
  // This count describes the shared bus, not the number of lost task chunks.
  return new OutputError(
    gap.replay_available
      ? 'Task output stream lost events; recovering from replay…'
      : 'Task output is incomplete: the stream lost events and replay is unavailable.',
    !gap.replay_available,
  )
}