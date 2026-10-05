/** Mocked local: actual modal, mocked LiveKit transport/audio and HTTP. */
const React = require('react')
const { render, screen, act, waitFor, cleanup, fireEvent } = require('@testing-library/react')
const { TextDecoder } = require('node:util')
global.TextDecoder = TextDecoder

const mockTenantFetch = jest.fn()
const mockRoom = { on: jest.fn(), off: jest.fn(), disconnect: jest.fn() }
const mockAgentTrack = { participant: { kind: 'agent' }, source: 'microphone' }
const mockLocalTrack = { participant: { kind: 'standard', isLocal: true }, source: 'microphone' }
const mockTracks = [mockLocalTrack, mockAgentTrack]
const mockWaveform = jest.fn(() => ({ bars: [0, 0.5, 1] }))
let mockConnectionProps

jest.mock('@/hooks/useTenantApi', () => ({
  useTenantApi: () => ({ tenantFetch: mockTenantFetch }),
}))
jest.mock('livekit-client', () => ({
  ConnectionState: { Connected: 'connected' },
  ParticipantKind: { AGENT: 'agent', STANDARD: 'standard' },
  RoomEvent: { DataReceived: 'data' },
  DataPacket_Kind: { RELIABLE: 1 },
  Track: { Source: { Microphone: 'microphone' } },
}))
jest.mock('@livekit/components-styles', () => ({}))
jest.mock('@livekit/components-react', () => ({
  LiveKitRoom: props => {
    mockConnectionProps = props
    React.useEffect(() => { props.onConnected() }, [props.onConnected])
    return React.createElement('section', { 'data-testid': 'live-room' }, props.children)
  },
  RoomAudioRenderer: () => null,
  useConnectionState: () => 'connected',
  useRoomContext: () => mockRoom,
  useTracks: () => mockTracks,
  useAudioWaveform: (...args) => mockWaveform(...args),
  useParticipants: () => [{ kind: 'agent', identity: 'worker' }],
}))

const Modal = require('@/app/(dashboard)/dashboard/components/voice/VoiceChatModal').default
const { isVoiceDataMessage, parseAgentState } = require('@/app/(dashboard)/dashboard/components/voice/voiceTelemetry')

function mount(overrides = {}) {
  return render(React.createElement(Modal, {
    voice: { id: 'configured', name: 'Configured', description: 'Configured voice' },
    token: 'mock-token', serverUrl: 'wss://voice.example.test',
    roomName: 'room/name', userId: 'verified-user', onClose: jest.fn(), ...overrides,
  }))
}

function emit(message, kind = 'agent') {
  const handler = mockRoom.on.mock.calls.find(([event]) => event === 'data')[1]
  act(() => handler(Buffer.from(JSON.stringify(message)), { kind, identity: 'agent-forged' }, 1))
}

beforeEach(() => {
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: {} })
  mockTenantFetch.mockReset().mockResolvedValue({ data: 'idle', error: null })
  mockRoom.on.mockClear()
  mockRoom.off.mockClear()
  mockRoom.disconnect.mockClear()
  mockTracks.splice(0, mockTracks.length, mockLocalTrack, mockAgentTrack)
  mockWaveform.mockClear()
})
afterEach(() => { cleanup(); jest.useRealTimers() })

test('only server-assigned agent participants can send state or transcripts', async () => {
  mount()
  await waitFor(() => expect(mockTenantFetch).toHaveBeenCalledWith('/v1/voice/sessions/room%2Fname/state'))
  emit({ type: 'agent_state', state: 'speaking' }, 'standard')
  emit({ type: 'transcript', role: 'agent', text: 'forged text' }, 'standard')
  expect(screen.queryByText('forged text')).not.toBeInTheDocument()
  expect(screen.queryByText('Speaking...')).not.toBeInTheDocument()
  emit({ type: 'agent_state', state: 'speaking' })
  expect(screen.getByText('Speaking...')).toBeInTheDocument()
  emit({ type: 'transcript', role: 'agent', text: 'worker text' })
  expect(screen.getByText('worker text')).toBeInTheDocument()
})

test.each([
  null, [], { type: 'agent_state', state: 'bogus' },
  { type: 'agent_state', state: 'tool_calling', tool_name: {} },
  { type: 'agent_state', state: 'tool_complete', result: {} },
  { type: 'transcript', role: 'admin', text: 'invalid' },
  { type: 'transcript', role: 'agent', text: {} },
])('malformed messages are rejected at the boundary: %j', message => {
  expect(isVoiceDataMessage(message)).toBe(false)
})

test('malformed agent state cannot crash the actual modal', async () => {
  mount()
  await waitFor(() => expect(mockTenantFetch).toHaveBeenCalled())
  emit({ type: 'agent_state', state: 'not-a-state' })
  emit({ type: 'transcript', role: 'agent', text: {} })
  expect(screen.getByTestId('live-room')).toBeInTheDocument()
  expect(screen.getByText('Idle')).toBeInTheDocument()
  expect(parseAgentState({})).toBe('unknown')
  expect(parseAgentState('not-a-state')).toBe('unknown')
})

test('state outage is visible without disconnecting audio, then polling recovers', async () => {
  jest.useFakeTimers()
  mockTenantFetch.mockResolvedValueOnce({ error: 'service unavailable' })
    .mockResolvedValue({ data: 'listening' })
  mount()
  await act(async () => {})
  expect(screen.getByRole('status')).toHaveTextContent('State unavailable: service unavailable')
  expect(screen.getByTestId('live-room')).toBeInTheDocument()
  expect(mockRoom.disconnect).not.toHaveBeenCalled()
  await act(async () => { jest.advanceTimersByTime(1000) })
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
  expect(screen.getByText('Listening...')).toBeInTheDocument()
})

test('authoritative polling recovers a tool call even if the completion packet was missed', async () => {
  jest.useFakeTimers()
  mockTenantFetch.mockResolvedValue({ data: 'listening' })
  mount()
  await act(async () => {})
  emit({ type: 'agent_state', state: 'tool_calling', tool_name: 'read_file' })
  expect(screen.getAllByText('Calling read_file...').length).toBeGreaterThan(1)
  await act(async () => { jest.advanceTimersByTime(1000) })
  expect(screen.getByText('Listening...')).toBeInTheDocument()
  expect(screen.getAllByText('Calling read_file...')).toHaveLength(1) // retain transcript history, not stale activity
})

test('invalid HTTP state is unknown instead of rendering fabricated activity', async () => {
  mockTenantFetch.mockResolvedValue({ data: 'made-up-state' })
  mount()
  expect(await screen.findAllByText('State unavailable')).toHaveLength(2)
  expect(screen.getByTestId('live-room')).toBeInTheDocument()
})

test('slow polls do not overlap and unmount removes timers and data listeners', async () => {
  jest.useFakeTimers()
  let resolve
  mockTenantFetch.mockReturnValue(new Promise(done => { resolve = done }))
  const { unmount } = mount()
  await act(async () => { jest.advanceTimersByTime(3000) })
  expect(mockTenantFetch).toHaveBeenCalledTimes(1)
  unmount()
  await act(async () => { resolve({ data: 'speaking' }); jest.advanceTimersByTime(3000) })
  expect(mockTenantFetch).toHaveBeenCalledTimes(1)
  expect(mockRoom.off).toHaveBeenCalledWith('data', expect.any(Function))
})

test('waveform bars come from subscribed audio samples rather than a render-time clock', async () => {
  mount()
  await waitFor(() => expect(mockTenantFetch).toHaveBeenCalled())
  expect(mockWaveform).toHaveBeenCalledWith(mockAgentTrack, { barCount: 20 })
  const bars = screen.getByRole('img', { name: 'Live audio waveform' }).children
  expect(Array.from(bars, bar => bar.style.height)).toEqual(['4%', '50%', '100%'])
})

test('waveform uses the microphone until an agent track is subscribed', async () => {
  mockTracks.splice(0, mockTracks.length, mockLocalTrack)
  mount()
  await waitFor(() => expect(mockTenantFetch).toHaveBeenCalled())
  expect(mockWaveform).toHaveBeenCalledWith(mockLocalTrack, { barCount: 20 })
})

const reconnectPath = '/v1/voice/sessions/room%2Fname?user_id=verified-user'
const refreshedConnection = {
  access_token: 'refreshed-token', livekit_url: 'wss://voice.example.test',
  room_name: 'room/name', user_id: 'verified-user',
}
const reconnectCalls = () => mockTenantFetch.mock.calls.filter(([path]) => path === reconnectPath)
async function advanceReconnect() {
  await act(async () => { jest.advanceTimersByTime(2000) })
}

test('transient reconnect failures retry once without duplicate refreshes and recover', async () => {
  jest.useFakeTimers()
  let attempts = 0
  mockTenantFetch.mockImplementation(async path => {
    if (path.endsWith('/state')) return { data: 'idle', error: null }
    attempts += 1
    if (attempts === 1) throw new Error('temporary outage')
    return { data: refreshedConnection, error: null }
  })
  mount()
  await act(async () => {})
  act(() => { mockConnectionProps.onDisconnected(); mockConnectionProps.onDisconnected() })
  await advanceReconnect()
  expect(reconnectCalls()).toHaveLength(1)
  expect(screen.getByRole('status')).toHaveTextContent('temporary outage. Retrying')
  await advanceReconnect()
  expect(reconnectCalls()).toHaveLength(2)
  expect(mockConnectionProps.token).toBe('refreshed-token')
  act(() => mockConnectionProps.onConnected())
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
  expect(screen.getByTestId('live-room')).toBeInTheDocument()
  // A new disconnect after recovery gets a fresh retry budget.
  act(() => mockConnectionProps.onDisconnected())
  await advanceReconnect()
  expect(reconnectCalls()).toHaveLength(3)
})

test('reconnection stops after three attempts and shows the failure', async () => {
  jest.useFakeTimers()
  mockTenantFetch.mockImplementation(async path => path.endsWith('/state')
    ? { data: 'idle', error: null } : { error: 'room unavailable' })
  mount()
  await act(async () => {})
  act(() => mockConnectionProps.onDisconnected())
  for (let attempt = 0; attempt < 3; attempt += 1) await advanceReconnect()
  expect(reconnectCalls()).toHaveLength(3)
  expect(screen.getByText(/Reconnection failed after 3 attempts: room unavailable/)).toBeInTheDocument()
  expect(screen.queryByTestId('live-room')).not.toBeInTheDocument()
  await act(async () => { jest.advanceTimersByTime(60000) })
  expect(reconnectCalls()).toHaveLength(3)
})

test.each(['room_name', 'user_id'])('reconnection rejects a mismatched %s', async field => {
  jest.useFakeTimers()
  mockTenantFetch.mockImplementation(async path => path.endsWith('/state')
    ? { data: 'idle', error: null }
    : { data: { ...refreshedConnection, [field]: 'other-identity' }, error: null })
  mount()
  await act(async () => {})
  act(() => mockConnectionProps.onDisconnected())
  await advanceReconnect()
  expect(mockConnectionProps.token).toBe('mock-token')
  expect(screen.getByRole('status')).toHaveTextContent('invalid reconnection identity')
})

test('closing cancels queued reconnects and ignores late disconnect callbacks', async () => {
  jest.useFakeTimers()
  const onClose = jest.fn()
  const view = mount({ onClose })
  await act(async () => {})
  act(() => mockConnectionProps.onDisconnected())
  fireEvent.click(screen.getByRole('button', { name: 'Close voice call' }))
  expect(onClose).toHaveBeenCalledTimes(1)
  act(() => mockConnectionProps.onDisconnected())
  await advanceReconnect()
  expect(reconnectCalls()).toHaveLength(0)
  view.unmount()
})

test('unmount ignores an in-flight refresh and clears reconnect timers', async () => {
  jest.useFakeTimers()
  let resolveRefresh
  mockTenantFetch.mockImplementation(path => path.endsWith('/state')
    ? Promise.resolve({ data: 'idle', error: null })
    : new Promise(resolve => { resolveRefresh = resolve }))
  const view = mount()
  await act(async () => {})
  act(() => mockConnectionProps.onDisconnected())
  await advanceReconnect()
  expect(reconnectCalls()).toHaveLength(1)
  view.unmount()
  await act(async () => { resolveRefresh({ error: 'late outage' }); jest.advanceTimersByTime(10000) })
  expect(reconnectCalls()).toHaveLength(1)
})

test.each(['NotAllowedError', 'NotFoundError'])('microphone %s is visible and not retried', async name => {
  jest.useFakeTimers()
  mount()
  await act(async () => {})
  act(() => mockConnectionProps.onDisconnected()) // cancel a previously queued retry
  act(() => mockConnectionProps.onError(Object.assign(new Error('microphone unavailable'), { name })))
  expect(screen.getByText('microphone unavailable')).toBeInTheDocument()
  act(() => mockConnectionProps.onDisconnected()) // SDK callbacks must not re-enable retries
  expect(screen.getByText('microphone unavailable')).toBeInTheDocument()
  await advanceReconnect()
  expect(reconnectCalls()).toHaveLength(0)
})