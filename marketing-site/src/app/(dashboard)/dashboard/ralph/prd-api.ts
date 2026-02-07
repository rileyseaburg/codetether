import { createGlobalTaskV1AgentTasksPost, getTaskV1AgentTasksTaskIdGet } from '@/lib/api'

export interface TaskResponse {
    id: string
    task_id?: string
    status: string
    result?: string
}

export async function createTask(prompt: string, conversationContext: string, codebaseId?: string): Promise<TaskResponse> {
    const result = await createGlobalTaskV1AgentTasksPost({
        body: {
            title: `PRD Builder: ${prompt.substring(0, 50)}...`,
            prompt: conversationContext,
            agent_type: 'general',
            codebase_id: codebaseId || undefined,
        },
    })

    if (!result.data) {
        throw new Error('Failed to create task: No data returned')
    }

    const data = result.data as any

    return {
        id: data.id,
        task_id: data.task_id,
        status: data.status,
        result: data.result,
    }
}

export async function getTask(taskId: string): Promise<TaskResponse> {
    const result = await getTaskV1AgentTasksTaskIdGet({
        path: { task_id: taskId },
    })

    if (!result.data) {
        throw new Error('Failed to get task: No data returned')
    }

    const data = result.data as any

    return {
        id: data.id,
        task_id: data.task_id,
        status: data.status,
        result: data.result,
    }
}

export async function pollTask(taskId: string): Promise<TaskResponse> {
    let task = await getTask(taskId)
    while (task.status === 'working') {
        await new Promise(r => setTimeout(r, 1000))
        task = await getTask(taskId)
    }
    return task
}

export function parseOpenCodeResult(result: string): string {
    if (!result) return 'No response'
    if (!result.trim().startsWith('{')) return result
    const textParts: string[] = []
    for (const line of result.split('\n').filter(l => l.trim())) {
        try {
            const parsed = JSON.parse(line)
            if (parsed.text) textParts.push(parsed.text)
            if (parsed.content) textParts.push(parsed.content)
        } catch {
            if (!line.trim().startsWith('{')) textParts.push(line)
        }
    }
    return textParts.length ? textParts.join('') : result
}

export interface GeneratedPRD {
    project: string
    branchName: string
    description: string
    userStories: Array<{ id: string, title: string, description: string, acceptanceCriteria: string[], priority: number }>
}

export function extractPRDFromResponse(response: string): GeneratedPRD | null {
    const jsonMatch = response.match(/```json\s*([\s\S]*?)\s*```/)
    if (jsonMatch) {
        try {
            const parsed = JSON.parse(jsonMatch[1])
            if (parsed.type === 'prd') return parsed as GeneratedPRD
        } catch {}
    }
    return null
}
