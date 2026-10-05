/** Runtime checks for telemetry crossing the LiveKit/HTTP boundary. */
const agentStates = ['idle', 'listening', 'thinking', 'speaking', 'tool_calling', 'tool_complete', 'error', 'unknown'] as const;
export type AgentState = typeof agentStates[number];

export type VoiceDataMessage = {
  type: 'agent_state';
  state: AgentState;
  tool_name?: string;
  result?: string;
} | {
  type: 'transcript';
  role: 'user' | 'agent';
  text: string;
};

export function isAgentState(value: unknown): value is AgentState {
  return typeof value === 'string' && agentStates.some(state => state === value);
}

export function isVoiceDataMessage(value: unknown): value is VoiceDataMessage {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const message = value as Record<string, unknown>;
  if (message.type === 'agent_state') {
    return isAgentState(message.state) &&
      (message.tool_name === undefined || typeof message.tool_name === 'string') &&
      (message.result === undefined || typeof message.result === 'string');
  }
  return message.type === 'transcript' &&
    (message.role === 'user' || message.role === 'agent') &&
    typeof message.text === 'string';
}

export function parseAgentState(value: unknown): AgentState {
  return isAgentState(value) ? value : 'unknown';
}