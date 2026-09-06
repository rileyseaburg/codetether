const React = require('react')
jest.mock('react-markdown', () => ({
  __esModule: true,
  default: ({ children }) => React.createElement('div', null, children),
}))
jest.mock('remark-gfm', () => ({ __esModule: true, default: () => {} }))
jest.mock('remark-breaks', () => ({ __esModule: true, default: () => {} }))
const {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
  act,
  within,
} = require('@testing-library/react')
const userEvent = require('@testing-library/user-event').default
jest.mock('next-auth/react', () => ({ useSession: jest.fn() }))
jest.mock('@/app/(dashboard)/dashboard/sessions/hooks/useWorkspaces', () => ({
  useWorkspaces: () => ({ workspaces: [{ id: 'work', name: 'Workspace' }] }),
}))
jest.mock('@/hooks/useTenantApi', () => ({
  useTenantApi: () => ({ apiUrl: 'https://api.example.invalid' }),
}))
jest.mock('@/lib/api', () => ({
  listAllTasksV1AgentTasksGet: jest.fn(),
  getTaskOutputV1AgentTasksTaskIdOutputGet: jest.fn(),
}))
const { useSession } = require('next-auth/react')
const api = require('@/lib/api')
const Tasks = require('@/app/(dashboard)/dashboard/tasks/page').default
const { readTaskQueue } = require('@/lib/task-queue-response')
const task = {
  id: 'task-1',
  title: 'Example task',
  agent_type: 'build',
  status: 'completed',
  created_at: '2026-09-01T00:00:00Z',
}
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  jest.clearAllMocks()
  localStorage.clear()
  window.matchMedia = jest.fn(() => ({
    matches: false,
    addEventListener() {},
    removeEventListener() {},
  }))
  useSession.mockReturnValue({
    status: 'authenticated',
    data: { accessToken: 'sso-fixture' },
  })
  api.listAllTasksV1AgentTasksGet.mockResolvedValue({ data: [] })
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ task_id: 'created-1', status: 'pending' }),
  })
})
afterEach(() => {
  cleanup()
  jest.useRealTimers()
})

async function openForm() {
  render(React.createElement(Tasks))
  const trigger = screen.getByRole('button', { name: 'New Task' })
  trigger.focus()
  fireEvent.click(trigger)
  const dialog = await screen.findByRole('dialog', { name: 'Create New Task' })
  return { trigger, dialog: dialog.querySelector('form') }
}
function fillForm() {
  fireEvent.change(screen.getByLabelText('Title'), {
    target: { value: ' New task ' },
  })
  fireEvent.change(screen.getByLabelText('Description'), {
    target: { value: ' Task instructions ' },
  })
}

test('initial pending data is loading, not an empty queue', async () => {
  let resolve
  api.listAllTasksV1AgentTasksGet.mockReturnValue(
    new Promise((done) => {
      resolve = done
    }),
  )
  render(React.createElement(Tasks))
  expect(screen.getByText('Loading tasks…')).toHaveAttribute('role', 'status')
  expect(screen.queryByText(/No tasks/)).not.toBeInTheDocument()
  await act(async () => resolve({ data: [] }))
  expect(screen.getByText(/No tasks yet/)).toBeVisible()
})

test.each([
  { error: { detail: 'Queue offline' } },
  { data: {} },
  { data: null },
])('unavailable response never appears empty: %j', async (response) => {
  api.listAllTasksV1AgentTasksGet
    .mockResolvedValueOnce(response)
    .mockResolvedValueOnce({ data: [task] })
  render(React.createElement(Tasks))
  expect(await screen.findByRole('alert')).toBeVisible()
  expect(screen.queryByText(/No tasks yet/)).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Retry loading tasks' }))
  expect(
    await screen.findByRole('button', { name: /Example task/ }),
  ).toBeVisible()
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
})

test('a thrown fetch failure has retry feedback', async () => {
  api.listAllTasksV1AgentTasksGet.mockRejectedValueOnce(
    new Error('Connection lost'),
  )
  render(React.createElement(Tasks))
  expect(await screen.findByRole('alert')).toHaveTextContent('Connection lost')
  expect(
    screen.getByRole('button', { name: 'Retry loading tasks' }),
  ).toBeEnabled()
})

test('background refresh failure preserves rows and warns they are stale', async () => {
  jest.useFakeTimers()
  api.listAllTasksV1AgentTasksGet
    .mockResolvedValueOnce({ data: [task] })
    .mockResolvedValue({ error: { detail: 'Offline' } })
  render(React.createElement(Tasks))
  await act(async () => {})
  fireEvent.click(screen.getByRole('button', { name: /Example task/ }))
  await act(async () => jest.advanceTimersByTime(5000))
  expect(screen.getByRole('alert')).toHaveTextContent('Previously loaded tasks')
  expect(screen.getByRole('button', { name: /Example task/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  expect(screen.queryByText(/No tasks/)).not.toBeInTheDocument()
})

test('polling does not overlap a slow request; removed tasks clear selection', async () => {
  jest.useFakeTimers()
  let resolve
  api.listAllTasksV1AgentTasksGet
    .mockResolvedValueOnce({ data: [task] })
    .mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done
        }),
    )
  render(React.createElement(Tasks))
  await act(async () => {})
  fireEvent.click(screen.getByRole('button', { name: /Example task/ }))
  await act(async () => jest.advanceTimersByTime(10000))
  expect(api.listAllTasksV1AgentTasksGet).toHaveBeenCalledTimes(2)
  await act(async () => resolve({ data: [] }))
  expect(
    screen.queryByRole('button', { name: /Example task/ }),
  ).not.toBeInTheDocument()
  expect(screen.getByText('Choose a task from the queue')).toBeVisible()
})

test('filters have names, pressed state, and a clear-filter recovery', async () => {
  api.listAllTasksV1AgentTasksGet.mockResolvedValue({ data: [task] })
  render(React.createElement(Tasks))
  await screen.findByRole('button', { name: /Example task/ })
  expect(
    screen.getByRole('combobox', { name: 'Filter tasks by workspace' }),
  ).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Failed', exact: true }))
  expect(
    screen.getByRole('button', { name: 'Failed', exact: true }),
  ).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByText('No tasks match these filters.')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
  expect(screen.getByRole('button', { name: /Example task/ })).toBeVisible()
})

test('keyboard task selection remains native and mobile selection focuses details', async () => {
  window.matchMedia.mockReturnValue({ matches: true })
  api.listAllTasksV1AgentTasksGet.mockResolvedValue({ data: [task] })
  render(React.createElement(Tasks))
  const row = await screen.findByRole('button', { name: /Example task/ })
  row.focus()
  await userEvent.keyboard('{Enter}')
  expect(row).toHaveAttribute('aria-pressed', 'true')
  await waitFor(() =>
    expect(screen.getByRole('heading', { name: 'Example task' })).toHaveFocus(),
  )
})

test('Tasks has one primary action and prioritizes results over collapsed metadata', async () => {
  api.listAllTasksV1AgentTasksGet.mockResolvedValue({
    data: [
      {
        ...task,
        result: 'Readable task result',
        prompt: 'Original task instructions',
        worker_id: 'worker-fixture',
      },
    ],
  })
  render(React.createElement(Tasks))
  expect(
    screen.getByRole('heading', { level: 1, name: 'Tasks' }),
  ).toBeInTheDocument()
  expect(
    screen.getAllByRole('button', { name: 'New Task', exact: true }),
  ).toHaveLength(1)
  fireEvent.click(await screen.findByRole('button', { name: /Example task/ }))
  expect(screen.getByText('Readable task result')).toBeInTheDocument()
  const metadata = screen.getByText('Task information').closest('details')
  expect(metadata).not.toHaveAttribute('open')
  expect(screen.getByText('Task brief').closest('details')).not.toHaveAttribute(
    'open',
  )
  expect(
    screen
      .getByRole('heading', { name: 'Result' })
      .compareDocumentPosition(metadata) & Node.DOCUMENT_POSITION_FOLLOWING,
  ).toBeTruthy()
})

test('returning to the mobile queue restores focus to the selected task', async () => {
  window.matchMedia.mockReturnValue({ matches: true })
  api.listAllTasksV1AgentTasksGet.mockResolvedValue({ data: [task] })
  render(React.createElement(Tasks))
  const row = await screen.findByRole('button', { name: /Example task/ })
  fireEvent.click(row)
  await waitFor(() =>
    expect(screen.getByRole('heading', { name: 'Example task' })).toHaveFocus(),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Back to task queue' }))
  await waitFor(() => expect(row).toHaveFocus())
})

test('dialog labels inputs, focuses Title, and restores focus on Escape', async () => {
  const { trigger } = await openForm()
  await waitFor(() => expect(screen.getByLabelText('Title')).toHaveFocus())
  expect(screen.getByLabelText('Description')).toBeRequired()
  expect(
    screen.getByRole('button', { name: 'Close create task' }),
  ).toBeVisible()
  await userEvent.keyboard('{Escape}')
  await waitFor(() =>
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
  )
  expect(trigger).toHaveFocus()
})

test('whitespace validation focuses the invalid field without dispatching', async () => {
  const { dialog } = await openForm()
  fireEvent.change(screen.getByLabelText('Title'), { target: { value: ' ' } })
  fireEvent.submit(dialog)
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Title and description are required',
  )
  expect(screen.getByLabelText('Title')).toHaveFocus()
  expect(fetch).not.toHaveBeenCalled()
})

test('successful dispatch uses password credentials and announces its ID despite refresh failure', async () => {
  useSession.mockReturnValue({ status: 'unauthenticated', data: null })
  localStorage.setItem('a2a_token', 'password-fixture')
  api.listAllTasksV1AgentTasksGet
    .mockResolvedValueOnce({ data: [] })
    .mockResolvedValue({ error: { detail: 'Refresh offline' } })
  const { dialog } = await openForm()
  fillForm()
  fireEvent.submit(dialog)
  await waitFor(() =>
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
  )
  expect(fetch).toHaveBeenCalledTimes(1)
  const [, options] = fetch.mock.calls[0]
  expect(options.headers.Authorization).toBe('Bearer password-fixture')
  expect(JSON.parse(options.body)).toMatchObject({
    title: 'New task',
    description: 'Task instructions',
  })
  expect(screen.getByText(/Task created-1 was submitted/)).toHaveAttribute(
    'role',
    'status',
  )
  expect(screen.getByRole('alert')).toHaveTextContent('Refresh offline')
})

test('pending dispatch rejects duplicate submits and dismissal', async () => {
  let resolve
  fetch.mockReturnValue(
    new Promise((done) => {
      resolve = done
    }),
  )
  const { dialog } = await openForm()
  fillForm()
  fireEvent.submit(dialog)
  fireEvent.submit(dialog)
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled()
  await userEvent.keyboard('{Escape}')
  expect(screen.getByRole('dialog')).toBeVisible()
  await act(async () =>
    resolve({ ok: true, json: async () => ({ task_id: 'created-1' }) }),
  )
})

test('server error warns that dispatch may have committed and preserves the draft', async () => {
  fetch.mockResolvedValue({
    ok: false,
    status: 500,
    json: async () => {
      throw new Error('non-JSON response')
    },
  })
  const { dialog } = await openForm()
  fillForm()
  fireEvent.submit(dialog)
  const alert = await within(dialog).findByRole('alert')
  expect(alert).toHaveTextContent('The task may already exist')
  expect(alert).toHaveTextContent('Check the queue before submitting again')
  expect(screen.getByLabelText('Title')).toHaveValue(' New task ')
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(screen.queryByText(/was submitted/)).not.toBeInTheDocument()
})

test('dispatch validation errors stay renderable and preserve the draft', async () => {
  fetch.mockResolvedValue({
    ok: false,
    status: 422,
    json: async () => ({ detail: [{ msg: 'Invalid agent type' }] }),
  })
  const { dialog } = await openForm()
  fillForm()
  fireEvent.submit(dialog)
  expect(await within(dialog).findByRole('alert')).toHaveTextContent(
    'Invalid agent type',
  )
  expect(screen.getByLabelText('Title')).toHaveValue(' New task ')
  expect(screen.getByRole('button', { name: 'Dispatch Task' })).toBeEnabled()
})

test('unconfirmed dispatch response does not clear the form or claim success', async () => {
  fetch.mockResolvedValue({ ok: true, json: async () => ({}) })
  const { dialog } = await openForm()
  fillForm()
  fireEvent.submit(dialog)
  expect(await within(dialog).findByRole('alert')).toHaveTextContent(
    'Check the queue before submitting again',
  )
  expect(screen.queryByText(/was submitted/)).not.toBeInTheDocument()
})

test('missing credentials show sign-in instead of an empty list or endless spinner', async () => {
  useSession.mockReturnValue({ status: 'unauthenticated', data: null })
  render(React.createElement(Tasks))
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Sign in to load your tasks',
  )
  expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute(
    'href',
    '/login?callbackUrl=%2Fdashboard%2Ftasks',
  )
  expect(screen.getByRole('button', { name: 'New Task' })).toBeDisabled()
  expect(api.listAllTasksV1AgentTasksGet).not.toHaveBeenCalled()
  expect(screen.queryByText('Loading tasks…')).not.toBeInTheDocument()
})

test('a slow initial load times out with a retry action', async () => {
  jest.useFakeTimers()
  api.listAllTasksV1AgentTasksGet.mockImplementation(
    ({ signal }) =>
      new Promise((resolve, reject) => {
        signal.addEventListener('abort', () => reject(new Error('Aborted')))
      }),
  )
  render(React.createElement(Tasks))
  await act(async () => jest.advanceTimersByTime(20000))
  expect(screen.getByRole('alert')).toHaveTextContent('Loading tasks timed out')
  expect(
    screen.getByRole('button', { name: 'Retry loading tasks' }),
  ).toBeEnabled()
})

test('dispatch timeout releases controls without erasing the draft or claiming success', async () => {
  const { dialog } = await openForm()
  fillForm()
  jest.useFakeTimers()
  fetch.mockImplementation(
    (url, { signal }) =>
      new Promise((resolve, reject) => {
        signal.addEventListener('abort', () => reject(new Error('Aborted')))
      }),
  )
  fireEvent.submit(dialog)
  await act(async () => jest.advanceTimersByTime(20000))
  expect(within(dialog).getByRole('alert')).toHaveTextContent(
    'Check the queue before submitting again',
  )
  expect(screen.getByLabelText('Title')).toHaveValue(' New task ')
  expect(screen.getByRole('button', { name: 'Cancel' })).toBeEnabled()
  expect(screen.queryByText(/was submitted/)).not.toBeInTheDocument()
})

test.each(['workspace_id', 'codebase_id'])(
  'workspace filters support %s',
  async (field) => {
    api.listAllTasksV1AgentTasksGet.mockResolvedValue({
      data: [{ ...task, [field]: 'work' }],
    })
    render(React.createElement(Tasks))
    await screen.findByRole('button', { name: /Example task/ })
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Filter tasks by workspace' }),
      {
        target: { value: 'work' },
      },
    )
    expect(screen.getByRole('button', { name: /Example task/ })).toBeVisible()
    expect(
      screen.queryByText('No tasks match these filters.'),
    ).not.toBeInTheDocument()
  },
)

test('queue parser accepts supported envelopes and rejects unsafe fields', () => {
  expect(readTaskQueue({ tasks: [task] })).toEqual([task])
  expect(readTaskQueue([{ ...task, agent_type: undefined }])).toHaveLength(1)
  expect(() => readTaskQueue([{ ...task, id: '' }])).toThrow(
    'unreadable response',
  )
  expect(() => readTaskQueue({ tasks: [{ ...task, title: {} }] })).toThrow(
    'unreadable response',
  )
})