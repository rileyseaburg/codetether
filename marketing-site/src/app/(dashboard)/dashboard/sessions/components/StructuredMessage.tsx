'use client'

import { useState, memo, useId } from 'react'
import {
    Project,
    Session,
    Message,
    Part,
    Diff,
    Todo,
    TodoList,
    SessionDiff,
    isSessionID,
    isMessageID,
    isPartID
} from '../../../../../../opencode-storage-types'
import { JsonNode } from './JsonNode'
import { CopyButton } from './CopyButton'
import type { JsonValue, ParsedJsonPayload } from './JsonHelpers'
import { formatCost } from '../utils'

type OpenCodeDataType =
    | { type: 'Project'; data: Project }
    | { type: 'Session'; data: Session }
    | { type: 'Message'; data: Message }
    | { type: 'Part'; data: Part }
    | { type: 'Diff'; data: Diff }
    | { type: 'Todo'; data: Todo }
    | { type: 'TodoList'; data: TodoList }
    | { type: 'SessionDiff'; data: SessionDiff }
    | { type: 'EventLog'; data: Record<string, any>[] }
    | { type: 'Unknown'; data: unknown }

interface StructuredMessageProps {
    payload: unknown
    isUser?: boolean
    model?: string
}

type EventSummary = {
    id: string
    kind: 'step_start' | 'step_finish' | 'text' | 'tool' | 'status' | 'error' | 'command' | 'file' | 'diagnostic' | 'todo' | 'message' | 'routing' | 'idle' | 'agent' | 'subtask' | 'other'
    label: string
    detail?: string
    rawType?: string
    timestamp?: string
    agent?: string
    agentKind?: 'primary' | 'subagent'
}

type UnwrappedPayload = {
    value: unknown
    kind?: ParsedJsonPayload['kind']
}

const EVENT_ARRAY_KEYS = ['events', 'data', 'payload', 'items']
const PRIMARY_AGENTS = new Set(['build', 'plan'])
const SUBAGENTS = new Set(['general', 'explore', 'title', 'summary', 'compaction', 'code'])

function isParsedJsonPayload(payload: unknown): payload is ParsedJsonPayload {
    if (!payload || typeof payload !== 'object') return false
    const candidate = payload as { kind?: unknown; value?: unknown }
    return (candidate.kind === 'single' || candidate.kind === 'lines') && 'value' in candidate
}

function unwrapPayload(payload: unknown): UnwrappedPayload {
    if (isParsedJsonPayload(payload)) return { value: payload.value, kind: payload.kind }
    return { value: payload }
}

function isEventLike(item: unknown): item is Record<string, any> {
    if (!item || typeof item !== 'object') return false
    const obj = item as Record<string, unknown>
    return (
        typeof obj.type === 'string' ||
        typeof obj.event_type === 'string' ||
        typeof obj.event === 'string' ||
        (typeof obj.part === 'object' && obj.part !== null)
    )
}

function extractEventItems(value: unknown): Record<string, any>[] | null {
    if (Array.isArray(value)) {
        const events = value.filter(isEventLike)
        return events.length ? events : null
    }
    if (value && typeof value === 'object') {
        const obj = value as Record<string, unknown>
        for (const key of EVENT_ARRAY_KEYS) {
            const candidate = obj[key]
            if (Array.isArray(candidate)) {
                const events = candidate.filter(isEventLike)
                if (events.length) return events
            }
        }
    }
    return null
}

function normalizeEventType(rawType: string): string {
    return rawType.replace(/^part\./, '').replace(/[-.]/g, '_').toLowerCase()
}

function extractEventPart(event: Record<string, any>): Record<string, any> {
    const part =
        event.part ??
        event.properties?.part ??
        event.payload?.part ??
        event.data?.part ??
        event.event?.part ??
        {}
    return typeof part === 'object' && part !== null ? part : {}
}

function extractTextContent(value: unknown): string | undefined {
    if (!value) return undefined
    if (typeof value === 'string') return value
    if (typeof value !== 'object') return undefined
    const obj = value as Record<string, unknown>
    if (typeof obj.text === 'string') return obj.text
    if (typeof obj.delta === 'string') return obj.delta
    if (typeof obj.content === 'string') return obj.content
    if (Array.isArray(obj.content)) {
        return obj.content
            .map((entry) => {
                if (typeof entry === 'string') return entry
                if (entry && typeof entry === 'object' && typeof (entry as Record<string, unknown>).text === 'string') {
                    return (entry as Record<string, unknown>).text as string
                }
                return ''
            })
            .join('')
    }
    return undefined
}

function toMilliseconds(value: unknown): number | undefined {
    if (typeof value === 'number' && Number.isFinite(value)) {
        return value > 1e11 ? value : value * 1000
    }
    if (typeof value === 'string') {
        const parsed = Date.parse(value)
        return Number.isFinite(parsed) ? parsed : undefined
    }
    return undefined
}

function formatEventTimestamp(value: unknown): string | undefined {
    const ms = toMilliseconds(value)
    if (!ms) return undefined
    return new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatDuration(ms: number): string {
    if (!Number.isFinite(ms) || ms <= 0) return ''
    if (ms < 1000) return `${Math.round(ms)}ms`
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
    const minutes = Math.floor(ms / 60000)
    const seconds = Math.floor((ms % 60000) / 1000)
    return `${minutes}m ${seconds}s`
}

function formatTokenSummary(tokens: Record<string, any> | undefined): string | undefined {
    if (!tokens || typeof tokens !== 'object') return undefined
    const input = typeof tokens.input === 'number' ? tokens.input : 0
    const output = typeof tokens.output === 'number' ? tokens.output : 0
    const reasoning = typeof tokens.reasoning === 'number' ? tokens.reasoning : 0
    const cache = tokens.cache && typeof tokens.cache === 'object' ? tokens.cache : undefined
    const cacheRead = cache && typeof cache.read === 'number' ? cache.read : 0
    const cacheWrite = cache && typeof cache.write === 'number' ? cache.write : 0
    const parts: string[] = []
    if (input) parts.push(`${input} in`)
    if (output) parts.push(`${output} out`)
    if (reasoning) parts.push(`${reasoning} reasoning`)
    if (cacheRead || cacheWrite) parts.push(`cache ${cacheRead}r/${cacheWrite}w`)
    return parts.length ? `Tokens: ${parts.join(', ')}` : undefined
}

function truncateText(text: string, maxLen: number): string {
    if (text.length <= maxLen) return text
    return `${text.slice(0, Math.max(0, maxLen - 3))}...`
}

function classifyAgent(name: string): 'primary' | 'subagent' {
    if (PRIMARY_AGENTS.has(name)) return 'primary'
    if (SUBAGENTS.has(name)) return 'subagent'
    return 'primary'
}

function getAgentBadge(agent: string, kind: 'primary' | 'subagent'): string {
    return kind === 'subagent' ? `Subagent ${agent}` : `Agent ${agent}`
}

function extractAgentFromEvent(event: Record<string, any>, part: Record<string, any>): { name: string; kind: 'primary' | 'subagent' } | undefined {
    const role = typeof event.role === 'string' ? event.role : undefined
    if (role === 'user') return undefined

    const subagentDirect =
        (typeof event.subagent === 'string' && event.subagent) ||
        (typeof event.subagent_type === 'string' && event.subagent_type) ||
        (typeof event.subagentType === 'string' && event.subagentType)

    if (subagentDirect) return { name: subagentDirect, kind: 'subagent' }

    const direct =
        (typeof event.agent === 'string' && event.agent) ||
        (typeof event.agent_name === 'string' && event.agent_name) ||
        (typeof event.agentName === 'string' && event.agentName)

    if (direct) return { name: direct, kind: classifyAgent(direct) }

    const infoAgent =
        event.info && typeof event.info === 'object' && typeof event.info.agent === 'string'
            ? event.info.agent
            : event.properties &&
                typeof event.properties === 'object' &&
                event.properties.info &&
                typeof event.properties.info === 'object' &&
                typeof event.properties.info.agent === 'string'
                ? event.properties.info.agent
                : undefined

    if (infoAgent) return { name: infoAgent, kind: classifyAgent(infoAgent) }

    if (part) {
        const partType = typeof part.type === 'string' ? normalizeEventType(part.type) : ''
        if (partType === 'agent' && typeof part.name === 'string') {
            return { name: part.name, kind: classifyAgent(part.name) }
        }
        if (partType === 'subtask' && typeof part.agent === 'string') {
            return { name: part.agent, kind: 'subagent' }
        }
    }

    return undefined
}

function buildEventSummaries(events: Record<string, any>[]): EventSummary[] {
    let currentAgent: { name: string; kind: 'primary' | 'subagent' } | undefined

    return events.map((event, index) => {
        const part = extractEventPart(event)
        const detectedAgent = extractAgentFromEvent(event, part)
        if (detectedAgent) {
            currentAgent = detectedAgent
        }

        const summary = summarizeEvent(event, index)
        const agentName = detectedAgent?.name || currentAgent?.name
        const agentKind = detectedAgent?.kind || currentAgent?.kind
        const label = summary.kind === 'text' && agentName && agentKind
            ? agentKind === 'subagent'
                ? 'Subagent message'
                : 'Agent message'
            : summary.kind === 'agent' && agentName && agentKind === 'subagent'
                ? 'Subagent selected'
                : summary.label

        return {
            ...summary,
            label,
            agent: agentName,
            agentKind: agentKind,
        }
    })
}

function summarizeEvent(event: Record<string, any>, index: number): EventSummary {
    const part = extractEventPart(event)
    const rawType = String(event.event_type || event.type || event.event || part.type || '').trim()
    const normalized = normalizeEventType(rawType)
    const kind =
        normalized.includes('step_start') ? 'step_start'
            : normalized.includes('step_finish') || normalized.includes('step_end') || normalized.includes('end_step') ? 'step_finish'
                : normalized.includes('subtask') ? 'subtask'
                    : normalized === 'agent' || normalized === 'subagent' || normalized.startsWith('agent_') || normalized.startsWith('subagent_') ? 'agent'
                        : normalized.includes('tool') ? 'tool'
                            : normalized.includes('text') ? 'text'
                                : normalized.includes('status') ? 'status'
                                    : normalized.includes('error') ? 'error'
                                        : normalized.includes('command') ? 'command'
                                            : normalized.includes('file_edit') ? 'file'
                                                : normalized.includes('diagnostic') ? 'diagnostic'
                                                    : normalized.includes('todo') ? 'todo'
                                                        : normalized.includes('message') ? 'message'
                                                            : normalized.includes('routing') ? 'routing'
                                                                : normalized.includes('idle') ? 'idle'
                                                                    : 'other'

    const labelMap: Record<EventSummary['kind'], string> = {
        step_start: 'Step started',
        step_finish: 'Step finished',
        tool: 'Tool',
        text: 'Agent message',
        status: 'Status update',
        error: 'Error',
        command: 'Command',
        file: 'File edit',
        diagnostic: 'Diagnostics',
        todo: 'Todo update',
        message: 'Message update',
        routing: 'RLM routing',
        idle: 'Idle',
        agent: 'Agent selected',
        subtask: 'Subagent task',
        other: rawType || 'Event',
    }

    const detailParts: string[] = []
    if (kind === 'step_finish') {
        const tokens = (part.tokens || event.tokens) as Record<string, any> | undefined
        const costValue = typeof part.cost === 'number' ? part.cost : typeof event.cost === 'number' ? event.cost : undefined
        const costText = typeof costValue === 'number' ? formatCost(costValue) : ''
        const reason = typeof part.reason === 'string' ? part.reason : typeof event.reason === 'string' ? event.reason : ''
        const start = toMilliseconds(part.time?.start ?? event.time?.start)
        const end = toMilliseconds(part.time?.end ?? event.time?.end)
        const duration = start && end ? formatDuration(end - start) : ''
        if (duration) detailParts.push(`Duration ${duration}`)
        const tokenSummary = formatTokenSummary(tokens)
        if (tokenSummary) detailParts.push(tokenSummary)
        if (costText) detailParts.push(`Cost ${costText}`)
        if (reason) detailParts.push(`Reason: ${truncateText(reason, 80)}`)
    } else if (kind === 'step_start') {
        const snapshot = part.snapshot || event.snapshot
        const mode = event.mode || part.mode
        if (mode) detailParts.push(`Mode: ${mode}`)
        if (snapshot) detailParts.push('Snapshot captured')
    } else if (kind === 'tool') {
        const toolName = part.tool || event.tool_name || event.tool || event.name || 'Tool'
        const status = part.state?.status || event.status
        const title = part.state?.title || event.title
        detailParts.push(String(toolName))
        if (status) detailParts.push(String(status))
        if (title) detailParts.push(truncateText(String(title), 80))
    } else if (kind === 'text') {
        const text = extractTextContent(part) || extractTextContent(event) || ''
        if (text) detailParts.push(truncateText(text.trim(), 120))
    } else if (kind === 'status') {
        const status = event.status || event.message || event.state
        if (status) detailParts.push(truncateText(String(status), 120))
    } else if (kind === 'error') {
        const message = event.error || event.message || part.error
        if (message) detailParts.push(truncateText(String(message), 120))
    } else if (kind === 'command') {
        const command = event.command || part.command
        const exitCode = event.exit_code ?? event.exitCode ?? part.exitCode
        if (command) detailParts.push(String(command))
        if (typeof exitCode === 'number') detailParts.push(`exit ${exitCode}`)
    } else if (kind === 'file') {
        const path = event.path || part.path || part.file
        if (path) detailParts.push(String(path))
    } else if (kind === 'diagnostic') {
        const diagnostics = event.diagnostics || part.diagnostics
        if (Array.isArray(diagnostics)) detailParts.push(`${diagnostics.length} diagnostics`)
    } else if (kind === 'todo') {
        const todos = event.todos || part.todos
        if (Array.isArray(todos)) detailParts.push(`${todos.length} items`)
    } else if (kind === 'agent') {
        const agentInfo = extractAgentFromEvent(event, part)
        if (agentInfo) detailParts.push(getAgentBadge(agentInfo.name, agentInfo.kind))
    } else if (kind === 'subtask') {
        const subtaskAgent = extractAgentFromEvent(event, part)
        const description = part.description || event.description
        if (subtaskAgent) detailParts.push(getAgentBadge(subtaskAgent.name, subtaskAgent.kind))
        if (description) detailParts.push(truncateText(String(description), 90))
    }

    const timestamp =
        formatEventTimestamp(event.timestamp) ||
        formatEventTimestamp(event.time?.created) ||
        formatEventTimestamp(part.time?.start) ||
        formatEventTimestamp(part.time?.end)

    const roleLabel = typeof event.role === 'string' ? event.role : undefined
    const baseLabel = kind === 'text' && roleLabel === 'user' ? 'User message' : labelMap[kind]

    return {
        id: String(event.id || part.id || `event-${index}`),
        kind,
        label: baseLabel,
        detail: detailParts.length ? detailParts.join(' | ') : undefined,
        rawType: rawType || undefined,
        timestamp,
    }
}

function getEventDotClass(kind: EventSummary['kind']): string {
    switch (kind) {
        case 'step_start':
            return 'bg-cyan-500 dark:bg-cyan-400'
        case 'step_finish':
            return 'bg-emerald-500 dark:bg-emerald-400'
        case 'tool':
            return 'bg-sky-500 dark:bg-sky-400'
        case 'text':
            return 'bg-gray-400 dark:bg-gray-500'
        case 'status':
            return 'bg-amber-500 dark:bg-amber-400'
        case 'error':
            return 'bg-red-500 dark:bg-red-400'
        default:
            return 'bg-gray-300 dark:bg-gray-600'
    }
}

function detectOpenCodeType(data: unknown): OpenCodeDataType {
    if (typeof data !== 'object' || data === null) {
        return { type: 'Unknown', data }
    }

    const events = extractEventItems(data)
    if (events) {
        return { type: 'EventLog', data: events }
    }

    const obj = data as Record<string, unknown>

    if ('id' in obj && 'worktree' in obj && 'time' in obj && !('sessionID' in obj)) {
        return { type: 'Project', data: data as Project }
    }

    if ('id' in obj && isSessionID(obj.id as string) && 'version' in obj && 'projectID' in obj) {
        return { type: 'Session', data: data as Session }
    }

    if ('id' in obj && isMessageID(obj.id as string) && 'sessionID' in obj && 'role' in obj) {
        return { type: 'Message', data: data as Message }
    }

    if ('id' in obj && isPartID(obj.id as string) && 'messageID' in obj && 'type' in obj) {
        return { type: 'Part', data: data as Part }
    }

    if ('file' in obj && 'before' in obj && 'after' in obj && 'additions' in obj) {
        return { type: 'Diff', data: data as Diff }
    }

    if ('content' in obj && 'status' in obj && 'priority' in obj) {
        return { type: 'Todo', data: data as Todo }
    }

    if (Array.isArray(data) && data.length > 0 && typeof data[0] === 'object' && data[0] && 'content' in data[0]) {
        return { type: 'TodoList', data: data as TodoList }
    }

    if (Array.isArray(data) && data.length > 0 && typeof data[0] === 'object' && data[0] && 'file' in data[0] && 'additions' in data[0]) {
        return { type: 'SessionDiff', data: data as SessionDiff }
    }

    return { type: 'Unknown', data }
}

function getDataTypeLabel(dataType: OpenCodeDataType): string {
    switch (dataType.type) {
        case 'Project':
            const p = dataType.data as Project
            return `Project${p.id === 'global' ? ' (Global)' : ''} - ${p.worktree.split('/').pop() || p.worktree}`
        case 'Session':
            const s = dataType.data as Session
            return `Session - ${s.title}`
        case 'Message':
            const m = dataType.data as Message
            return `${m.role === 'user' ? 'User' : 'Assistant'} Message`
        case 'Part':
            return `Content Part - ${dataType.data.type}`
        case 'Diff':
            return `File Change - ${dataType.data.file}`
        case 'Todo':
            const status = dataType.data.status
            return `Todo (${status})`
        case 'TodoList':
            return `${dataType.data.length} Todo Item${dataType.data.length !== 1 ? 's' : ''}`
        case 'SessionDiff':
            return `${dataType.data.length} File Change(s)`
        case 'EventLog':
            return `Execution Timeline (${dataType.data.length})`
        default:
            return 'Structured Data'
    }
}

function StructuredMessageInner({ payload, isUser = false, model }: StructuredMessageProps) {
    const [isExpanded, setIsExpanded] = useState(false)
    const [showTimeline, setShowTimeline] = useState(false)
    const id = useId()

    const { value: rawValue, kind } = unwrapPayload(payload)
    const dataType = detectOpenCodeType(rawValue)
    const jsonText = (() => {
        if (kind === 'lines' && Array.isArray(rawValue)) {
            return rawValue.map((line) => JSON.stringify(line)).join('\n')
        }
        try {
            const stringified = JSON.stringify(rawValue, null, 2)
            return stringified ?? String(rawValue)
        } catch {
            return String(rawValue)
        }
    })()

    const eventSummaries = dataType.type === 'EventLog'
        ? buildEventSummaries(dataType.data)
        : []
    const timelineEvents = eventSummaries.filter((item) => item.kind !== 'text')
    const previewEvents = timelineEvents.slice(0, 5)
    const remainingTimelineEvents = Math.max(0, timelineEvents.length - previewEvents.length)
    const messageEvents = eventSummaries.filter((item) => item.kind === 'text' && item.detail && item.label !== 'User message')
    const previewMessages = messageEvents.slice(-3)
    const remainingMessages = Math.max(0, messageEvents.length - previewMessages.length)
    const hasMessagePreview = previewMessages.length > 0
    const timelineVisible = !hasMessagePreview || showTimeline
    const eventCounts = eventSummaries.reduce(
        (acc, item) => {
            if (item.kind === 'step_start' || item.kind === 'step_finish') acc.steps += 1
            else if (item.kind === 'tool') acc.tools += 1
            else if (item.kind === 'text' && item.label !== 'User message') acc.outputs += 1
            else if (item.kind === 'status') acc.status += 1
            else if (item.kind === 'error') acc.errors += 1
            return acc
        },
        { steps: 0, tools: 0, outputs: 0, status: 0, errors: 0 }
    )

    const bubbleClass = isUser
        ? 'bg-cyan-600 text-white ring-cyan-700/40'
        : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 ring-gray-200 dark:ring-white/10'

    const panelClass = isUser
        ? 'border-cyan-400/30 bg-cyan-500/10 text-cyan-50'
        : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/30 text-gray-700 dark:text-gray-200'
    const panelMutedText = isUser ? 'text-cyan-100/80' : 'text-gray-500 dark:text-gray-400'
    const chipClass = isUser
        ? 'bg-cyan-500/20 text-cyan-100'
        : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
    const eventRowClass = isUser
        ? 'border-cyan-400/20 bg-cyan-500/10'
        : 'border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-800/50'
    const messageRowClass = isUser
        ? 'border-cyan-400/25 bg-cyan-500/15'
        : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/60'
    const eventLabelClass = isUser ? 'text-cyan-50' : 'text-gray-700 dark:text-gray-100'
    const eventDetailClass = isUser ? 'text-cyan-100/80' : 'text-gray-600 dark:text-gray-300'
    const eventBadgeClass = isUser
        ? 'bg-cyan-500/30 text-cyan-100'
        : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300'

    const typeLabel = getDataTypeLabel(dataType)

    return (
        <div className={`relative rounded-2xl shadow-sm ring-1 ${bubbleClass} overflow-hidden`}>
            <div className={`px-4 py-2.5 border-b ${isUser ? 'border-cyan-500/30' : 'border-gray-100 dark:border-gray-700/50'} flex items-center justify-between`}>
                <div className="flex items-center gap-2 text-xs">
                    <svg
                        className="w-4 h-4 shrink-0"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                        aria-hidden="true"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                    </svg>
                    <span className={`font-semibold ${isUser ? 'text-cyan-100' : 'text-gray-700 dark:text-gray-200'}`}>
                        {typeLabel}
                    </span>
                    {model && (
                        <span className={`opacity-60 ${isUser ? 'text-cyan-100' : 'text-gray-400'}`}>
                            • {model}
                        </span>
                    )}
                </div>
                <CopyButton text={jsonText} label="Copy data" />
            </div>

            <div>
                {isExpanded ? (
                    <div
                        id={id}
                        className="p-4 max-h-96 overflow-y-auto"
                        aria-label="Full structured data content"
                    >
                        <JsonNode value={rawValue as JsonValue} depth={0} path="root" />
                    </div>
                ) : (
                    <div className="px-4 py-3">
                        <div className="space-y-2">
                            {dataType.type === 'EventLog' && (
                                <div className="space-y-3">
                                    {hasMessagePreview && (
                                        <div className="space-y-2">
                                            <div className={`rounded-lg border p-3 ${panelClass}`}>
                                                <div className={`text-xs font-semibold ${eventLabelClass}`}>Agent messages</div>
                                                <p className={`mt-1 text-[11px] ${panelMutedText}`}>
                                                    Showing the most recent agent outputs first. Subagent messages are labeled.
                                                </p>
                                            </div>
                                            <div className="space-y-2">
                                                {previewMessages.map((item, index) => (
                                                    <div key={`${item.id}-msg-${index}`} className={`rounded-lg border px-3 py-2 ${messageRowClass}`}>
                                                        <div className="flex flex-wrap items-center gap-2">
                                                            <span className={`text-xs font-semibold ${eventLabelClass}`}>{item.label}</span>
                                                            {item.agent && item.agentKind && (
                                                                <span className={`rounded-full px-2 py-0.5 text-[10px] ${eventBadgeClass}`}>
                                                                    {getAgentBadge(item.agent, item.agentKind)}
                                                                </span>
                                                            )}
                                                            {item.timestamp && (
                                                                <span className="text-[10px] text-gray-400 dark:text-gray-500">{item.timestamp}</span>
                                                            )}
                                                        </div>
                                                        {item.detail && (
                                                            <p className={`mt-1 text-sm leading-relaxed ${eventDetailClass}`}>{item.detail}</p>
                                                        )}
                                                    </div>
                                                ))}
                                                {remainingMessages > 0 && (
                                                    <div className={`text-center text-[11px] ${panelMutedText}`}>
                                                        +{remainingMessages} more messages
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    )}
                                    {hasMessagePreview && (
                                        <button
                                            type="button"
                                            onClick={() => setShowTimeline((prev) => !prev)}
                                            className={`w-full rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${isUser
                                                    ? 'border-cyan-400/40 bg-cyan-500/10 text-cyan-100 hover:bg-cyan-500/20'
                                                    : 'border-gray-200 dark:border-gray-700 bg-white/70 dark:bg-gray-800/40 text-gray-600 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700'
                                                }`}
                                            aria-expanded={timelineVisible}
                                        >
                                            {timelineVisible ? 'Hide execution timeline' : 'Show execution timeline'}
                                        </button>
                                    )}

                                    {timelineVisible && (
                                        <>
                                            <div className={`rounded-lg border p-3 text-xs ${panelClass}`}>
                                                <div className={`text-xs font-semibold ${eventLabelClass}`}>Execution timeline</div>
                                                <p className={`mt-1 text-[11px] ${panelMutedText}`}>
                                                    Step started marks the beginning of a subtask. Step finished (end_step) marks completion and can include tokens or cost.
                                                </p>
                                                <div className="mt-2 flex flex-wrap gap-2">
                                                    {eventCounts.steps > 0 && (
                                                        <span className={`rounded-full px-2 py-0.5 text-[10px] ${chipClass}`}>Steps {eventCounts.steps}</span>
                                                    )}
                                                    {eventCounts.tools > 0 && (
                                                        <span className={`rounded-full px-2 py-0.5 text-[10px] ${chipClass}`}>Tools {eventCounts.tools}</span>
                                                    )}
                                                    {eventCounts.outputs > 0 && (
                                                        <span className={`rounded-full px-2 py-0.5 text-[10px] ${chipClass}`}>Messages {eventCounts.outputs}</span>
                                                    )}
                                                    {eventCounts.status > 0 && (
                                                        <span className={`rounded-full px-2 py-0.5 text-[10px] ${chipClass}`}>Status {eventCounts.status}</span>
                                                    )}
                                                    {eventCounts.errors > 0 && (
                                                        <span className={`rounded-full px-2 py-0.5 text-[10px] ${chipClass}`}>Errors {eventCounts.errors}</span>
                                                    )}
                                                </div>
                                            </div>
                                            <div className="space-y-2">
                                                {previewEvents.length > 0 ? (
                                                    previewEvents.map((item, index) => (
                                                        <div key={`${item.id}-${index}`} className={`flex items-start gap-2 rounded-lg border px-3 py-2 ${eventRowClass}`}>
                                                            <span className={`mt-1 h-2.5 w-2.5 rounded-full ${getEventDotClass(item.kind)}`} />
                                                            <div className="flex-1">
                                                                <div className="flex flex-wrap items-center gap-2">
                                                                    <span className={`text-xs font-semibold ${eventLabelClass}`}>{item.label}</span>
                                                                    {item.rawType && (item.kind === 'step_start' || item.kind === 'step_finish' || item.kind === 'other') && (
                                                                        <span className={`rounded-full px-2 py-0.5 text-[10px] ${eventBadgeClass}`}>{item.rawType}</span>
                                                                    )}
                                                                    {item.agent && item.agentKind && (
                                                                        <span className={`rounded-full px-2 py-0.5 text-[10px] ${eventBadgeClass}`}>
                                                                            {getAgentBadge(item.agent, item.agentKind)}
                                                                        </span>
                                                                    )}
                                                                    {item.timestamp && (
                                                                        <span className="text-[10px] text-gray-400 dark:text-gray-500">{item.timestamp}</span>
                                                                    )}
                                                                </div>
                                                                {item.detail && (
                                                                    <p className={`mt-1 text-[11px] ${eventDetailClass}`}>{item.detail}</p>
                                                                )}
                                                            </div>
                                                        </div>
                                                    ))
                                                ) : (
                                                    <div className={`text-center text-[11px] ${panelMutedText}`}>
                                                        No execution steps yet.
                                                    </div>
                                                )}
                                                {remainingTimelineEvents > 0 && (
                                                    <div className={`text-center text-[11px] ${panelMutedText}`}>
                                                        +{remainingTimelineEvents} more events
                                                    </div>
                                                )}
                                            </div>
                                        </>
                                    )}
                                </div>
                            )}

                            {dataType.type === 'Project' && (
                                <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/30">
                                    <div className="grid grid-cols-2 gap-2 text-xs">
                                        <div>
                                            <span className={`font-medium ${isUser ? 'text-cyan-200' : 'text-gray-500'}`}>ID:</span>{' '}
                                            <span className={`block truncate ${isUser ? 'text-cyan-100' : 'text-gray-700'}`}>{(dataType.data as Project).id.slice(0, 8)}...</span>
                                        </div>
                                        <div>
                                            <span className={`font-medium ${isUser ? 'text-cyan-200' : 'text-gray-500'}`}>VCS:</span>{' '}
                                            <span className={isUser ? 'text-cyan-100' : 'text-gray-700'}>{(dataType.data as Project).vcs || 'None'}</span>
                                        </div>
                                        <div>
                                            <span className={`font-medium ${isUser ? 'text-cyan-200' : 'text-gray-500'}`}>Sandboxes:</span>{' '}
                                            <span className={isUser ? 'text-cyan-100' : 'text-gray-700'}>{(dataType.data as Project).sandboxes.length}</span>
                                        </div>
                                    </div>
                                    <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
                                        <div className={`text-xs ${isUser ? 'text-cyan-200' : 'text-gray-400'}`}>
                                            {(dataType.data as Project).worktree}
                                        </div>
                                    </div>
                                </div>
                            )}

                            {dataType.type === 'Session' && (
                                <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/30">
                                    <div className={`text-sm font-medium ${isUser ? 'text-cyan-100 mb-2' : 'text-gray-700 mb-2'}`}>
                                        {(dataType.data as Session).title}
                                    </div>
                                    <div className="grid grid-cols-2 gap-2 text-xs">
                                        <div>
                                            <span className={`font-medium ${isUser ? 'text-cyan-200' : 'text-gray-500'}`}>Version:</span>{' '}
                                            <span className={isUser ? 'text-cyan-100' : 'text-gray-700'}>{(dataType.data as Session).version}</span>
                                        </div>
                                        <div>
                                            <span className={`font-medium ${isUser ? 'text-cyan-200' : 'text-gray-500'}`}>Dir:</span>{' '}
                                            <span className={`block truncate ${isUser ? 'text-cyan-100' : 'text-gray-700'}`}>{(dataType.data as Session).directory.split('/').pop() || '...'}</span>
                                        </div>
                                    </div>
                                    {(dataType.data as Session).summary && (
                                        <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600 flex gap-4 text-xs">
                                            <span className={isUser ? 'text-green-200' : 'text-green-600'}>
                                                +{(dataType.data as Session).summary?.additions || 0}
                                            </span>
                                            <span className={isUser ? 'text-red-200' : 'text-red-600'}>
                                                -{(dataType.data as Session).summary?.deletions || 0}
                                            </span>
                                            <span className={isUser ? 'text-cyan-200' : 'text-cyan-600'}>
                                                {(dataType.data as Session).summary?.files || 0} files
                                            </span>
                                        </div>
                                    )}
                                </div>
                            )}

                             {dataType.type === 'Message' && (
                                <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/30">
                                    <div className="flex items-center justify-between text-xs mb-2">
                                        <span className={`px-2 py-0.5 rounded font-medium ${(dataType.data as Message).role === 'user'
                                                ? 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900 dark:text-cyan-200'
                                                : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-200'
                                            }`}>
                                            {(dataType.data as Message).role}
                                        </span>
                                         <div className={`opacity-70 ${isUser ? 'text-cyan-100' : 'text-gray-500'}`}>
                                            {(dataType.data as Message).mode || 'No mode'}
                                        </div>
                                    </div>
                                    {(dataType.data as Message).tokens && (
                                        <div className="flex gap-3 text-xs mt-2">
                                            <span>In: {(dataType.data as Message).tokens?.input || 0}</span>
                                            <span>Out: {(dataType.data as Message).tokens?.output || 0}</span>
                                        </div>
                                    )}
                                </div>
                            )}

                             {dataType.type === 'Diff' && (
                                <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/30">
                                    <div className={`text-sm font-medium ${isUser ? 'text-cyan-100 mb-2' : 'text-gray-700 mb-2'}`}>
                                        {(dataType.data as Diff).file}
                                    </div>
                                    <div className="flex gap-4 text-xs">
                                        <span className={isUser ? 'text-green-200' : 'text-green-600'}>
                                            +{dataType.data.additions} lines
                                        </span>
                                        <span className={isUser ? 'text-red-200' : 'text-red-600'}>
                                            -{dataType.data.deletions} lines
                                        </span>
                                    </div>
                                </div>
                            )}

                            {dataType.type === 'TodoList' && (
                                <div className="space-y-1">
                                    {(dataType.data as TodoList).slice(0, 3).map((todo: Todo, idx: number) => (
                                        <div
                                            key={todo.id || idx}
                                            className="p-2 rounded bg-gray-50 dark:bg-gray-700/30 text-xs flex items-center gap-2"
                                        >
                                            <span className={`w-2 h-2 rounded-full ${todo.status === 'completed' ? 'bg-green-500' :
                                                    todo.status === 'in_progress' ? 'bg-blue-500' :
                                                        todo.priority === 'high' ? 'bg-red-500' :
                                                            'bg-gray-400'
                                                }`} />
                                             <span className={isUser ? 'text-cyan-100' : 'text-gray-700'}>{todo.content}</span>
                                        </div>
                                    ))}
                                    {dataType.data.length > 3 && (
                                        <div className="text-xs text-center pt-1 opacity-70">
                                            +{(dataType.data as TodoList).length - 3} more items
                                        </div>
                                    )}
                                </div>
                            )}

                             {dataType.type === 'Unknown' && (
                                <p className={`text-sm ${isUser ? 'text-cyan-50' : 'text-gray-600 dark:text-gray-400'}`}>
                                    Complex data structure. Click below to view full content.
                                </p>
                            )}
                        </div>
                    </div>
                )}

                <div className="px-4 pb-3">
                     <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className={`w-full flex items-center justify-center gap-2 px-4 py-2 text-xs font-medium rounded-lg transition-colors ${isUser
                                ? 'bg-cyan-500/20 text-cyan-100 hover:bg-cyan-500/30'
                                : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600'
                            }`}
                        aria-expanded={isExpanded}
                        aria-controls={id}
                        aria-label={isExpanded ? 'Hide structured data' : 'View full structured data'}
                    >
                        {isExpanded ? (
                            <>
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                                </svg>
                                Hide
                            </>
                        ) : (
                            <>
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                </svg>
                                View Full Data
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    )
}

export const StructuredMessage = memo(StructuredMessageInner, (prev, next) => {
    return (
        JSON.stringify(prev.payload) === JSON.stringify(next.payload) &&
        prev.isUser === next.isUser &&
        prev.model === next.model
    )
})
StructuredMessage.displayName = 'StructuredMessage'
