const React = require('react')
const { render, screen, fireEvent, cleanup } = require('@testing-library/react')
jest.mock('@/components/ModelSelector', () => ({ ModelSelector: props => React.createElement('select', { 'aria-label': props.label, value: props.selectedModel, disabled: props.disabled, onChange: event => props.onSelectedModelChange(event.target.value) }, React.createElement('option', { value: 'one' }, 'One'), React.createElement('option', { value: 'two' }, 'Two')) }))
jest.mock('@/app/(dashboard)/dashboard/sessions/components/SessionActions', () => ({ SessionActions: props => React.createElement('div', null, React.createElement('button', { onClick: props.onResume }, 'Resume'), React.createElement('button', { onClick: props.onRefresh }, 'Refresh')) }))
jest.mock('@/app/(dashboard)/dashboard/components/voice/VoiceChatButton', () => ({ __esModule: true, default: () => React.createElement('button', null, 'Voice') }))
const { ChatHeader } = require('@/app/(dashboard)/dashboard/sessions/components/ChatHeader')
const { SessionList } = require('@/app/(dashboard)/dashboard/sessions/components/SessionList')
const { ChatInput } = require('@/app/(dashboard)/dashboard/sessions/components/ChatInput')
afterEach(cleanup)
const session = { id: 's', title: 'Plan the release', time: { created: 1000, updated: 2000 } }
function header(overrides = {}) {
  const props = { selectedSession: session, selectedMode: 'code', selectedModel: 'one', suggestedModels: ['one', 'two'], selectedWorkspace: 'w', selectedWorkspaceName: 'Website', streamConnected: false, streamStatus: 'idle', loading: false, chatItemsCount: 3, onModeChange: jest.fn(), onModelChange: jest.fn(), onResume: jest.fn(), onRefresh: jest.fn(), onToggleRLMPane: jest.fn(), onBackToSessions: jest.fn(), showBackButton: true, ...overrides }
  render(React.createElement(ChatHeader, props))
  return props
}

test('conversation chrome hides model, voice, RLM and actions until requested', () => {
  const props = header()
  expect(screen.getByRole('heading', { name: session.title })).toBeVisible()
  expect(screen.getByRole('combobox', { name: 'Model' })).not.toBeVisible()
  expect(screen.getByRole('button', { name: 'Voice' })).not.toBeVisible()
  expect(screen.getByRole('button', { name: 'Resume' })).not.toBeVisible()
  fireEvent.click(screen.getByText('Conversation settings & actions'))
  const model = screen.getByRole('combobox', { name: 'Model' })
  expect(model).toBeVisible()
  fireEvent.change(model, { target: { value: 'two' } })
  expect(props.onModelChange).toHaveBeenCalledWith('two')
  fireEvent.click(screen.getByRole('button', { name: 'Resume' }))
  fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
  fireEvent.click(screen.getByRole('button', { name: 'Toggle RLM execution view' }))
  expect(props.onResume).toHaveBeenCalledTimes(1)
  expect(props.onRefresh).toHaveBeenCalledTimes(1)
  expect(props.onToggleRLMPane).toHaveBeenCalledTimes(1)
})

test('mobile back action remains explicit and invalid dates do not crash', () => {
  const props = header({ selectedSession: { ...session, time: { updated: NaN } } })
  fireEvent.click(screen.getByRole('button', { name: 'Back to sessions' }))
  expect(props.onBackToSessions).toHaveBeenCalledTimes(1)
})

test('workspace is always visible; search and sort wait for a workspace', () => {
  const changed = jest.fn()
  const props = { workspaces: [{ id: 'w', name: 'Website' }], sessions: [], selectedWorkspace: '', selectedSession: null, onWorkspaceChange: changed, onSessionSelect: jest.fn() }
  const { rerender } = render(React.createElement(SessionList, props))
  const workspace = screen.getByRole('combobox', { name: 'Select workspace' })
  expect(workspace).toBeVisible()
  expect(screen.queryByRole('searchbox')).not.toBeInTheDocument()
  fireEvent.change(workspace, { target: { value: 'w' } })
  expect(changed).toHaveBeenCalledWith('w')
  rerender(React.createElement(SessionList, { ...props, selectedWorkspace: 'w', sessions: [session] }))
  expect(screen.getByRole('searchbox', { name: 'Search sessions' })).toBeVisible()
  expect(screen.getByRole('combobox', { name: 'Sort' })).not.toBeVisible()
  fireEvent.click(screen.getByText('Sort & list details'))
  expect(screen.getByRole('combobox', { name: 'Sort' })).toBeVisible()
})

test('composer is absent without selection and has one clear send action', () => {
  const props = { draftMessage: 'Hello', loading: false, actionStatus: null, hasSession: false, onDraftChange: jest.fn(), onSend: jest.fn() }
  const { rerender } = render(React.createElement(ChatInput, props))
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  rerender(React.createElement(ChatInput, { ...props, hasSession: true }))
  expect(screen.getByRole('textbox')).toHaveAttribute('rows', '2')
  fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter', isComposing: true })
  expect(props.onSend).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Send message' }))
  expect(props.onSend).toHaveBeenCalledTimes(1)
})