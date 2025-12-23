import type { SessionMessage, ChatItem, NormalizedRole } from './types'
import { safeJsonStringify } from './utils'
import { extractUsage, extractTools, createTextEvent, createReasoningEvent, createStepFinishEvent } from './normalizers'

export function normalizeMessage(msg: SessionMessage, idx: number): ChatItem | null {
    const info = msg?.info && typeof msg.info === 'object' ? msg.info : undefined
    const infoId = (info && 'id' in info) ? (info as any).id : undefined;
    const roleRaw = (info?.role || msg.role || '').toString()
    const role: NormalizedRole = roleRaw === 'human' || roleRaw === 'user' ? 'user' : roleRaw === 'assistant' || roleRaw === 'agent' ? 'assistant' : 'system'
    const parts = Array.isArray(msg.parts) ? msg.parts : Array.isArray(info?.parts) ? info?.parts : []
    const model = info?.model || msg.model ? String(info?.model || msg.model) : undefined
    const createdAt = msg.time?.created || msg.created_at ? String(msg.time?.created || msg.created_at) : undefined

    if (parts.length) {
        const textParts = parts.filter((p) => p?.type === 'text' && p.text)
        const reasoningParts = parts.filter((p) => p?.type === 'reasoning' && p.text)
        const { cost, tokens } = extractUsage(msg, info, parts.filter((p) => p?.type === 'step-finish'))
        const tools = extractTools(parts.filter((p) => p?.type === 'tool'))
        const r = role === 'system' ? 'assistant' : role
        return { key: String(msg.id || infoId || `${r}-${idx}`), role: r, label: r === 'user' ? 'You' : 'Agent', model, createdAt, text: textParts.map((p) => p.text).join(''), reasoning: reasoningParts.map((p) => p.text).join('') || undefined, tools: tools.length ? tools : undefined, usage: cost || tokens ? { cost, tokens } : undefined }
    }

    const content = info?.content ?? (msg as any)?.content
    const obj: any = content && typeof content === 'object' ? content : msg
    const type = (obj?.event_type || obj?.type || msg.event_type || msg.type || '').toString()
    const part: any = obj?.part || obj?.properties?.part || msg.part

    if (type === 'text' || type === 'part.text') return createTextEvent(msg, part, obj, type, model, createdAt, idx)
    if (type === 'part.reasoning' || type === 'reasoning') return createReasoningEvent(msg, part, obj, type, model, createdAt, idx)
    if (type === 'step_finish' || type === 'part.step-finish') return createStepFinishEvent(msg, part, obj, type, idx)
    if (type === 'step_start' || type === 'part.step-start') return { key: String((msg as any)?.id || `${type}-${idx}`), role: 'system', label: 'System', text: 'Step started' }
    if (typeof content === 'string' && content) return { key: String(msg.id || `${role}-${idx}`), role, label: role === 'user' ? 'You' : role === 'assistant' ? 'Agent' : 'System', model, createdAt, text: content }
    if (type) return { key: String((msg as any)?.id || `${type}-${idx}`), role: 'system', label: 'System', text: `Event: ${type}`, rawDetails: safeJsonStringify(obj) }
    return null
}
