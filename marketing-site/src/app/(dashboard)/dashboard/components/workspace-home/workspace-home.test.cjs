const React = require('react')
const { render, screen, fireEvent, waitFor, cleanup, within } = require('@testing-library/react')
const fs = require('node:fs')
const path = require('node:path')
const fixtures = Array.from({ length: 1611 }, (_, index) => ({
  id: `workspace-${index}`, name: index === 1600 ? 'CodeTether' : `Project ${String(index).padStart(4, '0')}`,
  path: index === 1600 ? '/projects/A2A-Server-MCP' : `/projects/project-${index}`, status: index === 1600 ? 'idle' : 'offline',
  runtime: index % 2 ? 'vm' : 'container', worker_id: index === 1600 ? 'worker-connected' : 'worker-stale',
}))
const mockStore = { selectedModel: 'openai/gpt-fixture', selectedCodebase: 'workspace-1600', setSelectedCodebase: jest.fn(), setAgents: jest.fn(), setLoadingAgents: jest.fn() }
const mockTenantFetch = jest.fn(async url => ({ data: url.includes('/worker/connected') ? { workers: [{ worker_id: 'worker-connected', agent_name: 'Local worker' }] } : [] }))
jest.mock('next-auth/react', () => ({ useSession: () => ({ data: { accessToken: 'fixture' } }), signOut: jest.fn() }))
jest.mock('@/hooks/useTenantApi', () => ({ useTenantApi: () => ({ apiUrl: 'https://api.example.invalid', isAuthenticated: true, tenantFetch: mockTenantFetch }) }))
jest.mock('@/app/(dashboard)/dashboard/ralph/store', () => ({ useRalphStore: () => mockStore }))
jest.mock('@/components/TenantStatusBanner', () => () => React.createElement('div', null, 'Fixture tenant status'))
jest.mock('@/app/(dashboard)/dashboard/components/voice/VoiceAgentButton', () => ({ __esModule: true, default: () => React.createElement('button', null, 'Voice agent') }))
jest.mock('@/components/ModelSelector', () => ({ ModelSelector: () => React.createElement('label', null, 'Model', React.createElement('select', null, React.createElement('option', null, 'Fixture model'))) }))
jest.mock('@/components/WorkerSelector', () => ({ WorkerSelector: () => React.createElement('select', { 'aria-label': 'Worker' }, React.createElement('option', null, 'Automatic worker')) }))
jest.mock('@/lib/api', () => ({
  listWorkspacesV1AgentWorkspacesListGet: jest.fn(), listAllTasksV1AgentTasksGet: jest.fn(),
  listWorkersV1AgentWorkersGet: jest.fn(), listModelsV1AgentModelsGet: jest.fn(),
  triggerAgentV1AgentWorkspacesWorkspaceIdTriggerPost: jest.fn(), registerWorkspaceV1AgentWorkspacesPost: jest.fn(),
  unregisterWorkspaceV1AgentWorkspacesWorkspaceIdDelete: jest.fn(), hasApiAuthToken: () => true,
}))
const api = require('@/lib/api')
const { WorkspaceBrowser } = require('./WorkspaceBrowser')
const Dashboard = require('../../page').default
beforeEach(() => {
  global.fetch = jest.fn().mockRejectedValue(new Error('Network disabled for local preview'))
  localStorage.clear()
  api.listWorkspacesV1AgentWorkspacesListGet.mockResolvedValue({ data: fixtures })
  api.listAllTasksV1AgentTasksGet.mockResolvedValue({ data: [] })
  api.listWorkersV1AgentWorkersGet.mockResolvedValue({ data: [{ worker_id: 'worker-connected', name: 'Local worker', status: 'active', global_workspace_id: 'workspace-1600' }] })
  api.listModelsV1AgentModelsGet.mockResolvedValue({ data: { models: [] } })
  global.EventSource = class { addEventListener() {} removeEventListener() {} close() {} }
})
afterEach(cleanup)
const props = { workspaces: fixtures, selectedId: 'workspace-1600', onSelect: jest.fn(), onRegister: jest.fn(), statusLabel: value => value, connectedWorkerIds: ['worker-connected'] }

test('1611 records start as eight rows, with connected workers first', () => {
  render(React.createElement(WorkspaceBrowser, props))
  const list = screen.getByRole('list', { name: 'Available workspaces' })
  expect(within(list).getAllByRole('button')).toHaveLength(8)
  expect(within(list).getAllByRole('button')[0]).toHaveTextContent('CodeTether')
  expect(screen.getByText('1611 of 1611')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /Show more workspaces/ }))
  expect(within(list).getAllByRole('button')).toHaveLength(16)
})

test('search reaches records outside the initial page and preserves selection', () => {
  render(React.createElement(WorkspaceBrowser, props))
  fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'workspace-1610' } })
  expect(within(screen.getByRole('list')).getAllByRole('button')).toHaveLength(1)
  expect(screen.getByText('1 of 1611')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Continue with CodeTether/ })).toHaveAttribute('href', '#workspace-launcher')
  fireEvent.click(screen.getByRole('button', { name: 'Show selected workspace' }))
  expect(within(screen.getByRole('list')).getAllByRole('button')[0]).toHaveAttribute('aria-pressed', 'true')
})

test('connected-only and runtime filters never remove access to stale records', () => {
  render(React.createElement(WorkspaceBrowser, props))
  fireEvent.click(screen.getByRole('checkbox', { name: 'Connected workers only' }))
  expect(screen.getByText('1 of 1611')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Filter workspaces by runtime'), { target: { value: 'vm' } })
  expect(screen.getByText('No workspaces match these filters.')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }))
  expect(screen.getByText('1611 of 1611')).toBeInTheDocument()
})

test('loading and errors do not masquerade as an empty workspace list', () => {
  const view = render(React.createElement(WorkspaceBrowser, { ...props, workspaces: [], loading: true }))
  expect(screen.getByText('Loading your workspaces…')).toBeInTheDocument()
  expect(screen.queryByText('Start with your code')).not.toBeInTheDocument()
  view.rerender(React.createElement(WorkspaceBrowser, { ...props, workspaces: [], error: 'Offline', onRetry: jest.fn() }))
  expect(screen.getByRole('alert')).toHaveTextContent('Offline')
  expect(screen.queryByText('Start with your code')).not.toBeInTheDocument()
})

test('landing page has a single main workflow and retains advanced capabilities', async () => {
  render(React.createElement(Dashboard))
  await screen.findByText('1611 of 1611')
  expect(screen.getByRole('heading', { level: 1, name: 'Workspaces' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Start agent', exact: true })).toBeDisabled()
  expect(screen.getByLabelText('What would you like to do?')).toBeInTheDocument()
  window.matchMedia = jest.fn(() => ({ matches: true }))
  HTMLElement.prototype.scrollIntoView = jest.fn()
  fireEvent.click(within(screen.getByRole('list', { name: 'Available workspaces' })).getAllByRole('button')[0])
  expect(screen.getByLabelText('What would you like to do?')).toHaveFocus()
  expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled()
  expect(screen.getByText('Workspace setup and selected workspace details').closest('details')).not.toHaveAttribute('open')
  expect(screen.getByText('Execution details, workers and more tools').closest('details')).not.toHaveAttribute('open')
  fireEvent.click(screen.getByRole('button', { name: 'Agent, worker & model settings' }))
  expect(screen.getByRole('combobox', { name: 'Model' })).toBeInTheDocument()
  expect(screen.getByRole('combobox', { name: 'Worker' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Add workspace', exact: true }))
  expect(screen.getByRole('heading', { name: 'Register Workspace', exact: true })).toBeInTheDocument()
})

test('preview renders the real landing component with labelled sample records', async () => {
  render(React.createElement(Dashboard))
  await screen.findByText('1611 of 1611')
  const evidenceDir = path.resolve(__dirname, '../../../../../../../artifacts/ui-redesign/workspace-home-fixture')
  fs.mkdirSync(evidenceDir, { recursive: true })
  fs.writeFileSync(path.join(evidenceDir, 'preview-body.html'), document.body.innerHTML)
})