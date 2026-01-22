import type { TokenUsage } from './tokens'

export type NormalizedRole = 'user' | 'assistant' | 'system'

export type ToolEntry = {
    tool: string
    status?: string
    title?: string
    input?: unknown
    output?: unknown
    error?: unknown
}

export type ChatItem = {
    key: string
    role: NormalizedRole
    label: string
    model?: string
    createdAt?: string
    text: string
    reasoning?: string
    tools?: ToolEntry[]
    usage?: { cost?: number; tokens?: TokenUsage }
}
