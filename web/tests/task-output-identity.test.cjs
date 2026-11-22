/** @jest-environment node */
const { watchTaskOutput } = require('../src/lib/task-output-stream')
const { context, taskId, output, replay, event, stream } = require('./task-output-fixtures.cjs')
let ctx, controller
beforeEach(() => {
  ctx = context()
  controller = new AbortController()
  ctx.options.signal = controller.signal
})
afterEach(() => { controller.abort(); ctx.close() })

test.each(['another-task', null, 7, false, {}])(
  'rejects replay chunks naming another or invalid task (%#)', async (task_id) => {
    ctx.callbacks.onOutput.mockImplementation(() => controller.abort())
    fetch.mockResolvedValueOnce(replay([{ ...output(1), task_id }]))
    await watchTaskOutput(ctx.options)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(ctx.callbacks.onOutput).not.toHaveBeenCalled()
    expect(ctx.callbacks.onDone).not.toHaveBeenCalled()
    expect(ctx.callbacks.onError).toHaveBeenLastCalledWith(
      'Task output belongs to a different task.',
    )
  },
)

test.each(['output', 'done'].flatMap((name) =>
  ['another-task', null, 7, false, {}].map((task_id) => [name, task_id]),
))('rejects %s events naming another or invalid task (%#)', async (name, task_id) => {
  ctx.callbacks.onOutput.mockImplementation(() => controller.abort())
  const payload = name === 'output' ? { ...output(1), task_id } : { status: 'completed', task_id }
  fetch.mockResolvedValueOnce(replay()).mockResolvedValueOnce(stream(event(name, payload, '1')))
  await watchTaskOutput(ctx.options)
  expect(fetch).toHaveBeenCalledTimes(2)
  expect(ctx.callbacks.onOutput).not.toHaveBeenCalled()
  expect(ctx.callbacks.onDone).not.toHaveBeenCalled()
  expect(ctx.callbacks.onError).toHaveBeenLastCalledWith(
    'Task output belongs to a different task.',
  )
})

test('accepts explicit matching task identity in replay, output and completion', async () => {
  fetch.mockResolvedValueOnce(replay([{ ...output(1), task_id: taskId }]))
    .mockResolvedValueOnce(stream(
      event('output', { ...output(2), task_id: taskId }, '2'),
      event('done', { status: 'completed', task_id: taskId, next_cursor: 2 }),
    ))
    .mockResolvedValueOnce(replay([{ ...output(2), task_id: taskId }]))
  await watchTaskOutput(ctx.options)
  expect(ctx.callbacks.onOutput.mock.calls.map(([chunk]) => chunk.cursor)).toEqual([1, 2])
  expect(ctx.callbacks.onDone).toHaveBeenCalledWith('completed')
  expect(ctx.callbacks.onError).toHaveBeenLastCalledWith(null)
})