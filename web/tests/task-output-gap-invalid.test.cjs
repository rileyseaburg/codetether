/** @jest-environment node */
const { watchTaskOutput } = require('../src/lib/task-output-stream')
const { context, replay, stream, event, gap } = require('./task-output-fixtures.cjs')
let ctx
beforeEach(() => { ctx = context() })
afterEach(() => ctx.close())

test.each([
  null, [], 'not an object', {},
  { ...gap(), task_id: 'another-task' },
  { ...gap(), error: 'another-error' },
  { ...gap(), replay_available: 'true' },
  { ...gap(), skipped_bus_events: 0 },
  { ...gap(), skipped_bus_events: -1 },
  { ...gap(), skipped_bus_events: 1.5 },
  { ...gap(), skipped_bus_events: '2' },
  { ...gap(), skipped_bus_events: Number.MAX_SAFE_INTEGER + 1 },
  { ...gap(), skipped_bus_events: undefined },
])('rejects malformed gap events without retry (%#)', async (payload) => {
  fetch.mockResolvedValueOnce(replay())
    .mockResolvedValueOnce(stream(event('lag', payload)))
  await watchTaskOutput(ctx.options)
  expect(fetch).toHaveBeenCalledTimes(2)
  expect(ctx.callbacks.onOutput).not.toHaveBeenCalled()
  expect(ctx.callbacks.onDone).not.toHaveBeenCalled()
  expect(ctx.callbacks.onError).toHaveBeenLastCalledWith(
    'Task output stream has an invalid gap event.',
  )
})