const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

export async function searchWorkersModels(query: string): Promise<string[]> {
    if (!query?.trim()) return []

    try {
        const url = `${API_URL}/v1/agent/workers?search=${encodeURIComponent(query)}`
        const response = await fetch(url)
        if (!response.ok) return []

        const workers = await response.json()
        const allModels: string[] = []

        for (const worker of workers || []) {
            const rawModels = (worker.models as Array<string | Record<string, unknown>>) || []
            for (const m of rawModels) {
                let modelStr: string | null = null
                if (typeof m === 'string') {
                    modelStr = m
                } else if (m && typeof m === 'object') {
                    const obj = m as any
                    if (obj.providerID && obj.modelID) modelStr = `${obj.providerID}:${obj.modelID}`
                    else if (obj.provider && obj.name && obj.name !== obj.provider) modelStr = `${obj.provider}:${obj.name}`
                    else if (obj.provider && obj.id && obj.id !== obj.provider) modelStr = `${obj.provider}:${obj.id}`
                    else if (obj.name) modelStr = obj.name
                    else if (obj.id) modelStr = obj.id
                }
                if (modelStr) allModels.push(modelStr)
            }
        }

        return allModels.slice(0, 50)
    } catch {
        return []
    }
}

export interface Worker {
    models: Array<string | Record<string, unknown>>
}

export async function fetchWorkers(): Promise<Worker[]> {
    const response = await fetch(`${API_URL}/v1/agent/workers`)
    if (!response.ok) throw new Error('Failed to fetch workers')
    const workers = await response.json()
    return workers?.filter((w: Worker) => w?.models?.length > 0) ?? []
}
