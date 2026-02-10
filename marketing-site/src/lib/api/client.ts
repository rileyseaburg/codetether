const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

// Helper for JSON fetch
async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
    const res = await fetch(url, options)
    if (!res.ok) {
        const text = await res.text()
        throw new Error(`API Error ${res.status}: ${text}`)
    }
    return res.json()
}

// Types
export interface Worker {
    worker_id: string
    name: string
    hostname?: string
    status: string
    last_seen: string
    registered_at: string
    codebases: string[]
    models: Array<{ providerID?: string; modelID?: string } | string>
    capabilities: string[]
}

export interface Codebase {
    id: string
    name: string
    path: string
    worker_id?: string
    status: string
}

export interface Task {
    id: string
    codebase_id?: string
    title: string
    prompt: string
    agent_type: string
    status: string
    priority: number
    result?: string
    error?: string
    metadata?: Record<string, unknown>
    created_at: string
    started_at?: string
    completed_at?: string
}

export interface PRDChatRequest {
    message: string
    conversation_id?: string
    history?: Array<{ role: string; content: string }>
    model?: string
    worker_id?: string
    codebase_id?: string
}

export interface PRDChatResponse {
    task_id: string
    status: string
}

// Type-safe API client
export const api = {
    // Workers
    workers: {
        list: () => fetchJson<Worker[]>(`${API_URL}/v1/opencode/workers`),
    },
    
    // Codebases
    codebases: {
        list: () => fetchJson<Codebase[]>(`${API_URL}/v1/opencode/codebases/list`),
    },
    
    // Tasks
    tasks: {
        get: (id: string) => fetchJson<Task>(`${API_URL}/v1/opencode/tasks/${id}`),
        
        list: (params?: { status?: string; limit?: number }) => {
            const searchParams = new URLSearchParams()
            if (params?.status) searchParams.set('status', params.status)
            if (params?.limit) searchParams.set('limit', String(params.limit))
            const query = searchParams.toString()
            return fetchJson<Task[]>(`${API_URL}/v1/opencode/tasks${query ? '?' + query : ''}`)
        },
        
        create: (data: {
            title: string
            prompt: string
            codebase_id?: string
            agent_type?: string
            priority?: number
            model?: string
            metadata?: Record<string, unknown>
        }) => fetchJson<Task>(`${API_URL}/v1/opencode/tasks`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        }),
    },
    
    // Ralph / PRD Chat
    ralph: {
        chat: (data: PRDChatRequest) => fetchJson<PRDChatResponse>(`${API_URL}/v1/ralph/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        }),
        
        runs: {
            create: (data: {
                prd: {
                    project: string
                    branchName: string
                    description: string
                    userStories: Array<{
                        id: string
                        title: string
                        description: string
                        acceptanceCriteria: string[]
                        priority: number
                    }>
                }
                codebase_id?: string
                model?: string
                max_iterations?: number
                run_mode?: 'sequential' | 'parallel'
                max_parallel?: number
            }) => fetchJson<{ id: string }>(`${API_URL}/v1/ralph/runs`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            }),
            
            get: (id: string) => fetchJson<{ id: string; status: string }>(`${API_URL}/v1/ralph/runs/${id}`),
            
            stream: (id: string) => new EventSource(`${API_URL}/v1/ralph/runs/${id}/stream`),
        },
    },
}

export type Api = typeof api
