/** @jest-environment node */
// Mocked local: exercise the real consumer with fixture-backed HTTP/SSE.
const { watchTaskOutput } = require('../src/lib/task-output-stream')
const { taskId, output, replay, event, stream, context } = require('./task-output-fixtures.cjs')
let ctx
beforeEach(() => { ctx = context() })
afterEach(() => ctx.close())

function page(outputs, next_cursor, has_more = false, status) {
  return new Response(JSON.stringify({ task_id: taskId, outputs, next_cursor, has_more, status }), {
    headers: { 'Content-Type': 'application/json' },
  })
}

test.each(['completed', 'failed', 'cancelled'])('accepts matching durable %s status', async (status) => {
  fetch.mockResolvedValueOnce(replay())
    .mockResolvedValueOnce(stream(event('done', { status, next_cursor: 1 })))
    .mockResolvedValueOnce(page([output(1)], 1, false, status))
  await watchTaskOutput(ctx.options)
  expect(ctx.callbacks.onOutput).toHaveBeenCalledWith(output(1))
  expect(ctx.callbacks.onDone).toHaveBeenCalledWith(status)
  expect(ctx.callbacks.onError.mock.calls.filter(([error]) => error !== null)).toEqual([])
})

test('rejects a status conflict on a later replay page before delivering its output', async () => {
  fetch.mockResolvedValueOnce(replay())
    .mockResolvedValueOnce(stream(event('done', { status: 'completed', next_cursor: 2 })))
    .mockResolvedValueOnce(page([output(1)], 1, true, 'completed'))
    .mockResolvedValueOnce(page([output(2)], 2, false, 'failed'))
  await watchTaskOutput(ctx.options)
  expect(ctx.callbacks.onOutput).toHaveBeenCalledTimes(1)
  expect(ctx.callbacks.onOutput).toHaveBeenCalledWith(output(1))
  expect(ctx.callbacks.onDone).not.toHaveBeenCalled()
  expect(ctx.callbacks.onError).toHaveBeenCalledWith(
    'Task output replay disagrees with its terminal status.',
  )
  expect(fetch).toHaveBeenCalledTimes(4)
})

test.each(['completed', 'failed', 'cancelled'])(
  'reauthorizes already-consumed output before reporting %s', async (status) => {
    fetch.mockResolvedValueOnce(replay([output(1)]))
      .mockResolvedValueOnce(stream(event('done', { status, next_cursor: 1 })))
      .mockImplementationOnce(() => {
        expect(ctx.callbacks.onDone).not.toHaveBeenCalled()
        return Promise.resolve(page([], 1, false, status))
      })
    await watchTaskOutput(ctx.options)
    expect(ctx.callbacks.onOutput).toHaveBeenCalledTimes(1)
    expect(ctx.callbacks.onDone).toHaveBeenCalledTimes(1)
    expect(ctx.callbacks.onDone).toHaveBeenCalledWith(status)
    expect(fetch.mock.calls[2][0]).toContain('output?since=1')
    expect(fetch.mock.calls[2][1].headers).toMatchObject({
      Authorization: 'Bearer initial', 'X-Tenant-ID': 'tenant-one',
    })
    expect(ctx.options.getHeaders).toHaveBeenCalledTimes(3)
  },
)

test('revoked access blocks completion even when output is already consumed', async () => {
  fetch.mockResolvedValueOnce(replay([output(1)]))
    .mockResolvedValueOnce(stream(event('done', { status: 'completed', next_cursor: 1 })))
    .mockResolvedValueOnce(new Response('', { status: 403 }))
  await watchTaskOutput(ctx.options)
  expect(ctx.callbacks.onOutput).toHaveBeenCalledTimes(1)
  expect(ctx.callbacks.onDone).not.toHaveBeenCalled()
  expect(ctx.callbacks.onError).toHaveBeenCalledWith('Task output unavailable (HTTP 403).')
  expect(fetch.mock.calls[2][0]).toContain('output?since=1')
  expect(ctx.options.getHeaders).toHaveBeenCalledTimes(3)
  expect(fetch).toHaveBeenCalledTimes(3)
})

test.each(['completed', 'failed', 'cancelled'])('replays trailing pages before %s completion', async (status) => {
  const order = []
  ctx.callbacks.onOutput.mockImplementation((chunk) => order.push(chunk.cursor))
  ctx.callbacks.onDone.mockImplementation(() => order.push('done'))
  fetch.mockResolvedValueOnce(replay([output(1)]))
    .mockResolvedValueOnce(stream(event('output', output(2), '2'),
      event('done', { task_id: taskId, status, next_cursor: 5 })))
    .mockResolvedValueOnce(page([output(3), output(4)], 4, true))
    .mockResolvedValueOnce(page([output(5)], 5))
  await watchTaskOutput(ctx.options)
  expect(order).toEqual([1, 2, 3, 4, 5, 'done'])
  expect(ctx.callbacks.onDone).toHaveBeenCalledWith(status)
  expect(ctx.callbacks.onError.mock.calls.filter(([error]) => error !== null)).toEqual([])
  expect(fetch.mock.calls[2][0]).toContain('output?since=2')
  expect(fetch.mock.calls[3][0]).toContain('output?since=4')
  expect(ctx.options.getHeaders).toHaveBeenCalledTimes(4)
})

test('legacy cursorless completion gets a final authenticated replay', async () => {
  fetch.mockResolvedValueOnce(replay([output(1)]))
    .mockResolvedValueOnce(stream(event('done', { status: 'completed' })))
    .mockResolvedValueOnce(replay([output(2)]))
  await watchTaskOutput(ctx.options)
  expect(ctx.callbacks.onOutput.mock.calls.map(([chunk]) => chunk.cursor)).toEqual([1, 2])
  expect(ctx.callbacks.onDone).toHaveBeenCalledWith('completed')
  expect(fetch.mock.calls[2][1].headers).toMatchObject({
    Authorization: 'Bearer initial', 'X-Tenant-ID': 'tenant-one',
  })
})

test.each([-1, 0, 1.5, null, '2', Number.MAX_SAFE_INTEGER + 1])(
  'rejects invalid or backward terminal cursor %p without completion', async (next_cursor) => {
    fetch.mockResolvedValueOnce(replay([output(1)]))
      .mockResolvedValueOnce(stream(event('done', { status: 'completed', next_cursor })))
    await watchTaskOutput(ctx.options)
    expect(ctx.callbacks.onDone).not.toHaveBeenCalled()
    expect(ctx.callbacks.onError).toHaveBeenCalledWith('Task output stream has an invalid terminal cursor.')
    expect(fetch).toHaveBeenCalledTimes(2)
  },
)

test.each([
  [3, [output(2)]],
  [2, [output(2), output(3)]],
])('rejects replay that does not reach terminal cursor %s exactly', async (next_cursor, outputs) => {
  fetch.mockResolvedValueOnce(replay([output(1)]))
    .mockResolvedValueOnce(stream(event('done', { status: 'completed', next_cursor })))
    .mockResolvedValueOnce(replay(outputs))
  await watchTaskOutput(ctx.options)
  expect(ctx.callbacks.onDone).not.toHaveBeenCalled()
  expect(ctx.callbacks.onError).toHaveBeenCalledWith('Task output replay did not reach its terminal cursor.')
  expect(fetch).toHaveBeenCalledTimes(3)
})

test('revoked replay authorization cannot become successful completion', async () => {
  fetch.mockResolvedValueOnce(replay())
    .mockResolvedValueOnce(stream(event('done', { status: 'completed' })))
    .mockResolvedValueOnce(new Response('', { status: 403 }))
  await watchTaskOutput(ctx.options)
  expect(ctx.callbacks.onDone).not.toHaveBeenCalled()
  expect(ctx.callbacks.onError).toHaveBeenCalledWith('Task output unavailable (HTTP 403).')
  expect(fetch).toHaveBeenCalledTimes(3)
})

test('transient final replay failure reconnects instead of completing', async () => {
  fetch.mockResolvedValueOnce(replay([output(1)]))
    .mockResolvedValueOnce(stream(event('done', { status: 'completed', next_cursor: 2 })))
    .mockResolvedValueOnce(new Response('', { status: 503 }))
    .mockResolvedValueOnce(replay([output(2)]))
    .mockResolvedValueOnce(stream(event('done', { status: 'completed', next_cursor: 2 })))
    .mockResolvedValueOnce(replay([output(2)]))
  await watchTaskOutput(ctx.options)
  expect(ctx.callbacks.onError).toHaveBeenCalledWith('Task output unavailable (HTTP 503).')
  expect(ctx.callbacks.onDone).toHaveBeenCalledTimes(1)
  expect(ctx.callbacks.onDone).toHaveBeenCalledWith('completed')
  expect(fetch.mock.calls[3][0]).toContain('output?since=1')
})

test.each(['working', 'failed', 'cancelled', '', null, 42])(
  'rejects final replay status %p conflicting with completion', async (status) => {
    fetch.mockResolvedValueOnce(replay())
      .mockResolvedValueOnce(stream(event('done', { status: 'completed', next_cursor: 0 })))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        task_id: taskId, outputs: [], next_cursor: 0, has_more: false, status,
      })))
    await watchTaskOutput(ctx.options)
    expect(ctx.callbacks.onDone).not.toHaveBeenCalled()
    expect(ctx.callbacks.onError).toHaveBeenCalledWith(
      'Task output replay disagrees with its terminal status.',
    )
    expect(fetch).toHaveBeenCalledTimes(3)
  },
)

test('legacy cursorless completion cannot contradict explicit durable state', async () => {
  fetch.mockResolvedValueOnce(replay())
    .mockResolvedValueOnce(stream(event('done', { status: 'completed' })))
    .mockResolvedValueOnce(new Response(JSON.stringify({
      task_id: taskId, outputs: [], next_cursor: 0, has_more: false, status: 'failed',
    })))
  await watchTaskOutput(ctx.options)
  expect(ctx.callbacks.onDone).not.toHaveBeenCalled()
  expect(ctx.callbacks.onError).toHaveBeenCalledWith(
    'Task output replay disagrees with its terminal status.',
  )
  expect(fetch).toHaveBeenCalledTimes(3)
})

test('cancellation during final replay suppresses completion', async () => {
  fetch.mockResolvedValueOnce(replay())
    .mockResolvedValueOnce(stream(event('done', { status: 'cancelled' })))
    .mockImplementationOnce(() => {
      ctx.close()
      throw new DOMException('Aborted', 'AbortError')
    })
  await watchTaskOutput(ctx.options)
  expect(ctx.callbacks.onDone).not.toHaveBeenCalled()
  expect(ctx.callbacks.onError.mock.calls.filter(([error]) => error !== null)).toEqual([])
})