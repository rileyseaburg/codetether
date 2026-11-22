/** Mocked local: real assistant controls, mocked LiveKit media and transport. */
const React = require('react')
const { render, screen, fireEvent, waitFor } = require('@testing-library/react')
const mockMicrophone = jest.fn()
const mockDisconnect = jest.fn()
const mockWaveform = jest.fn()
let mockConnection
let mockEnabled
let mockAgentTrack
const mockMicrophoneTrack = { trackSid: 'microphone-track' }
const mockParticipant = { setMicrophoneEnabled: mockMicrophone }
jest.mock('livekit-client', () => ({
  ConnectionState: { Connected: 'connected' },
  Track: { Source: { Microphone: 'microphone' } },
}))
jest.mock('@livekit/components-react', () => ({
  useRoomContext: () => ({ disconnect: mockDisconnect }),
  useConnectionState: () => mockConnection,
  useVoiceAssistant: () => ({ state: 'listening', audioTrack: mockAgentTrack }),
  useLocalParticipant: () => ({
    localParticipant: mockParticipant,
    microphoneTrack: mockMicrophoneTrack, isMicrophoneEnabled: mockEnabled,
  }),
  useAudioWaveform: (...args) => mockWaveform(...args),
}))
const VoiceAssistantUI = require('@/app/(dashboard)/dashboard/components/voice/VoiceAssistantUI').default
const renderAssistant = (onClose = jest.fn()) => render(React.createElement(VoiceAssistantUI, {
  voice: { id: 'voice', name: 'Voice', description: 'Configured voice' }, onClose,
}))
beforeEach(() => {
  mockConnection = 'connected'
  mockEnabled = true
  mockAgentTrack = 'agent-track'
  mockMicrophone.mockReset().mockResolvedValue(undefined)
  mockDisconnect.mockReset().mockResolvedValue(undefined)
  mockWaveform.mockReset().mockReturnValue({ bars: [0, 0.5, 1] })
})

test('renders actual connection, agent state and audio samples', () => {
  renderAssistant()
  expect(screen.getByRole('status')).toHaveTextContent('Connected to LiveKit')
  expect(screen.getByText('Listening...')).toBeInTheDocument()
  expect(mockWaveform).toHaveBeenCalledWith('agent-track', { barCount: 20 })
  const waveform = screen.getByRole('img', { name: 'Live audio waveform' })
  expect([...waveform.firstChild.children].map(bar => bar.style.height)).toEqual(['4%', '50%', '100%'])
})

test('cannot pretend to be connected or toggle media while disconnected', () => {
  mockConnection = 'disconnected'
  renderAssistant()
  expect(screen.getByRole('status')).toHaveTextContent('LiveKit: disconnected')
  expect(screen.getByText('State unavailable')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Mute microphone' })).toBeDisabled()
})

test('uses the local microphone reference before agent audio is published', () => {
  mockAgentTrack = undefined
  renderAssistant()
  expect(mockWaveform).toHaveBeenCalledWith({
    participant: mockParticipant,
    publication: mockMicrophoneTrack,
    source: 'microphone',
  }, { barCount: 20 })
})

test.each([true, false])('mute controls update LiveKit, not simulated local state: %s', async enabled => {
  mockEnabled = enabled
  renderAssistant()
  const button = screen.getByRole('button', { name: enabled ? 'Mute microphone' : 'Unmute microphone' })
  expect(button).toHaveAttribute('aria-pressed', String(!enabled))
  fireEvent.click(button)
  await waitFor(() => expect(mockMicrophone).toHaveBeenCalledWith(!enabled))
})

test('microphone errors are visible and do not falsely flip mute state', async () => {
  mockMicrophone.mockRejectedValue(new Error('Microphone denied'))
  renderAssistant()
  fireEvent.click(screen.getByRole('button', { name: 'Mute microphone' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Microphone denied')
  expect(screen.getByRole('button', { name: 'Mute microphone' })).toHaveAttribute('aria-pressed', 'false')
})

test('ending a call disconnects the real room before invoking cleanup', async () => {
  const onClose = jest.fn()
  renderAssistant(onClose)
  fireEvent.click(screen.getByRole('button', { name: 'End voice call' }))
  await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1))
  expect(mockDisconnect).toHaveBeenCalledTimes(1)
  expect(mockDisconnect.mock.invocationCallOrder[0]).toBeLessThan(onClose.mock.invocationCallOrder[0])
})

test('disconnect failure stays visible rather than falsely closing', async () => {
  const onClose = jest.fn()
  mockDisconnect.mockRejectedValue(new Error('Disconnect failed'))
  renderAssistant(onClose)
  fireEvent.click(screen.getByRole('button', { name: 'End voice call' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Disconnect failed')
  expect(onClose).not.toHaveBeenCalled()
})