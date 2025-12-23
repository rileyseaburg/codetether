import { useMemo } from 'react'
import type { ChatItem } from './types'

const DEFAULT_MODELS = [
    'google/gemini-3-flash-preview',
    'anthropic/claude-sonnet-4-20250514',
    'anthropic/claude-3-5-sonnet-latest',
    'azure-anthropic/claude-opus-4-5',
    'openai/gpt-4.1',
    'openai/gpt-4o',
    'glm/glm-4.6',
    'glm/glm-4.5',
    'z-ai/coding-plain-v1',
    'z-ai/coding-plain-v2',
]

export function useSuggestedModels(chatItems: ChatItem[]): string[] {
    return useMemo(() => {
        const models = new Set<string>()

        for (const m of chatItems) {
            if (m.model) models.add(String(m.model))
        }

        DEFAULT_MODELS.forEach((m) => models.add(m))

        return Array.from(models).sort()
    }, [chatItems])
}
