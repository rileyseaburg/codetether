import type { getApiAuth } from '@/lib/auth-token'
import type { Session } from '../../types'

export type ApiAuth = ReturnType<typeof getApiAuth>
export type TaskStatus = 'pending' | 'queued' | 'running' | 'working' | 'completed' | 'failed' | 'cancelled' | 'interrupted'
export interface ResumeProps {
    selectedWorkspace: string
    selectedMode: string
    selectedModel: string
    onSessionUpdate: (sessionId: string) => void
    loadSessions: (workspaceId: string) => Promise<void>
    loadSessionMessages: (sessionId: string, force?: boolean) => Promise<void>
}
export interface ResumeState {
    loading: boolean
    actionStatus: string | null
    taskStatus: TaskStatus | null
    activeTaskId: string | null
}
export interface ResumeRun {
    controller: AbortController
    isCurrent: () => boolean
    update: (patch: Partial<ResumeState>) => void
}
export interface ResumePayload {
    status?: string
    success?: boolean
    error?: unknown
    detail?: unknown
    result?: unknown
    task_id?: string
    active_session_id?: string
    new_session_id?: string
    session_id?: string
}
export type Submission = {
    props: ResumeProps
    session: Session
    message: string | null
    auth: ApiAuth
    run: ResumeRun
}
