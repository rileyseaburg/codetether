import { useState, useEffect } from 'react'

const MODEL_STORAGE_KEY = 'codetether.model.default'

function getStoredModel(): string {
    if (typeof window === 'undefined') return ''
    try {
        return window.localStorage.getItem(MODEL_STORAGE_KEY) ?? ''
    } catch {
        return ''
    }
}

export function useModelStorage() {
    const [selectedModel, setSelectedModel] = useState(getStoredModel)

    useEffect(() => {
        try {
            if (selectedModel) {
                window.localStorage.setItem(MODEL_STORAGE_KEY, selectedModel)
            } else {
                window.localStorage.removeItem(MODEL_STORAGE_KEY)
            }
        } catch {
            // ignore
        }
    }, [selectedModel])

    return { selectedModel, setSelectedModel }
}
