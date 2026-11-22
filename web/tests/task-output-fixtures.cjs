const taskId = 'task/one'
const output = (cursor) => ({ cursor, output: `chunk ${cursor}` })
const replay = (outputs = []) => new Response(JSON.stringify({
  task_id: taskId, outputs, next_cursor: outputs.at(-1)?.cursor ?? 0, has_more: false,
}), { headers: { 'Content-Type': 'application/json' } })
const event = (name, data, id = '') =>
  `event: ${name}\nid: ${id}\ndata: ${JSON.stringify(data)}\n\n`
const stream = (...events) => new Response(events.join(''), {
  headers: { 'Content-Type': 'text/event-stream' },
})
const gap = (replay_available = false) => ({
  task_id: taskId, error: 'output_gap', skipped_bus_events: 2, replay_available,
})

function context() {
  const originalFetch = global.fetch
  const controller = new AbortController()
  const callbacks = {
    onOutput: jest.fn(), onConnection: jest.fn(), onDone: jest.fn(), onError: jest.fn(),
  }
  const options = {
    apiUrl: 'https://api.example', taskId, signal: controller.signal, retryMs: 0,
    getHeaders: jest.fn(() => ({ Authorization: 'Bearer initial', 'X-Tenant-ID': 'tenant-one' })),
    ...callbacks,
  }
  global.fetch = jest.fn()
  const close = () => { controller.abort(); global.fetch = originalFetch }
  return { callbacks, options, close }
}

module.exports = { taskId, output, replay, event, stream, gap, context }