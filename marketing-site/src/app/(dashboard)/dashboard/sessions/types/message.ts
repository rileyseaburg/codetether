import type { TokenUsage, ToolState } from './tokens'

export interface SessionPart {
    id?: string
    type: string
    text?: string
    tool?: string
    callID?: string
    state?: ToolState
    reason?: string
    cost?: number
    tokens?: TokenUsage
    hash?: string
    files?: string[]
    filename?: string
    url?: string
    mime?: string
    snapshot?: string
}

export interface SessionMessage {
    id?: string
    sessionID?: string
    info?: { role?: string; model?: string; content?: unknown; cost?: number; tokens?: TokenUsage; parts?: SessionPart[] }
    role?: string
    model?: string
    agent?: string
    cost?: number | null
    tokens?: TokenUsage | null
    tool_calls?: unknown[]
    toolCalls?: unknown[]
    created_at?: string
    time?: { created?: string }
    parts?: SessionPart[]
    type?: string
    event_type?: string
    part?: unknown
}
