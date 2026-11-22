/** @jest-environment node */
const { watchTaskOutput } = require('../src/lib/task-output-stream')

const taskId = 'task/one'
const replay = (outputs = [], has_more = false, next_cursor = outputs.at(-1)?.cursor ?? 0) =>
  new Response(JSON.stringify({ task_id: taskId, outputs, next_cursor, has_more }), {
    headers: { 'Content-Type': 'application/json' },
  })
const output = (cursor, text = 'hello') => ({ cursor, output: text })
const event = (name, data, id = '') =>
  `event: ${name}\r\nid: ${id}\r\ndata: ${JSON.stringify(data)}\r\n\r\n`
const stream = (text, fragment = false) => {
  const bytes = new TextEncoder().encode(text)
  return new Response(new ReadableStream({
    start(controller) {
      if (fragment) for (const byte of bytes) controller.enqueue(Uint8Array.of(byte))
      else controller.enqueue(bytes)
      controller.close()
    },
  }), { headers: { 'Content-Type': 'text/event-stream' } })
}
let controller, callbacks, options
const originalFetch = global.fetch
beforeEach(() => {
  controller = new AbortController()
  callbacks = {
    onOutput: jest.fn(), onConnection: jest.fn(), onDone: jest.fn(), onError: jest.fn(),
  }
  options = {
    apiUrl: 'https://api.example/', taskId, signal: controller.signal,
    getHeaders: () => ({ Authorization: 'Bearer test-credential', 'X-Tenant-ID': 'tenant-one' }),
    retryMs: 0, ...callbacks,
  }
  global.fetch = jest.fn()
})
afterEach(() => { controller.abort(); global.fetch = originalFetch })

test('drains all replay pages before SSE, uses header auth, and deduplicates replayed cursors', async () => {
  fetch.mockResolvedValueOnce(replay([output(1)], true))
    .mockResolvedValueOnce(replay([output(2)]))
    .mockResolvedValueOnce(stream(event('output', output(2), '2') +
      event('output', output(3), '3') + event('done', { status: 'completed', next_cursor: 3 })))
    .mockResolvedValueOnce(replay([output(3)]))
  await watchTaskOutput(options)
  expect(callbacks.onOutput.mock.calls.map(([chunk]) => chunk.cursor)).toEqual([1, 2, 3])
  expect(fetch.mock.calls.map(([url]) => url)).toEqual([
    'https://api.example/v1/agent/tasks/task%2Fone/output?since=0',
    'https://api.example/v1/agent/tasks/task%2Fone/output?since=1',
    'https://api.example/v1/agent/tasks/task%2Fone/output/stream?since=2',
    'https://api.example/v1/agent/tasks/task%2Fone/output?since=3',
  ])
  for (const [url, init] of fetch.mock.calls) {
    expect(url).not.toContain('test-credential')
    expect(url).not.toContain('access_token')
    expect(init.headers.Authorization).toBe('Bearer test-credential')
    expect(init.headers['X-Tenant-ID']).toBe('tenant-one')
  }
  expect(fetch.mock.calls[2][1].headers['Last-Event-ID']).toBe('2')
  expect(callbacks.onDone).toHaveBeenCalledWith('completed')
  expect(callbacks.onConnection).toHaveBeenLastCalledWith(false)
})

test('decodes fragmented UTF-8, split CRLF, comments, and multiline SSE data', async () => {
  const text = ': keepalive\r\n\r\nevent: output\r\nid: 1\r\n' +
    'data: {"cursor":1,\r\ndata: "output":"héllo 🐢"}\r\n\r\n' +
    event('done', { status: 'failed', next_cursor: 1 })
  fetch.mockResolvedValueOnce(replay())
    .mockResolvedValueOnce(stream(text, true))
    .mockResolvedValueOnce(replay([output(1, 'héllo 🐢')]))
  await watchTaskOutput(options)
  expect(callbacks.onOutput).toHaveBeenCalledWith(output(1, 'héllo 🐢'))
  expect(callbacks.onDone).toHaveBeenCalledWith('failed')
})

test('reconnects by replaying from the last consumed cursor with fresh credentials', async () => {
  let credential = 'first'
  options.getHeaders = () => ({ Authorization: `Bearer ${credential}` })
  fetch.mockResolvedValueOnce(replay([output(1)]))
    .mockImplementationOnce(async () => {
      credential = 'refreshed'
      return stream(event('output', output(2), '2'))
    })
    .mockResolvedValueOnce(replay([output(3)]))
    .mockResolvedValueOnce(stream(event('done', { status: 'cancelled', next_cursor: 3 })))
    .mockResolvedValueOnce(replay([output(3)]))
  await watchTaskOutput(options)
  expect(callbacks.onOutput.mock.calls.map(([chunk]) => chunk.cursor)).toEqual([1, 2, 3])
  expect(fetch.mock.calls[2][0]).toContain('?since=2')
  expect(fetch.mock.calls[2][1].headers.Authorization).toBe('Bearer refreshed')
  expect(fetch.mock.calls[3][1].headers['Last-Event-ID']).toBe('3')
  expect(callbacks.onDone).toHaveBeenCalledWith('cancelled')
})

test.each([401, 403, 404, 422])('stops on HTTP %s instead of reconnecting indefinitely', async (status) => {
  fetch.mockResolvedValueOnce(new Response('', { status }))
  await watchTaskOutput(options)
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(callbacks.onError).toHaveBeenCalledWith(expect.stringContaining(`HTTP ${status}`))
  expect(callbacks.onDone).not.toHaveBeenCalled()
})

test.each([
  [() => replay([output(2)]), 'cursor gap'],
  [() => replay([], true), 'did not advance'],
  [() => replay([output(1)], false, 4), 'did not advance'],
  [() => replay([output(0)]), 'invalid cursor'],
  [() => new Response('{'), 'invalid JSON'],
  [() => new Response(JSON.stringify({ task_id: 'other' })), 'invalid response'],
])('rejects malformed replay without opening SSE (%#)', async (response, error) => {
  fetch.mockResolvedValueOnce(response())
  await watchTaskOutput(options)
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(callbacks.onError).toHaveBeenCalledWith(expect.stringContaining(error))
})

test.each([
  [() => stream(event('output', output(1), '2')), 'invalid cursor'],
  [() => stream(event('output', output(2), '2')), 'cursor gap'],
  [() => stream('event: output\ndata: {\n\n'), 'invalid JSON'],
  [() => stream(event('done', { status: 'running' })), 'invalid terminal status'],
  [() => new Response('not SSE'), 'invalid response'],
])('rejects invalid stream contracts without retry (%#)', async (response, error) => {
  fetch.mockResolvedValueOnce(replay()).mockResolvedValueOnce(response())
  await watchTaskOutput(options)
  expect(fetch).toHaveBeenCalledTimes(2)
  expect(callbacks.onError).toHaveBeenCalledWith(expect.stringContaining(error))
  expect(callbacks.onDone).not.toHaveBeenCalled()
})

test('retries transient storage failure then reauthorizes replay', async () => {
  fetch.mockResolvedValueOnce(new Response('', { status: 503 }))
    .mockResolvedValueOnce(replay())
    .mockResolvedValueOnce(stream(event('done', { status: 'completed', next_cursor: 0 })))
    .mockResolvedValueOnce(replay())
  await watchTaskOutput(options)
  expect(fetch).toHaveBeenCalledTimes(4)
  expect(callbacks.onDone).toHaveBeenCalledWith('completed')
})

test('abort cancels an established stream and suppresses later callbacks', async () => {
  const cancel = jest.fn()
  fetch.mockResolvedValueOnce(replay()).mockResolvedValueOnce(new Response(
    new ReadableStream({ cancel }), { headers: { 'Content-Type': 'text/event-stream' } },
  ))
  callbacks.onConnection.mockImplementation((connected) => {
    if (connected) queueMicrotask(() => controller.abort())
  })
  await watchTaskOutput(options)
  expect(cancel).toHaveBeenCalled()
  expect(callbacks.onDone).not.toHaveBeenCalled()
  expect(callbacks.onError).not.toHaveBeenCalledWith(expect.any(String))
  expect(fetch).toHaveBeenCalledTimes(2)
})