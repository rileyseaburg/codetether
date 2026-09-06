const React = require('react')
const {
  renderHook,
  act,
  render,
  screen,
  fireEvent,
  cleanup,
  waitFor,
} = require('@testing-library/react')
jest.mock('@/lib/api', () => ({
  listSessionsV1AgentWorkspacesWorkspaceIdSessionsGet: jest.fn(),
  getSessionMessagesByIdV1AgentWorkspacesWorkspaceIdSessionsSessionIdMessagesGet:
    jest.fn(),
  listWorkspacesV1AgentWorkspacesListGet: jest.fn(),
  hasApiAuthToken: jest.fn(() => false),
}))
jest.mock('next-auth/react', () => ({
  useSession: jest.fn(() => ({
    status: 'authenticated',
    data: { accessToken: 'fixture' },
  })),
}))
jest.mock(
  '@tanstack/react-virtual',
  () => ({
    useVirtualizer: () => ({
      getVirtualItems: () => [],
      getTotalSize: () => 0,
    }),
  }),
  { virtual: true },
)
jest.mock(
  '@/app/(dashboard)/dashboard/sessions/components/ChatMessage',
  () => ({ ChatMessage: () => null }),
)
const api = require('@/lib/api')
const {
  useSessions,
} = require('@/app/(dashboard)/dashboard/sessions/hooks/useSessions')
const {
  useWorkspaces,
} = require('@/app/(dashboard)/dashboard/sessions/hooks/useWorkspaces')
const {
  SessionList,
} = require('@/app/(dashboard)/dashboard/sessions/components/SessionList')
const {
  ChatMessages,
} = require('@/app/(dashboard)/dashboard/sessions/components/ChatMessages')
const list = api.listSessionsV1AgentWorkspacesWorkspaceIdSessionsGet
const messages =
  api.getSessionMessagesByIdV1AgentWorkspacesWorkspaceIdSessionsSessionIdMessagesGet
const session = {
  id: 's',
  title: 'Keyboard session',
  time: { created: 1700000000000 },
  directory: '/fixture',
}
const pageOfSessions = (items, hasMore = false) => ({
  data: { sessions: items, total: items.length, hasMore },
})
const pageOfMessages = (items, hasMore = false) => ({
  data: { messages: items, total: items.length, hasMore },
})
const deferred = () => {
  let resolve
  const promise = new Promise((r) => {
    resolve = r
  })
  return { promise, resolve }
}
beforeEach(() => {
  jest.clearAllMocks()
  localStorage.clear()
  Element.prototype.scrollTo = jest.fn()
  list.mockResolvedValue(pageOfSessions([]))
  messages.mockResolvedValue(pageOfMessages([]))
  api.listWorkspacesV1AgentWorkspacesListGet.mockResolvedValue({
    data: { workspaces: [] },
  })
  require('next-auth/react').useSession.mockReturnValue({
    status: 'authenticated',
    data: { accessToken: 'fixture' },
  })
})
afterEach(cleanup)

test('StrictMode cleanup does not poison the selected-session request cache', async () => {
  const { result } = renderHook(
    () => {
      const state = useSessions('w')
      React.useEffect(() => {
        void state.loadSessionMessages('s')
      }, [state.loadSessionMessages])
      return state
    },
    { reactStrictMode: true },
  )
  await waitFor(() => expect(result.current.loading).toBe(false))
  expect(messages).toHaveBeenCalledTimes(2)
  expect(result.current.error).toBeNull()
})

test('latest search wins over slower results', async () => {
  const old = deferred(),
    latest = deferred()
  list.mockReturnValueOnce(old.promise).mockReturnValueOnce(latest.promise)
  const { result } = renderHook(() => useSessions('w'))
  let a, b
  act(() => {
    a = result.current.loadSessions('w', 'old')
    b = result.current.loadSessions('w', 'new')
  })
  await act(async () => {
    latest.resolve(pageOfSessions([{ ...session, id: 'new' }]))
    await b
  })
  await act(async () => {
    old.resolve(pageOfSessions([{ ...session, id: 'old' }]))
    await a
  })
  expect(result.current.sessions.map((s) => s.id)).toEqual(['new'])
  expect(list.mock.calls[1][0].query.q).toBe('new')
})

test('stale list failure cannot clear a newer loading state', async () => {
  const old = deferred(),
    latest = deferred()
  list.mockReturnValueOnce(old.promise).mockReturnValueOnce(latest.promise)
  const { result } = renderHook(() => useSessions('w'))
  let a, b
  act(() => {
    a = result.current.loadSessions('w')
    b = result.current.loadSessions('w', 'new')
  })
  await act(async () => {
    old.resolve({ error: { detail: 'old failure' } })
    await a
  })
  expect(result.current.sessionsLoading).toBe(true)
  expect(result.current.sessionsError).toBeNull()
  await act(async () => {
    latest.resolve(pageOfSessions([]))
    await b
  })
})

test('clearing a workspace invalidates pending list and message responses', async () => {
  const pendingList = deferred(),
    pendingMessages = deferred()
  list.mockReturnValueOnce(pendingList.promise)
  messages.mockReturnValueOnce(pendingMessages.promise)
  const { result } = renderHook(() => useSessions('w'))
  let a, b
  act(() => {
    a = result.current.loadSessions('w')
    b = result.current.loadSessionMessages('s')
  })
  act(() => result.current.clearSessions())
  await act(async () => {
    pendingList.resolve(pageOfSessions([session], true))
    pendingMessages.resolve(pageOfMessages([{ id: 'stale' }], true))
    await Promise.all([a, b])
  })
  expect(result.current.sessions).toEqual([])
  expect(result.current.sessionMessages).toEqual([])
  expect(result.current.totalSessions).toBe(0)
  expect(result.current.hasMoreSessions).toBe(false)
  expect(result.current.loadingMoreSessions).toBe(false)
})

test('message loading does not change list loading', async () => {
  const pending = deferred()
  list.mockReturnValueOnce(pending.promise)
  const { result } = renderHook(() => useSessions('w'))
  let work
  act(() => {
    work = result.current.loadSessions('w')
  })
  await act(() => result.current.loadSessionMessages('s'))
  expect(result.current.loading).toBe(false)
  expect(result.current.sessionsLoading).toBe(true)
  await act(async () => {
    pending.resolve(pageOfSessions([]))
    await work
  })
})

test('newer forced requests for the same session win', async () => {
  const old = deferred(),
    latest = deferred()
  messages.mockReturnValueOnce(old.promise).mockReturnValueOnce(latest.promise)
  const { result } = renderHook(() => useSessions('w'))
  let a, b
  act(() => {
    a = result.current.loadSessionMessages('s')
    b = result.current.loadSessionMessages('s', true)
  })
  await act(async () => {
    latest.resolve(pageOfMessages([{ id: 'new' }]))
    await b
  })
  await act(async () => {
    old.resolve(pageOfMessages([{ id: 'old' }]))
    await a
  })
  expect(result.current.sessionMessages).toEqual([{ id: 'new' }])
  expect(result.current.loading).toBe(false)
})

test('message failure unlocks normal retry and clears old counts', async () => {
  messages.mockResolvedValueOnce({ error: { detail: 'offline' } })
  const { result } = renderHook(() => useSessions('w'))
  await act(() => result.current.loadSessionMessages('s'))
  expect(result.current.error).toMatch(/Failed to load messages/)
  expect(result.current.loading).toBe(false)
  expect(result.current.totalMessages).toBe(0)
  await act(() => result.current.loadSessionMessages('s'))
  expect(messages).toHaveBeenCalledTimes(2)
  expect(result.current.error).toBeNull()
})

test('older history expands the limit and replaces rather than duplicates the window', async () => {
  messages
    .mockResolvedValueOnce(pageOfMessages([{ id: 'new' }], true))
    .mockResolvedValueOnce(pageOfMessages([{ id: 'old' }, { id: 'new' }], true))
    .mockResolvedValueOnce(
      pageOfMessages([{ id: 'oldest' }, { id: 'old' }, { id: 'new' }]),
    )
  const { result } = renderHook(() => useSessions('w'))
  await act(() => result.current.loadSessionMessages('s'))
  await act(() => result.current.loadMoreMessages())
  await act(() => result.current.loadMoreMessages())
  expect(messages.mock.calls.map(([args]) => args.query.limit)).toEqual([
    20, 40, 60,
  ])
  expect(result.current.sessionMessages.map((m) => m.id)).toEqual([
    'oldest',
    'old',
    'new',
  ])
})

test('failed history extension preserves messages and retries the same limit', async () => {
  messages
    .mockResolvedValueOnce(pageOfMessages([{ id: 'new' }], true))
    .mockResolvedValueOnce({ error: {} })
  const { result } = renderHook(() => useSessions('w'))
  await act(() => result.current.loadSessionMessages('s'))
  await act(() => result.current.loadMoreMessages())
  expect(result.current.sessionMessages).toEqual([{ id: 'new' }])
  expect(result.current.error).toMatch(/older messages/)
  await act(() => result.current.loadMoreMessages())
  expect(messages.mock.calls[2][0].query.limit).toBe(40)
})

test('pending pagination cannot pollute the newly selected conversation', async () => {
  const old = deferred()
  messages
    .mockResolvedValueOnce(pageOfMessages([{ id: 'a' }], true))
    .mockReturnValueOnce(old.promise)
    .mockResolvedValueOnce(pageOfMessages([{ id: 'b' }]))
  const { result } = renderHook(() => useSessions('w'))
  await act(() => result.current.loadSessionMessages('a'))
  let pending
  act(() => {
    pending = result.current.loadMoreMessages()
  })
  await act(() => result.current.loadSessionMessages('b'))
  await act(async () => {
    old.resolve(pageOfMessages([{ id: 'old-a' }]))
    await pending
  })
  expect(result.current.sessionMessages).toEqual([{ id: 'b' }])
})

test('duplicate pagination calls are coalesced and session IDs are deduplicated', async () => {
  const next = deferred()
  list
    .mockResolvedValueOnce(pageOfSessions([session], true))
    .mockReturnValueOnce(next.promise)
  const { result } = renderHook(() => useSessions('w'))
  await act(() => result.current.loadSessions('w'))
  let pending
  act(() => {
    pending = result.current.loadMoreSessions('w')
    result.current.loadMoreSessions('w')
  })
  expect(list).toHaveBeenCalledTimes(2)
  await act(async () => {
    next.resolve(pageOfSessions([session, { ...session, id: 'next' }]))
    await pending
  })
  expect(result.current.sessions.map((s) => s.id)).toEqual(['s', 'next'])
})

test('workspace failure is visible and password-token users can retry', async () => {
  require('next-auth/react').useSession.mockReturnValue({
    status: 'unauthenticated',
    data: null,
  })
  localStorage.setItem('a2a_token', 'password-fixture')
  api.listWorkspacesV1AgentWorkspacesListGet.mockResolvedValueOnce({
    error: {},
  })
  const { result } = renderHook(useWorkspaces)
  await waitFor(() =>
    expect(result.current.error).toMatch(/Failed to load workspaces/),
  )
  await act(() => result.current.loadWorkspaces())
  expect(result.current.error).toBeNull()
  expect(
    api.listWorkspacesV1AgentWorkspacesListGet.mock.calls[1][0].headers
      .Authorization,
  ).toBe('Bearer password-fixture')
})

const listProps = {
  workspaces: [{ id: 'w', name: 'Workspace' }],
  sessions: [],
  selectedWorkspace: 'w',
  selectedSession: null,
  onWorkspaceChange: jest.fn(),
  onSessionSelect: jest.fn(),
}
test('session list distinguishes loading, error, and empty states with retry', () => {
  const retry = jest.fn()
  const { rerender } = render(
    React.createElement(SessionList, { ...listProps, loading: true }),
  )
  expect(screen.getByText('Loading sessions…')).toBeInTheDocument()
  expect(screen.queryByText('No sessions found')).toBeNull()
  rerender(
    React.createElement(SessionList, {
      ...listProps,
      error: 'Offline',
      onRetry: retry,
    }),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Retry sessions' }))
  expect(retry).toHaveBeenCalledTimes(1)
  expect(screen.queryByText('No sessions found')).toBeNull()
  rerender(React.createElement(SessionList, listProps))
  expect(screen.getByText('No sessions found')).toBeInTheDocument()
})

test('native session buttons expose selection and load-more without an observer', () => {
  const select = jest.fn(),
    more = jest.fn()
  render(
    React.createElement(SessionList, {
      ...listProps,
      sessions: [{ ...session, time: { created: NaN } }],
      selectedSession: session,
      onSessionSelect: select,
      hasMoreSessions: true,
      onLoadMoreSessions: more,
    }),
  )
  const button = screen.getByRole('button', { name: /Keyboard session/ })
  expect(button).toHaveAttribute('aria-pressed', 'true')
  fireEvent.click(button)
  fireEvent.click(screen.getByRole('button', { name: 'Load more sessions' }))
  expect(select).toHaveBeenCalledTimes(1)
  expect(more).toHaveBeenCalledTimes(1)
  expect(screen.queryByRole('listbox')).toBeNull()
})

test('message errors have an explicit retry action', () => {
  const retry = jest.fn()
  render(
    React.createElement(ChatMessages, {
      chatItems: [],
      selectedSession: session,
      loading: false,
      loadingMore: false,
      hasMore: false,
      totalMessages: 0,
      error: 'Offline',
      liveDraft: '',
      awaitingResponse: false,
      onLoadMore: jest.fn(),
      onRetry: retry,
    }),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Retry messages' }))
  expect(retry).toHaveBeenCalledTimes(1)
  expect(screen.queryByText('No messages yet.')).toBeNull()
})

test.each([
  [{ key: 'Enter', isComposing: true }, 0],
  [{ key: 'Enter', keyCode: 229 }, 0],
  [{ key: 'Enter', shiftKey: true }, 0],
  [{ key: 'Enter' }, 1],
])('preserves existing IME/Enter behavior: %j', (event, sends) => {
  const {
    ChatInput,
  } = require('@/app/(dashboard)/dashboard/sessions/components/ChatInput')
  const onSend = jest.fn()
  render(
    React.createElement(ChatInput, {
      draftMessage: 'Fixture',
      loading: false,
      actionStatus: null,
      hasSession: true,
      onDraftChange: jest.fn(),
      onSend,
    }),
  )
  fireEvent.keyDown(screen.getByRole('textbox'), event)
  expect(onSend).toHaveBeenCalledTimes(sends)
})

test('identical session IDs across workspaces do not share the loading cache', async () => {
  const old = deferred()
  messages
    .mockReturnValueOnce(old.promise)
    .mockResolvedValueOnce(pageOfMessages([{ id: 'workspace-b' }]))
  const { result, rerender } = renderHook(
    ({ workspace }) => useSessions(workspace),
    { initialProps: { workspace: 'a' } },
  )
  let pending
  act(() => {
    pending = result.current.loadSessionMessages('same-id')
  })
  rerender({ workspace: 'b' })
  await act(() => result.current.loadSessionMessages('same-id'))
  await act(async () => {
    old.resolve(pageOfMessages([{ id: 'workspace-a' }]))
    await pending
  })
  expect(result.current.sessionMessages).toEqual([{ id: 'workspace-b' }])
  expect(messages.mock.calls[1][0].path.workspace_id).toBe('b')
})

test('malformed message payload shows an error rather than an empty transcript', async () => {
  messages.mockResolvedValueOnce({ data: { messages: null } })
  const { result } = renderHook(() => useSessions('w'))
  await act(() => result.current.loadSessionMessages('s'))
  expect(result.current.error).toMatch(/Failed to load messages/)
  expect(result.current.loading).toBe(false)
})