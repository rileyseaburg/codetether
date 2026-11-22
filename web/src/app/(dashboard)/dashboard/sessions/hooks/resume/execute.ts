import type { Session } from '../../types'
import type { ApiAuth, ResumeProps, ResumeRun } from './contracts'
import { submit } from './request'
import { activeSession, directSuccess, executionError, failureStatus } from './outcome'
import { poll } from './poll'
import { refresh } from './refresh'

export async function executeResume(props: ResumeProps, session: Session, message: string | null, auth: ApiAuth, run: ResumeRun): Promise<void> {
    let executed = false
    try {
        const data = await submit({ props, session, message, auth, run })
        if (!run.isCurrent() || run.controller.signal.aborted) return
        const error = executionError(data)
        if (error) {
            run.update({ taskStatus: failureStatus(data) })
            throw new Error(error)
        }
        const sessionId = activeSession(data, session.id)
        if (data.task_id) {
            if (typeof data.task_id !== 'string' || !data.task_id.trim()) throw new Error('Invalid task identity.')
            run.update({ activeTaskId: data.task_id, taskStatus: 'pending', actionStatus: 'Message queued - waiting for worker...' })
            await poll(data.task_id, auth, run)
        } else if (!directSuccess(data)) {
            throw new Error('No confirmed execution result or task identity returned; execution outcome is unknown. Check session history before resending.')
        }
        if (!run.isCurrent() || run.controller.signal.aborted) return
        executed = true
        await refresh(props, sessionId, run)
        run.update({ actionStatus: message ? 'Response received!' : 'Session resumed: ' + sessionId.slice(0, 16) + '...' })
    } catch (error) {
        if (!run.isCurrent()) return
        const reason = run.controller.signal.reason
        const detail = reason === 'submission-timeout'
            ? 'Request timed out after 30s; execution outcome is unknown. Check session history before resending.'
            : reason === 'poll-timeout' ? 'Task observation timed out; the task may still be running.'
            : error instanceof TypeError ? 'Network response lost; execution outcome is unknown. Check session history before resending.'
            : error instanceof Error ? error.message : 'Unknown error.'
        run.update({ actionStatus: executed ? 'Response received, but refresh failed: ' + detail : 'Failed to resume: ' + detail })
    }
}
