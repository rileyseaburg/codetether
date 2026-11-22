import { NextResponse } from 'next/server'

const MODELS_DEV_API = 'https://models.dev/api.json'
const CACHE_TTL_SECONDS = 3600 // 1 hour

let cached: { data: Record<string, ProviderData>; fetchedAt: number } | null = null

interface ModelCost {
    input: number
    output: number
}

interface ModelData {
    id: string
    name: string
    cost?: ModelCost
}

interface ProviderData {
    id: string
    name: string
    models: Record<string, ModelData>
}

export async function GET() {
    const now = Date.now()

    if (cached && now - cached.fetchedAt < CACHE_TTL_SECONDS * 1000) {
        return NextResponse.json(extractPricing(cached.data))
    }

    try {
        const res = await fetch(MODELS_DEV_API, {
            next: { revalidate: CACHE_TTL_SECONDS },
        })

        if (!res.ok) {
            return NextResponse.json({ error: 'Failed to fetch model data' }, { status: 502 })
        }

        const data = (await res.json()) as Record<string, ProviderData>
        cached = { data, fetchedAt: now }

        return NextResponse.json(extractPricing(data))
    } catch {
        return NextResponse.json({ error: 'Failed to fetch model data' }, { status: 502 })
    }
}

function extractPricing(data: Record<string, ProviderData>) {
    const pricing: Record<string, { provider: string; model: string; name: string; inputCostPerM: number; outputCostPerM: number }> = {}

    for (const [providerId, provider] of Object.entries(data)) {
        if (!provider.models) continue
        for (const [modelId, model] of Object.entries(provider.models)) {
            if (model.cost) {
                const key = `${providerId}:${modelId}`
                pricing[key] = {
                    provider: provider.name,
                    model: modelId,
                    name: model.name,
                    inputCostPerM: model.cost.input,
                    outputCostPerM: model.cost.output,
                }
            }
        }
    }

    return { pricing, fetchedAt: new Date().toISOString() }
}
