import type { ChatItem } from '../types'
import { coerceTokenUsage, formatTokens, formatCost, safeJsonStringify } from '../utils'

export function getText(obj: any): string {
    if (!obj) return ''
    if (typeof obj === 'string') return obj
    if (typeof obj.text === 'string') return obj.text
    if (typeof obj.delta === 'string') return obj.delta
    if (typeof obj.content === 'string') return obj.content
    if (Array.isArray(obj.content)) return obj.content.map((c: any) => c?.text || (typeof c === 'string' ? c : '')).join('')
    return ''
}

export function createTextEvent(msg: any, part: any, obj: any, type: string, model: string | undefined, createdAt: string | undefined, idx: number): ChatItem {
    return { key: String(msg?.id || `${type}-${idx}`), role: 'assistant', label: 'Agent', model, createdAt, text: getText(part) || getText(obj) || '' }
}

export function createReasoningEvent(msg: any, part: any, obj: any, type: string, model: string | undefined, createdAt: string | undefined, idx: number): ChatItem {
    return { key: String(msg?.id || `${type}-${idx}`), role: 'assistant', label: 'Agent', model, createdAt, text: '', reasoning: getText(part) || getText(obj) || undefined }
}

export function createStepFinishEvent(msg: any, part: any, obj: any, type: string, idx: number): ChatItem {
    const t = coerceTokenUsage(part?.tokens || obj?.tokens)
    const c = typeof part?.cost === 'number' ? part.cost : obj?.cost
    const sum = formatTokens(t)?.summary
    return { key: String(msg?.id || `${type}-${idx}`), role: 'system', label: 'System', text: `Step finished${sum ? ` * ${sum}` : ''}${typeof c === 'number' ? ` * ${formatCost(c)}` : ''}`, usage: c || t ? { cost: c, tokens: t } : undefined, rawDetails: safeJsonStringify(obj) }
}
