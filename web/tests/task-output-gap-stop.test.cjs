/** @jest-environment node */
const { watchTaskOutput } = require('../src/lib/task-output-stream')
const { context, output, replay, stream, event, gap } = require('./task-output-fixtures.cjs')
let ctx
beforeEach(() => { ctx = context() })
afterEach(() => ctx.close())

test('unreplayable gaps leave a disconnected error without retry or false completion', async () => {
  fetch.mockResolvedValueOnce(replay([output(1)]))
    .mockResolvedValueOnce(stream(
      event('lag', gap()),
      event('output', output(2), '2'),
      event('done', { status: 'completed' }),
    ))
  await watchTaskOutput(ctx.options)
  expect(fetch).toHaveBeenCalledTimes(2)
  expect(ctx.callbacks.onOutput.mock.calls.map(([chunk]) => chunk.cursor)).toEqual([1])
  expect(ctx.callbacks.onDone).not.toHaveBeenCalled()
  expect(ctx.callbacks.onConnection).toHaveBeenLastCalledWith(false)
  expect(ctx.callbacks.onError).toHaveBeenLastCalledWith(
    expect.stringContaining('Task output is incomplete'),
  )
  expect(ctx.callbacks.onError).toHaveBeenLastCalledWith(
    expect.stringContaining('replay is unavailable'),
  )
})