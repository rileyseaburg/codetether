import { useState, useEffect } from 'react'

const MODEL_STORAGE_KEY = 'codetether.model.default'

export function useModelStorage() {
    const [selectedModel, setSelectedModel] = useState('')

    useEffect(() => {
        try {
            const saved = window.localStorage.getItem(MODEL_STORAGE_KEY)
            if (saved) setSelectedModel(saved)
        } catch {
            // ignore
        }
    }, [])

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
