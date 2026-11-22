export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue }

export type ParsedJsonPayload =
    | { kind: 'single'; value: JsonValue }
    | { kind: 'lines'; value: JsonValue[] }

export type JsonExpandContextValue = { action: 'expand' | 'collapse' | null; version: number }

export function safeParseJson(text: string): { ok: true; value: JsonValue } | { ok: false } {
    try {
        return { ok: true, value: JSON.parse(text) as JsonValue }
    } catch {
        return { ok: false }
    }
}

export function parseJsonPayload(text: string): ParsedJsonPayload | null {
    const trimmed = text.trim()
    if (!trimmed) return null

    const isLikelyJson = (value: string) => value.startsWith('{') || value.startsWith('[')

    if (isLikelyJson(trimmed)) {
        const parsed = safeParseJson(trimmed)
        if (parsed.ok) {
            return { kind: 'single', value: parsed.value }
        }
    }

    const lines = trimmed.split('\n').map((line) => line.trim()).filter(Boolean)
    if (lines.length > 1 && lines.every(isLikelyJson)) {
        const parsedLines = lines.map((line) => safeParseJson(line))
        if (parsedLines.every((line) => line.ok)) {
            return {
                kind: 'lines',
                value: parsedLines.map((line) => (line as { ok: true; value: JsonValue }).value),
            }
        }
    }

    return null
}

export function formatJsonValue(value: JsonValue) {
    if (typeof value === 'string') return `"${value}"`
    if (typeof value === 'number') return String(value)
    if (typeof value === 'boolean') return value ? 'true' : 'false'
    if (value === null) return 'null'
    return ''
}

export function getJsonSummary(value: JsonValue) {
    if (Array.isArray(value)) return `${value.length} item${value.length === 1 ? '' : 's'}`
    if (value && typeof value === 'object') return `${Object.keys(value).length} key${Object.keys(value).length === 1 ? '' : 's'}`
    return typeof value
}
