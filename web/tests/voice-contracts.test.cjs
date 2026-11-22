/** Mocked-local dashboard voice contracts; no microphone or LiveKit network. */
const React = require('react')
const { render, screen, fireEvent, waitFor, act, cleanup } = require('@testing-library/react')

const mockTenantFetch = jest.fn()
jest.mock('@/hooks/useTenantApi', () => ({
  useTenantApi: () => ({ tenantFetch: mockTenantFetch }),
}))
jest.mock('@/app/(dashboard)/dashboard/components/voice/VoiceChatModal', () => ({
  __esModule: true,
  default: ({ userId, onClose }) => React.createElement('div', {},
    React.createElement('p', {}, `Participant: ${userId}`),
    React.createElement('button', { onClick: onClose }, 'End voice session')),
}))

const VoiceAgentButton = require('@/app/(dashboard)/dashboard/components/voice/VoiceAgentButton').default
const VoiceChatButton = require('@/app/(dashboard)/dashboard/components/voice/VoiceChatButton').default
const VoiceSelector = require('@/app/(dashboard)/dashboard/components/voice/VoiceSelector').default
const voice = { id: 'configured-voice', name: 'Configured voice', description: 'Tenant voice' }
const connection = {
  room_name: 'voice/room', access_token: 'mock-token', livekit_url: 'wss://voice.example.test',
  user_id: 'verified-user', voice: voice.id, mode: 'chat', expires_at: '2030-01-01T00:00:00Z',
}

beforeEach(() => {
  mockTenantFetch.mockReset()
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: {} })
})

function renderAgent() {
  return render(React.createElement(VoiceAgentButton, {
    codebaseId: 'workspace-a', workers: [{ worker_id: 'worker-a', is_sse_connected: true }],
  }))
}

describe('deployment readiness', () => {
  beforeEach(() => {
    jest.useFakeTimers()
    jest.spyOn(window, 'confirm').mockReturnValue(true)
  })
  afterEach(() => {
    cleanup()
    jest.useRealTimers()
    jest.restoreAllMocks()
  })
  const startDeployment = async () => {
    render(React.createElement(VoiceAgentButton, { codebaseId: 'workspace-a', workers: [] }))
    await act(async () => fireEvent.click(screen.getByRole('button', { name: /talk to agent/i })))
    const payload = JSON.parse(mockTenantFetch.mock.calls[0][1].body)
    expect(payload.env_vars.CODETETHER_WORKER_NAME).toBe(payload.subagent_id)
    return payload.subagent_id
  }
  const poll = async () => act(async () => jest.advanceTimersByTimeAsync(2000))

  test('waits for its own worker in the live SSE endpoint, not unrelated or absent workers', async () => {
    let requestedName
    let polls = 0
    const deployed = jest.fn()
    mockTenantFetch.mockImplementation(async (path, options) => {
      if (path === '/v1/k8s/subagent') {
        requestedName = JSON.parse(options.body).subagent_id
        return { data: { action: 'created' } }
      }
      if (path === '/v1/worker/connected') {
        polls += 1
        return { data: { workers: polls === 2 ? [] : [{
          worker_id: 'registered-worker-id',
          agent_name: polls === 1 ? 'unrelated-worker' : requestedName,
        }] } }
      }
      if (path === '/v1/voice/voices') return { data: { voices: [voice] } }
      return { data: connection }
    })
    render(React.createElement(VoiceAgentButton, { workers: [], onWorkerDeployed: deployed }))
    await act(async () => fireEvent.click(screen.getByRole('button', { name: /talk to agent/i })))
    expect(JSON.parse(mockTenantFetch.mock.calls[0][1].body).env_vars.CODETETHER_WORKER_NAME).toBe(requestedName)
    await poll()
    await poll()
    expect(deployed).not.toHaveBeenCalled()
    expect(mockTenantFetch.mock.calls.some(([path]) => path === '/v1/voice/sessions')).toBe(false)
    await poll()
    expect(deployed).toHaveBeenCalledTimes(1)
    expect(screen.getByText('Participant: verified-user')).toBeInTheDocument()
  })

  test('readiness errors are visible and cannot start a session', async () => {
    mockTenantFetch.mockResolvedValueOnce({ data: { action: 'created' } })
      .mockResolvedValueOnce({ error: 'Worker service unavailable' })
    await startDeployment()
    await poll()
    expect(screen.getByText('Could not check worker readiness: Worker service unavailable')).toBeInTheDocument()
    expect(mockTenantFetch).toHaveBeenCalledTimes(2)
  })

  test('times out rather than launching on an unrelated worker', async () => {
    mockTenantFetch.mockResolvedValueOnce({ data: { action: 'created' } })
      .mockResolvedValue({ data: { workers: [{ worker_id: 'other-id', agent_name: 'unrelated-worker' }] } })
    await startDeployment()
    for (let i = 0; i < 30; i++) await poll()
    expect(screen.getByText('Worker deployed but did not come online within 60s')).toBeInTheDocument()
    expect(mockTenantFetch).toHaveBeenCalledTimes(31)
  })
})

test('agent launches with the configured catalog and server identity, then deletes the owned room', async () => {
  mockTenantFetch.mockResolvedValueOnce({ data: { voices: [voice] } })
    .mockResolvedValueOnce({ data: connection }).mockResolvedValueOnce({ data: { success: true } })
  renderAgent()
  fireEvent.click(screen.getByRole('button', { name: /talk to agent/i }))
  expect(await screen.findByText('Participant: verified-user')).toBeInTheDocument()
  expect(mockTenantFetch.mock.calls[0][0]).toBe('/v1/voice/voices')
  expect(JSON.parse(mockTenantFetch.mock.calls[1][1].body)).toEqual({
    voice: voice.id, mode: 'chat', workspace_id: 'workspace-a',
  })
  fireEvent.click(screen.getByRole('button', { name: 'End voice session' }))
  await waitFor(() => expect(mockTenantFetch).toHaveBeenLastCalledWith(
    '/v1/voice/sessions/voice%2Froom', { method: 'DELETE' },
  ))
})

test.each([
  { data: { voices: [] } }, { error: 'Voice catalog unavailable' },
])('agent does not launch with an unavailable catalog: %j', async (result) => {
  mockTenantFetch.mockResolvedValueOnce(result)
  renderAgent()
  fireEvent.click(screen.getByRole('button', { name: /talk to agent/i }))
  expect(await screen.findByText(/voice catalog unavailable|no voice is configured/i)).toBeInTheDocument()
  expect(mockTenantFetch).toHaveBeenCalledTimes(1)
})

test.each(['access_token', 'livekit_url', 'room_name', 'user_id'])(
  'agent rejects a connection missing %s instead of opening the modal', async (field) => {
    mockTenantFetch.mockResolvedValueOnce({ data: { voices: [voice] } })
      .mockResolvedValueOnce({ data: { ...connection, [field]: '' } })
    renderAgent()
    fireEvent.click(screen.getByRole('button', { name: /talk to agent/i }))
    expect(await screen.findByText('Voice server returned an incomplete connection')).toBeInTheDocument()
    expect(screen.queryByText('Participant: verified-user')).not.toBeInTheDocument()
  },
)

test('room cleanup failure is visible to the agent launcher', async () => {
  mockTenantFetch.mockResolvedValueOnce({ data: { voices: [voice] } })
    .mockResolvedValueOnce({ data: connection }).mockResolvedValueOnce({ error: 'Service unavailable' })
  renderAgent()
  fireEvent.click(screen.getByRole('button', { name: /talk to agent/i }))
  fireEvent.click(await screen.findByRole('button', { name: 'End voice session' }))
  expect(await screen.findByText('Could not end voice session: Service unavailable')).toBeInTheDocument()
})

test('session chat sends execution-target fields and ignores browser participant IDs', async () => {
  mockTenantFetch.mockResolvedValueOnce({ data: { voices: [voice] } })
    .mockResolvedValueOnce({ data: connection }).mockResolvedValueOnce({ data: { success: true } })
  localStorage.setItem('voice_user_id', 'forged-browser-user')
  render(React.createElement(VoiceChatButton, {
    codebaseId: 'workspace-a', sessionId: 'session-a', mode: 'chat',
  }))
  fireEvent.click(screen.getByRole('button', { name: /voice chat/i }))
  fireEvent.click(await screen.findByRole('button', { name: /configured voice/i }))
  expect(await screen.findByText('Participant: verified-user')).toBeInTheDocument()
  expect(JSON.parse(mockTenantFetch.mock.calls[1][1].body)).toEqual({
    voice: voice.id, workspace_id: 'workspace-a', session_id: 'session-a',
    mode: 'chat', playback_style: 'verbatim',
  })
  fireEvent.click(screen.getByRole('button', { name: 'End voice session' }))
  await waitFor(() => expect(mockTenantFetch).toHaveBeenLastCalledWith(
    '/v1/voice/sessions/voice%2Froom', { method: 'DELETE' },
  ))
  localStorage.removeItem('voice_user_id')
})

test('session chat reports a thrown cleanup failure', async () => {
  mockTenantFetch.mockResolvedValueOnce({ data: { voices: [voice] } })
    .mockResolvedValueOnce({ data: connection }).mockRejectedValueOnce(new Error('Network failure'))
  render(React.createElement(VoiceChatButton, { mode: 'chat' }))
  fireEvent.click(screen.getByRole('button', { name: /voice chat/i }))
  fireEvent.click(await screen.findByRole('button', { name: /configured voice/i }))
  fireEvent.click(await screen.findByRole('button', { name: 'End voice session' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not end voice session: Network failure')
})

test('voice selector distinguishes service failure from an empty catalog', async () => {
  mockTenantFetch.mockResolvedValueOnce({ error: 'Catalog access denied' })
  render(React.createElement(VoiceSelector, { selected: null, onSelect: jest.fn(), onClose: jest.fn() }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Catalog access denied')
  expect(screen.getByRole('button', { name: 'Close voice selector' })).toBeInTheDocument()
})