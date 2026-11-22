/** @jest-environment node */
const { watchTaskOutput } = require('../src/lib/task-output-stream')
const { context, output, replay, stream, event, gap } = require('./task-output-fixtures.cjs')
let ctx
beforeEach(() => { ctx = context() })
afterEach(() => ctx.close())

test('recoverable gaps replay from the last cursor with fresh credentials', async () => {
  fetch.mockResolvedValueOnce(replay())
    .mockResolvedValueOnce(stream(event('output', output(1), '1'), event('lag', gap(true))))
    .mockResolvedValueOnce(replay([output(2)]))
    .mockResolvedValueOnce(stream(
      event('output', output(2), '2'), event('output', output(3), '3'),
      event('done', { status: 'completed', next_cursor: 3 }),
    ))
    .mockResolvedValueOnce(replay([output(3)]))
  ctx.options.getHeaders
    .mockReturnValueOnce({ Authorization: 'Bearer initial', 'X-Tenant-ID': 'tenant-one' })
    .mockReturnValueOnce({ Authorization: 'Bearer initial', 'X-Tenant-ID': 'tenant-one' })
    .mockReturnValue({ Authorization: 'Bearer refreshed', 'X-Tenant-ID': 'tenant-one' })
  await watchTaskOutput(ctx.options)
  expect(fetch).toHaveBeenCalledTimes(5)
  expect(ctx.callbacks.onOutput.mock.calls.map(([chunk]) => chunk.cursor)).toEqual([1, 2, 3])
  expect(fetch.mock.calls[2][0]).toMatch(/\/output\?since=1$/)
  expect(fetch.mock.calls[3][0]).toMatch(/\/output\/stream\?since=2$/)
  expect(fetch.mock.calls[4][0]).toMatch(/\/output\?since=3$/)
  expect(fetch.mock.calls[3][1].headers['Last-Event-ID']).toBe('2')
  for (const [url, init] of fetch.mock.calls.slice(2)) {
    expect(init.headers.Authorization).toBe('Bearer refreshed')
    expect(init.headers['X-Tenant-ID']).toBe('tenant-one')
    expect(url).not.toContain('Bearer')
    expect(url).not.toContain('access_token')
  }
  expect(ctx.callbacks.onError).toHaveBeenCalledWith(
    expect.stringContaining('recovering from replay'),
  )
  expect(ctx.callbacks.onError).toHaveBeenLastCalledWith(null)
  expect(ctx.callbacks.onConnection).toHaveBeenLastCalledWith(false)
  expect(ctx.callbacks.onDone).toHaveBeenCalledTimes(1)
  expect(ctx.callbacks.onDone).toHaveBeenCalledWith('completed')
})