import type { TokenUsage, SessionMessage } from '../types'
import { coerceTokenUsage } from '../utils'

export function extractUsage(msg: SessionMessage, stepFinishes: Array<{ cost?: number; tokens?: TokenUsage }>) {
    const stepCostAny = stepFinishes.some((p) => typeof p.cost === 'number')
    const stepCostSum = stepFinishes.reduce((acc, p) => acc + (p.cost || 0), 0)

    const stepTokensSum: TokenUsage | undefined = stepFinishes.length
        ? stepFinishes.reduce<TokenUsage>((acc, p) => {
            const t = coerceTokenUsage(p.tokens)
            if (!t) return acc
            acc.input = (acc.input || 0) + (t.input || 0)
            acc.output = (acc.output || 0) + (t.output || 0)
            acc.reasoning = (acc.reasoning || 0) + (t.reasoning || 0)
            if (t.cache) {
                acc.cache = acc.cache || {}
                acc.cache.read = (acc.cache.read || 0) + (t.cache.read || 0)
                acc.cache.write = (acc.cache.write || 0) + (t.cache.write || 0)
            }
            return acc
        }, {})
        : undefined

    const cost =
        (typeof msg.cost === 'number' ? msg.cost : undefined) ??
        (stepCostAny ? stepCostSum : undefined)

    const tokens =
        coerceTokenUsage(msg.tokens) ??
        stepTokensSum

    return { cost, tokens }
}
