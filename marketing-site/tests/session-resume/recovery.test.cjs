// Mocked-local contracts; no provider, worker, or deployment is contacted.
const { renderHook, act, cleanup } = require('@testing-library/react')
jest.mock('next-auth/react', () => ({ useSession: () => ({ data: null }) }))
jest.mock('@/lib/auth-token', () => ({
  ...jest.requireActual('@/lib/auth-token'),
  getApiAuth: jest.fn(),
}))
const { getApiAuth } = require('@/lib/auth-token')
const { useSessionResume } = require('@/app/(dashboard)/dashboard/sessions/hooks/useSessionResume')

const session = { id: 'session/one' }
const response = (data, status = 200) => ({
  ok: status >= 200 && status < 300, status, json: async () => data,
})
const deferred = () => {
  let resolve
  const promise = new Promise(yes => { resolve = yes })
  return { promise, resolve }
}
const props = () => ({
  selectedWorkspace: 'workspace/one', selectedMode: 'build', selectedModel: 'fixture-model',
  onSessionUpdate: jest.fn(), loadSessions: jest.fn(async () => {}),
  loadSessionMessages: jest.fn(async () => {}),
})
const mount = (options = props()) => ({
  ...renderHook(value => useSessionResume(value), { initialProps: options }), options,
})
const start = async hook => {
  let pending
  await act(async () => { pending = hook.result.current.resumeSession(session, 'hello') })
  return { pending }
}
const observe = async (milliseconds = 2000) => {
  await act(async () => { await jest.advanceTimersByTimeAsync(milliseconds) })
}

describe('session recovery (mocked local)', () => {
  const originalFetch = global.fetch
  beforeEach(() => {
    jest.useFakeTimers()
    getApiAuth.mockReturnValue({ token: 'fixture-token', tenantId: 'fixture-tenant' })
    global.fetch = jest.fn()
  })
  afterEach(() => {
    cleanup()
    jest.useRealTimers()
    jest.clearAllMocks()
    global.fetch = originalFetch
  })

  test('authenticates the POST, encodes identities, and refreshes the returned session', async () => {
    fetch.mockResolvedValue(response({ status: 'completed', active_session_id: 'recovered' }))
    const hook = mount()
    await act(async () => { await hook.result.current.resumeSession(session, 'hello') })
    const [url, request] = fetch.mock.calls[0]
    expect(url).toContain('/workspaces/workspace%2Fone/sessions/session%2Fone/resume')
    expect(request.method).toBe('POST')
    expect(request.headers).toEqual({
      Authorization: 'Bearer fixture-token', 'X-Tenant-ID': 'fixture-tenant',
      'Content-Type': 'application/json',
    })
    expect(JSON.parse(request.body)).toEqual({ message: 'hello', mode: 'build', model: 'fixture-model' })
    expect(hook.options.onSessionUpdate).toHaveBeenCalledWith('recovered')
    expect(hook.options.loadSessionMessages).toHaveBeenCalledWith('recovered', true)
    expect(hook.result.current.actionStatus).toBe('Response received!')
    expect(hook.result.current.loading).toBe(false)
  })

  test('requires authentication before submission', async () => {
    getApiAuth.mockReturnValue({ token: null, tenantId: null })
    const hook = mount()
    await act(async () => { await hook.result.current.resumeSession(session, 'hello') })
    expect(fetch).not.toHaveBeenCalled()
    expect(hook.result.current.actionStatus).toContain('Sign in')
    expect(hook.options.loadSessions).not.toHaveBeenCalled()
  })

  test('never replays a POST after losing its response', async () => {
    fetch.mockRejectedValue(new TypeError('Failed to fetch'))
    const hook = mount()
    await act(async () => { await hook.result.current.resumeSession(session, 'hello') })
    await observe(180000)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(hook.result.current.actionStatus).toContain('execution outcome is unknown')
    expect(hook.result.current.actionStatus).toContain('Check session history before resending')
    expect(hook.options.loadSessions).not.toHaveBeenCalled()
  })

  test('submission timeout leaves outcome unknown without resubmitting', async () => {
    fetch.mockImplementation((url, { signal }) => new Promise((resolve, reject) => {
      signal.addEventListener('abort', () => reject(new Error('aborted')), { once: true })
    }))
    const hook = mount()
    const { pending } = await start(hook)
    await observe(30000)
    await act(async () => { await pending })
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(hook.result.current.actionStatus).toContain('timed out after 30s')
    expect(hook.result.current.actionStatus).toContain('execution outcome is unknown')
    expect(hook.result.current.loading).toBe(false)
  })

  test.each([
    { status: 'failed', error: 'worker failed' },
    { status: 'completed', result: { error: 'worker failed' } },
    { status: 'completed', result: JSON.stringify({ success: false, error: 'worker failed' }) },
  ])('does not mistake HTTP-200 execution errors for success: %j', async payload => {
    fetch.mockResolvedValue(response(payload))
    const hook = mount()
    await act(async () => { await hook.result.current.resumeSession(session, 'hello') })
    expect(hook.result.current.taskStatus).toBe('failed')
    expect(hook.result.current.actionStatus).toContain('worker failed')
    expect(hook.options.loadSessions).not.toHaveBeenCalled()
  })

  test.each([{ status: 'pending' }, {}, { status: 123 }, { task_id: '   ' }])(
    'does not refresh unconfirmed execution: %j', async payload => {
      fetch.mockResolvedValue(response(payload))
      const hook = mount()
      await act(async () => { await hook.result.current.resumeSession(session, 'hello') })
      expect(hook.result.current.actionStatus).not.toBe('Response received!')
      expect(hook.options.loadSessions).not.toHaveBeenCalled()
    },
  )

  test('retries only observation after network loss and authenticates each GET', async () => {
    fetch.mockResolvedValueOnce(response({ task_id: 'task/one', active_session_id: 'recovered' }))
      .mockRejectedValueOnce(new TypeError('offline'))
      .mockResolvedValueOnce(response({ status: 'completed' }))
    const hook = mount()
    const { pending } = await start(hook)
    await observe()
    expect(hook.result.current.actionStatus).toContain('retrying observation, not the prompt')
    await observe()
    await act(async () => { await pending })
    expect(fetch.mock.calls.filter(([, request]) => request.method === 'POST')).toHaveLength(1)
    for (const [url, request] of fetch.mock.calls.slice(1)) {
      expect(url).toContain('/tasks/task%2Fone')
      expect(request.headers).toEqual({ Authorization: 'Bearer fixture-token', 'X-Tenant-ID': 'fixture-tenant' })
    }
    expect(hook.result.current.taskStatus).toBe('completed')
    expect(hook.options.onSessionUpdate).toHaveBeenCalledWith('recovered')
  })

  test('a completed task carrying an error is displayed as failed', async () => {
    fetch.mockResolvedValueOnce(response({ task_id: 'task-one' }))
      .mockResolvedValueOnce(response({ status: 'completed', result: { error: 'tool failed' } }))
    const hook = mount()
    const { pending } = await start(hook)
    await observe()
    await act(async () => { await pending })
    expect(hook.result.current.taskStatus).toBe('failed')
    expect(hook.result.current.actionStatus).toContain('tool failed')
    expect(hook.options.loadSessions).not.toHaveBeenCalled()
  })

  test.each(['cancelled', 'interrupted'])('surfaces terminal %s without refresh', async status => {
    fetch.mockResolvedValueOnce(response({ task_id: 'task-one' }))
      .mockResolvedValueOnce(response({ status }))
    const hook = mount()
    const { pending } = await start(hook)
    await observe()
    await act(async () => { await pending })
    expect(hook.result.current.taskStatus).toBe(status)
    expect(hook.options.loadSessions).not.toHaveBeenCalled()
  })

  test.each([401, 403, 404])('HTTP %s stops observing without claiming execution stopped', async status => {
    fetch.mockResolvedValueOnce(response({ task_id: 'task-one' }))
      .mockResolvedValueOnce(response({}, status))
    const hook = mount()
    const { pending } = await start(hook)
    await observe()
    await act(async () => { await pending })
    await observe(6000)
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(hook.result.current.actionStatus).toContain(`HTTP ${status}`)
    expect(hook.result.current.actionStatus).toContain('may still be running')
    expect(hook.options.loadSessions).not.toHaveBeenCalled()
  })

  test('stopping observation does not cancel the server task', async () => {
    fetch.mockResolvedValueOnce(response({ task_id: 'task-one' }))
    const hook = mount()
    const { pending } = await start(hook)
    act(() => { hook.result.current.cancelPolling() })
    await act(async () => { await pending })
    await observe(6000)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(hook.result.current.actionStatus).toBe('Stopped watching; the task may still be running.')
    expect(hook.result.current.loading).toBe(false)
  })

  test('blocks overlapping submissions', async () => {
    const old = deferred()
    fetch.mockReturnValue(old.promise)
    const hook = mount()
    const { pending } = await start(hook)
    await act(async () => { await hook.result.current.resumeSession(session, 'duplicate') })
    expect(fetch).toHaveBeenCalledTimes(1)
    await act(async () => { old.resolve(response({ status: 'ready' })); await pending })
  })

  test.each(['workspace', 'token', 'tenant'])('ignores late responses after changing %s', async change => {
    const old = deferred()
    fetch.mockReturnValueOnce(old.promise)
    const hook = mount()
    const { pending } = await start(hook)
    const signal = fetch.mock.calls[0][1].signal
    if (change !== 'workspace') getApiAuth.mockReturnValue({
      token: change === 'token' ? 'new-token' : 'fixture-token',
      tenantId: change === 'tenant' ? 'new-tenant' : 'fixture-tenant',
    })
    hook.rerender({ ...hook.options, selectedWorkspace: change === 'workspace' ? 'new-workspace' : hook.options.selectedWorkspace })
    expect(signal.aborted).toBe(true)
    fetch.mockResolvedValueOnce(response({ status: 'completed', active_session_id: 'new-session' }))
    await act(async () => { await hook.result.current.resumeSession({ id: 'new-session' }, 'new prompt') })
    await act(async () => { old.resolve(response({ status: 'failed', error: 'obsolete failure' })); await pending })
    expect(hook.result.current.actionStatus).toBe('Response received!')
    expect(hook.options.onSessionUpdate).toHaveBeenCalledTimes(1)
    expect(hook.options.onSessionUpdate).toHaveBeenCalledWith('new-session')
  })

  test.each(['token', 'tenant', 'logout'])('auth notification invalidates observation after %s without a manual render', async change => {
    const old = deferred()
    fetch.mockReturnValueOnce(old.promise)
    const hook = mount()
    const { pending } = await start(hook)
    const signal = fetch.mock.calls[0][1].signal
    act(() => {
      getApiAuth.mockReturnValue(change === 'logout' ? {} : {
        token: change === 'token' ? 'new-token' : 'fixture-token',
        tenantId: change === 'tenant' ? 'new-tenant' : 'fixture-tenant',
      })
      window.dispatchEvent(new Event('codetether-auth-change'))
    })
    expect(signal.aborted).toBe(true)
    await act(async () => {
      old.resolve(response({ status: 'completed', active_session_id: 'obsolete-session' }))
      await pending
    })
    expect(hook.options.loadSessions).not.toHaveBeenCalled()
    expect(hook.options.onSessionUpdate).not.toHaveBeenCalled()
    expect(hook.result.current.actionStatus).toBeNull()
  })

  test('does not select an obsolete session if workspace changes during refresh', async () => {
    const refreshing = deferred()
    const options = props()
    options.loadSessions.mockReturnValue(refreshing.promise)
    fetch.mockResolvedValue(response({ status: 'completed' }))
    const hook = mount(options)
    const { pending } = await start(hook)
    expect(options.loadSessions).toHaveBeenCalledTimes(1)
    hook.rerender({ ...options, selectedWorkspace: 'new-workspace' })
    await act(async () => { refreshing.resolve(); await pending })
    expect(options.onSessionUpdate).not.toHaveBeenCalled()
    expect(options.loadSessionMessages).not.toHaveBeenCalled()
  })

  test('distinguishes refresh failure from execution failure', async () => {
    fetch.mockResolvedValue(response({ status: 'completed' }))
    const options = props()
    options.loadSessions.mockRejectedValue(new Error('history unavailable'))
    const hook = mount(options)
    await act(async () => { await hook.result.current.resumeSession(session, 'hello') })
    expect(hook.result.current.actionStatus).toContain('Response received, but refresh failed')
    expect(hook.result.current.actionStatus).toContain('history unavailable')
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})