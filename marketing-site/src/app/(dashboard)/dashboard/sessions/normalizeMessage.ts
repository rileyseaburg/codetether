import type { SessionMessageWithParts, ChatItem, NormalizedRole, SessionPart, SessionMessage } from './types'
import { extractUsage, extractTools } from './normalizers'
import { getText } from './normalizers/eventHelpers'
import { estimateCostFromTokens } from './utils'

function normalizeRole(role: SessionMessage['role'] | string): NormalizedRole {
    if (role === 'user') return 'user'
    if (role === 'assistant') return 'assistant'
    return 'system'
}

function formatTimestamp(timestamp?: number | string): string | undefined {
    if (!timestamp) return undefined
    if (typeof timestamp === 'string') {
        const parsed = Date.parse(timestamp)
        return Number.isFinite(parsed) ? new Date(parsed).toISOString() : undefined
    }
    if (!Number.isFinite(timestamp)) return undefined
    return new Date(timestamp).toISOString()
}

function collectPartText(parts: SessionPart[], type: string): string {
    return parts
        .filter((part) => part.type === type && part.text)
        .map((part) => part.text)
        .join('')
}

function parseStructuredEvents(rawText: string): SessionPart[] | null {
    const trimmed = rawText.trim()
    if (!trimmed) return null

    const events: Array<Record<string, any>> = []
    const extractChildEvents = (value: unknown) => {
        const childEvents: Array<Record<string, any>> = []
        const candidates: unknown[] = []

        if (Array.isArray(value)) {
            candidates.push(...value)
        } else if (value && typeof value === 'object') {
            const obj = value as Record<string, unknown>
            if (Array.isArray(obj.children)) {
                candidates.push(...obj.children)
            }
            const node = obj.node
            if (node && typeof node === 'object') {
                const nodeChildren = (node as Record<string, unknown>).children
                if (Array.isArray(nodeChildren)) {
                    candidates.push(...nodeChildren)
                } else if (typeof nodeChildren === 'string') {
                    try {
                        const parsed = JSON.parse(nodeChildren)
                        if (Array.isArray(parsed)) candidates.push(...parsed)
                    } catch {
                        // Ignore node children that are not valid JSON.
                    }
                }
            }
        }

        for (const candidate of candidates) {
            if (typeof candidate === 'string') {
                const line = candidate.trim()
                if (!line || line === '<br />' || line === '<br>') continue
                if (!line.startsWith('{') && !line.startsWith('[')) continue
                try {
                    const parsed = JSON.parse(line)
                    if (Array.isArray(parsed)) {
                        parsed.forEach((entry) => {
                            if (entry && typeof entry === 'object') childEvents.push(entry)
                        })
                    } else if (parsed && typeof parsed === 'object') {
                        childEvents.push(parsed)
                    }
                } catch {
                    // Ignore non-JSON child lines.
                }
            } else if (candidate && typeof candidate === 'object') {
                childEvents.push(candidate as Record<string, any>)
            }
        }

        return childEvents
    }
    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
        try {
            const parsed = JSON.parse(trimmed)
            if (Array.isArray(parsed)) {
                events.push(...parsed)
            } else if (parsed && typeof parsed === 'object') {
                const maybeEvents =
                    Array.isArray(parsed.events)
                        ? parsed.events
                        : Array.isArray(parsed.data)
                            ? parsed.data
                            : Array.isArray(parsed.payload)
                                ? parsed.payload
                                : null
                if (maybeEvents) {
                    events.push(...maybeEvents)
                } else {
                    const childEvents = extractChildEvents(parsed)
                    if (childEvents.length) {
                        events.push(...childEvents)
                    } else {
                        events.push(parsed)
                    }
                }
            }
        } catch {
            // Fall back to line parsing below.
        }
    }

    if (!events.length) {
        const lines = trimmed.split('\n').map((line) => line.trim()).filter(Boolean)
        for (const line of lines) {
            try {
                const parsed = JSON.parse(line)
                if (parsed && typeof parsed === 'object') events.push(parsed)
            } catch {
                // Ignore non-JSON lines.
            }
        }
    }

    if (!events.length) return null

    const parts: SessionPart[] = []
    let matched = false

    events.forEach((event, index) => {
        if (!event || typeof event !== 'object') return
        const candidate =
            event.part ??
            event.properties?.part ??
            event.payload?.part ??
            event.data?.part

        if (candidate && typeof candidate === 'object' && typeof candidate.type === 'string') {
            const id = String(candidate.id || `event-${index}`)
            const part: SessionPart = {
                id,
                sessionID: String(candidate.sessionID || ''),
                messageID: String(candidate.messageID || ''),
                type: candidate.type,
                text: candidate.text,
                tool: candidate.tool,
                callID: candidate.callID,
                state: candidate.state,
                reason: candidate.reason,
                cost: candidate.cost,
                tokens: candidate.tokens,
            }
            parts.push(part)
            matched = true
            return
        }

        const eventType =
            typeof event.event_type === 'string'
                ? event.event_type
                : typeof event.type === 'string'
                    ? event.type
                    : ''

        if (eventType === 'part.text' || eventType === 'text' || eventType === 'message.part.updated') {
            const delta = getText(event.part ?? event.properties ?? event)
            if (delta) {
                parts.push({
                    id: `event-${index}`,
                    sessionID: '',
                    messageID: '',
                    type: 'text',
                    text: delta,
                })
                matched = true
            }
        }

        if (eventType === 'part.reasoning' || eventType === 'reasoning') {
            const delta = getText(event.part ?? event.properties ?? event)
            if (delta) {
                parts.push({
                    id: `event-${index}`,
                    sessionID: '',
                    messageID: '',
                    type: 'reasoning',
                    text: delta,
                })
                matched = true
            }
        }
    })

    return matched ? parts : null
}

function looksLikeWorkerRegistryPayload(text: string): boolean {
    const trimmed = text.trim()
    if (!trimmed) return false

    const hasMarkers = (value: string, markers: string[]) =>
        markers.every((marker) => value.includes(marker))

    if (
        hasMarkers(trimmed, ["'worker_id':", "'models':", "'registered_at':"]) ||
        hasMarkers(trimmed, ['"worker_id"', '"models"', '"registered_at"'])
    ) {
        return true
    }

    if (trimmed.startsWith('{') || trimmed.startsWith('[')) {
        try {
            const parsed = JSON.parse(trimmed) as unknown
            if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
                const obj = parsed as Record<string, unknown>
                if ('worker_id' in obj && 'models' in obj && 'registered_at' in obj) {
                    return true
                }
                if ('models' in obj && 'global_codebase_id' in obj && 'last_seen' in obj) {
                    return true
                }
            }
            if (Array.isArray(parsed) && parsed.length && parsed.every((entry) => entry && typeof entry === 'object')) {
                const sample = parsed.slice(0, 3) as Array<Record<string, unknown>>
                if (sample.every((entry) => 'provider_id' in entry && 'capabilities' in entry)) {
                    return true
                }
            }
        } catch {
            // Ignore parsing failures and fall through to false.
        }
    }

    return false
}

export function normalizeMessage(msg: SessionMessageWithParts, idx: number): ChatItem | null {
    const info = (msg as { info?: SessionMessage }).info || (msg as unknown as SessionMessage)
    if (!info || typeof info !== 'object') return null

    const parts = Array.isArray(msg.parts) ? msg.parts : []
    const role = normalizeRole((info as any).role || (msg as any).role)
    const label = role === 'user' ? 'You' : role === 'assistant' ? 'Agent' : 'System'
    const model =
        info.modelID ||
        info.model?.modelID ||
        (typeof (info as any).model === 'string' ? (info as any).model : undefined) ||
        (typeof (msg as any).model === 'string' ? (msg as any).model : undefined)
    const providerID =
        info.providerID ||
        (typeof (info as any).model === 'object' && (info as any).model ? (info as any).model.providerID : undefined)
    const createdAt = formatTimestamp((info as any).time?.created || (msg as any).time?.created)

    let text = collectPartText(parts, 'text')
    let reasoning = collectPartText(parts, 'reasoning') || undefined
    let tools = extractTools(parts.filter((part) => part.type === 'tool'))
    let { cost, tokens } = extractUsage(info, parts.filter((part) => part.type === 'step-finish'))

    const fallbackContent =
        typeof (info as any).content === 'string'
            ? (info as any).content
            : typeof (msg as any).content === 'string'
                ? (msg as any).content
                : ''
    if (!text && fallbackContent) {
        text = fallbackContent
    }

    if (text && role !== 'user' && looksLikeWorkerRegistryPayload(text)) {
        return null
    }

    if (text) {
        const structuredParts = parseStructuredEvents(text)
        if (structuredParts) {
            const structuredText = collectPartText(structuredParts, 'text')
            const structuredReasoning = collectPartText(structuredParts, 'reasoning') || undefined
            const structuredTools = extractTools(structuredParts.filter((part) => part.type === 'tool'))
            const structuredUsage = extractUsage(info, structuredParts.filter((part) => part.type === 'step-finish'))

            if (structuredText || structuredReasoning || structuredTools.length) {
                text = structuredText
                reasoning = structuredReasoning
                tools = structuredTools
                cost = structuredUsage.cost ?? cost
                tokens = structuredUsage.tokens ?? tokens
            }
        }
    }

    if ((cost === undefined || cost === 0) && tokens) {
        const modelKey = model && !model.includes('/') && providerID ? `${providerID}/${model}` : model
        const estimated = estimateCostFromTokens(modelKey, tokens)
        if (typeof estimated === 'number') cost = estimated
    }

    if (!text && !reasoning && tools.length === 0) return null

    return {
        key: info.id || `${role}-${idx}`,
        role,
        label,
        model,
        createdAt,
        text,
        reasoning,
        tools: tools.length ? tools : undefined,
        usage: cost || tokens ? { cost, tokens } : undefined,
    }
}
