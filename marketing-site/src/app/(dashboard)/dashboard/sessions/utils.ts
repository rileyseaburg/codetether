import type { TokenUsage } from './types'

export function formatCost(cost?: number): string {
    if (typeof cost !== 'number' || !Number.isFinite(cost)) return ''
    if (cost === 0) return '$0'
    if (cost < 0.01) return `$${cost.toFixed(4)}`
    if (cost < 1) return `$${cost.toFixed(3)}`
    return `$${cost.toFixed(2)}`
}

export function coerceTokenUsage(input: unknown): TokenUsage | undefined {
    if (!input || typeof input !== 'object') return undefined
    const o = input as Record<string, unknown>
    const c = o.cache && typeof o.cache === 'object' ? (o.cache as Record<string, unknown>) : undefined
    const n = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : undefined)
    const t: TokenUsage = { input: n(o.input), output: n(o.output), reasoning: n(o.reasoning), cache: c ? { read: n(c.read), write: n(c.write) } : undefined }
    return t.input !== undefined || t.output !== undefined || t.reasoning !== undefined || t.cache?.read !== undefined || t.cache?.write !== undefined ? t : undefined
}

export function formatTokens(tokens?: TokenUsage): { summary: string; detail?: string } | null {
    if (!tokens) return null
    const i = tokens.input || 0, o = tokens.output || 0, r = tokens.reasoning || 0, cr = tokens.cache?.read || 0, cw = tokens.cache?.write || 0
    const pieces: string[] = []
    if (i) pieces.push(`${i} in`)
    if (o) pieces.push(`${o} out`)
    if (r) pieces.push(`${r} reasoning`)
    if (cr || cw) pieces.push(`cache ${cr}r/${cw}w`)
    return { summary: `${i + o + r} tokens`, detail: pieces.length ? pieces.join(' * ') : undefined }
}

export function safeJsonStringify(value: unknown, maxLen = 8000): string {
    try { const t = JSON.stringify(value, null, 2); return t.length > maxLen ? t.slice(0, maxLen) + '\n...' : t } catch { return String(value) }
}

export function formatDate(dateStr: string): string {
    if (!dateStr) return ''
    const d = new Date(dateStr), diff = Date.now() - d.getTime()
    if (diff < 60000) return 'Just now'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    return d.toLocaleDateString()
}
