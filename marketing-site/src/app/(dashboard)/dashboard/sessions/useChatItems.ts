import { useMemo } from 'react'
import type { SessionMessageWithParts, ChatItem } from './types'
import { normalizeMessage } from './normalizeMessage'

export function useChatItems(sessionMessages: SessionMessageWithParts[]): ChatItem[] {
    return useMemo(() => {
        const raw = sessionMessages || []
        const items: ChatItem[] = []

        for (let i = 0; i < raw.length; i++) {
            const normalized = normalizeMessage(raw[i], i)
            if (normalized) items.push(normalized)
        }

        return mergeAdjacentAssistantChunks(items)
    }, [sessionMessages])
}

function mergeAdjacentAssistantChunks(items: ChatItem[]): ChatItem[] {
    const merged: ChatItem[] = []

    for (const item of items) {
        const prev = merged[merged.length - 1]
        const canMerge =
            prev &&
            item.role === 'assistant' &&
            prev.role === 'assistant' &&
            !item.tools?.length &&
            !prev.tools?.length &&
            !item.usage &&
            !prev.usage &&
            item.model === prev.model &&
            (item.text || item.reasoning)

        if (canMerge) {
            merged[merged.length - 1] = {
                ...prev,
                text: prev.text + (item.text || ''),
                reasoning: (prev.reasoning || '') + (item.reasoning || ''),
            }
        } else {
            merged.push(item)
        }
    }

    return merged
}
