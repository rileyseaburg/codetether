import type { TokenUsage, ToolState } from './tokens'

export interface SessionPartBase {
    id: string
    sessionID: string
    messageID: string
    type: string
    text?: string
    time?: {
        start?: number
        end?: number
    }
}

export interface SessionPart extends SessionPartBase {
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

export interface SessionMessageBase {
    id: string
    sessionID: string
    role: 'user' | 'assistant'
    time: {
        created: number
        completed?: number
    }
    summary?: {
        title?: string
        diffs?: unknown[]
    }
    parentID?: string
    modelID?: string
    providerID?: string
    mode?: string
    path?: {
        cwd: string
        root: string
    }
    cost?: number
    tokens?: TokenUsage
    agent?: string
    model?: {
        providerID: string
        modelID: string
    }
}

export type SessionMessage = SessionMessageBase

export interface SessionMessageWithParts {
    info: SessionMessage
    parts: SessionPart[]
}
