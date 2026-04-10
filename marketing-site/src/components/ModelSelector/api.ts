const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

export async function searchWorkersModels(query: string): Promise<string[]> {
    if (!query?.trim()) return []

    try {
        // Use dedicated models endpoint for aggregated, deduplicated results
        const url = `${API_URL}/v1/agent/models`
        const response = await fetch(url)
        if (!response.ok) return []

        const data = await response.json()
        const models: { id?: string }[] = data?.models || []
        const queryLower = query.toLowerCase()

        return models
            .map(m => m.id)
            .filter((id): id is string => Boolean(id))
            .filter(id => id.toLowerCase().includes(queryLower))
            .slice(0, 50)
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
