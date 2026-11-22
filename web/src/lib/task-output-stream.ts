/** Ordered, authenticated durable replay followed by cursor-based SSE. */
import { OutputError, outputGapError } from './task-output-errors'

type Output = { cursor: number; [key: string]: unknown }
type Options = {
  apiUrl: string
  taskId: string
  signal: AbortSignal
  getHeaders: () => Record<string, string>
  onOutput: (output: Output) => void
  onConnection: (connected: boolean) => void
  onDone: (status: string) => void
  onError: (message: string | null) => void
  retryMs?: number
  requestTimeoutMs?: number
}

function cursor(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0
}

/** Legacy task-scoped payloads omit the ID; an explicit ID must match. */
function checkTaskIdentity(value: object, taskId: string): void {
  if ('task_id' in value && value.task_id !== taskId) {
    throw new OutputError('Task output belongs to a different task.', true)
  }
}

async function checkedFetch(url: string, options: RequestInit): Promise<Response> {
  const response = await fetch(url, options)
  if (!response.ok) {
    throw new OutputError(`Task output unavailable (HTTP ${response.status}).`,
      [401, 403, 404, 422].includes(response.status))
  }
  return response
}

/** Bound replay bodies and stream handshakes, not an established SSE connection. */
async function request<T>(
  url: string, options: RequestInit, signal: AbortSignal, timeoutMs: number,
  consume: (response: Response, signal: AbortSignal) => Promise<T>, stream = false,
): Promise<T> {
  const controller = new AbortController()
  const abort = () => controller.abort()
  let timedOut = false
  signal.addEventListener('abort', abort, { once: true })
  if (signal.aborted) controller.abort()
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)
  try {
    const response = await checkedFetch(url, { ...options, signal: controller.signal })
    if (stream) clearTimeout(timer)
    return await consume(response, controller.signal)
  } catch (error) {
    if (timedOut && !signal.aborted) {
      throw new OutputError('Task output request timed out. Reconnecting…')
    }
    throw error
  } finally {
    clearTimeout(timer)
    signal.removeEventListener('abort', abort)
  }
}

/** Decode SSE frames across arbitrary UTF-8/chunk/newline boundaries. */
async function readEvents(
  body: ReadableStream<Uint8Array>, signal: AbortSignal,
  onEvent: (event: string, data: string, id: string) => boolean,
): Promise<void> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let pending = '', event = '', id = ''
  let data: string[] = []
  let frameSize = 0
  const cancel = () => { void reader.cancel().catch(() => undefined) }
  signal.addEventListener('abort', cancel, { once: true })
  try {
    while (!signal.aborted) {
      const chunk = await reader.read()
      if (chunk.done) return
      pending += decoder.decode(chunk.value, { stream: true })
      if (pending.length + frameSize > 1024 * 1024) {
        throw new OutputError('Task output frame is too large.', true)
      }
      while (true) {
        const match = /\r\n|\r|\n/.exec(pending)
        if (!match || (match[0] === '\r' && match.index === pending.length - 1)) break
        const line = pending.slice(0, match.index)
        pending = pending.slice(match.index + match[0].length)
        if (!line) {
          if (data.length && onEvent(event || 'message', data.join('\n'), id)) return
          event = ''; id = ''; data = []; frameSize = 0
        } else if (!line.startsWith(':')) {
          frameSize += line.length
          const colon = line.indexOf(':')
          const field = colon < 0 ? line : line.slice(0, colon)
          const value = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '')
          if (field === 'event') event = value
          if (field === 'id') id = value
          if (field === 'data') data.push(value)
        }
      }
    }
  } finally {
    signal.removeEventListener('abort', cancel)
    await reader.cancel().catch(() => undefined)
    reader.releaseLock()
  }
}
function delay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    if (signal.aborted) { resolve(); return }
    const finish = () => {
      clearTimeout(timer)
      signal.removeEventListener('abort', finish)
      resolve()
    }
    const timer = setTimeout(finish, ms)
    signal.addEventListener('abort', finish, { once: true })
  })
}

/** Reauthorize and drain replay on every reconnect; never put credentials in URLs. */
export async function watchTaskOutput(options: Options): Promise<void> {
  const { signal, taskId, getHeaders, onOutput, onConnection, onDone, onError } = options
  const base = `${options.apiUrl.replace(/\/$/, '')}/v1/agent/tasks/${encodeURIComponent(taskId)}/output`
  let since = 0
  let done = false
  const ingest = (value: unknown) => {
    if (!value || typeof value !== 'object' || !('cursor' in value) ||
        !cursor(value.cursor) || value.cursor === 0) {
      throw new OutputError('Task output has an invalid cursor.', true)
    }
    checkTaskIdentity(value, taskId)
    if (value.cursor <= since) return
    if (value.cursor !== since + 1) {
      throw new OutputError('Task output cursor gap.', true)
    }
    onOutput(value as Output)
    since = value.cursor
  }
  const drainReplay = async (terminalStatus?: string) => {
      let hasMore = true
      while (hasMore && !signal.aborted) {
        const page = await request(`${base}?since=${since}`, {
          headers: getHeaders(), signal, cache: 'no-store',
        }, signal, options.requestTimeoutMs ?? 20_000,
        async (response) => {
          try { return await response.json() } catch (error) {
            // Fetch implementations may create exceptions in another JS realm.
            if (error && typeof error === 'object' && 'name' in error &&
                error.name === 'SyntaxError') {
              throw new OutputError('Task output replay returned invalid JSON.', true)
            }
            throw error
          }
        })
        if (signal.aborted) return
        if (!page || page.task_id !== taskId || !Array.isArray(page.outputs) ||
            !cursor(page.next_cursor) || typeof page.has_more !== 'boolean') {
          throw new OutputError('Task output replay returned an invalid response.', true)
        }
        // Older task-scoped replay responses may omit status. An explicit state
        // must agree with the terminal event before completion is authorized.
        if (terminalStatus !== undefined && 'status' in page && page.status !== terminalStatus) {
          throw new OutputError('Task output replay disagrees with its terminal status.', true)
        }
        const previous = since
        for (const output of page.outputs) ingest(output)
        if (page.next_cursor !== since || (page.has_more && since <= previous)) {
          throw new OutputError('Task output replay did not advance its cursor.', true)
        }
        hasMore = page.has_more
      }
  }
  while (!signal.aborted && !done) {
    try {
      let terminal: { status: string; nextCursor?: number } | undefined
      await drainReplay()
      if (signal.aborted) return
      await request(`${base}/stream?since=${since}`, {
        headers: { ...getHeaders(), Accept: 'text/event-stream', 'Last-Event-ID': String(since) },
        signal, cache: 'no-store',
      }, signal, options.requestTimeoutMs ?? 20_000, async (response, streamSignal) => {
        if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
          throw new OutputError('Task output stream returned an invalid response.', true)
        }
        onError(null)
        onConnection(true)
        await readEvents(response.body, streamSignal, (event, data, id) => {
        if (signal.aborted) return true
        if (event !== 'output' && event !== 'done' && event !== 'lag') return false
        let payload: unknown
        try { payload = JSON.parse(data) } catch {
          throw new OutputError('Task output stream returned invalid JSON.', true)
        }
        if (event === 'lag') throw outputGapError(payload, taskId)
        if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
          throw new OutputError('Task output stream returned an invalid event.', true)
        }
        checkTaskIdentity(payload, taskId)
        const fields = payload as Record<string, unknown>
        if (event === 'output') {
          if (!/^[1-9]\d*$/.test(id) || !cursor(Number(id)) || Number(id) !== fields.cursor) {
            throw new OutputError('Task output stream has an invalid cursor.', true)
          }
          ingest(payload)
        } else {
          const status = fields.status
          if (typeof status !== 'string' || !['completed', 'failed', 'cancelled'].includes(status)) {
            throw new OutputError('Task output stream has an invalid terminal status.', true)
          }
          if ('next_cursor' in fields &&
              (!cursor(fields.next_cursor) || fields.next_cursor < since)) {
            throw new OutputError('Task output stream has an invalid terminal cursor.', true)
          }
          terminal = { status, nextCursor: fields.next_cursor as number | undefined }
          // Stop the reader, but do not report completion until replay has
          // accounted for any trailing output (including legacy done events).
          return true
        }
        return false
        })
      }, true)
      if (terminal && !signal.aborted) {
        // Output position alone cannot prove completion: refresh authorization
        // and reconcile state even when the terminal cursor is already consumed.
        await drainReplay(terminal.status)
        if (signal.aborted) return
        if (terminal.nextCursor !== undefined && since !== terminal.nextCursor) {
          throw new OutputError('Task output replay did not reach its terminal cursor.', true)
        }
        done = true
        onDone(terminal.status)
      }
      if (!signal.aborted && !done) onError('Task output disconnected; reconnecting…')
    } catch (error) {
      if (signal.aborted) return
      onError(error instanceof Error ? error.message : 'Task output unavailable.')
      if (error instanceof OutputError && error.permanent) return
    } finally {
      if (!signal.aborted) onConnection(false)
    }
    if (!done) await delay(options.retryMs ?? 2000, signal)
  }
}