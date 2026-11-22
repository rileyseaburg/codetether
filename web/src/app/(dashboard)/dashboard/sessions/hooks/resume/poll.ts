import { API_URL } from '../../types'
import type { ApiAuth, ResumePayload, ResumeRun } from './contracts'
import { authHeaders } from './request'
import { executionError, failureStatus, taskStatus } from './outcome'
import { wait } from './wait'

export async function poll(taskId: string, auth: ApiAuth, run: ResumeRun): Promise<void> {
    const headers = authHeaders(auth)
    const timer = setTimeout(() => run.controller.abort('poll-timeout'), 180000)
    try {
        while (run.isCurrent() && !run.controller.signal.aborted) {
            await wait(2000, run.controller.signal)
            let response: Response
            try {
                response = await fetch(API_URL + '/v1/agent/tasks/' + encodeURIComponent(taskId), { headers, signal: run.controller.signal })
            } catch (error) {
                if (run.controller.signal.aborted) throw error
                run.update({ actionStatus: 'Task status unavailable; retrying observation, not the prompt.' })
                continue
            }
            if (!run.isCurrent() || run.controller.signal.aborted) return
            if ([401, 403, 404].includes(response.status)) throw new Error('Cannot observe task (HTTP ' + response.status + '); it may still be running.')
            if (!response.ok) continue
            const data: ResumePayload = await response.json()
            if (!run.isCurrent() || run.controller.signal.aborted) return
            const error = executionError(data)
            if (error) {
                run.update({ taskStatus: failureStatus(data) })
                throw new Error(error)
            }
            const status = taskStatus(data.status)
            run.update({ taskStatus: status })
            if (status === 'completed') return
            run.update({ actionStatus: status === 'pending' || status === 'queued' ? 'Waiting for worker...' : 'Agent is working...' })
        }
    } finally {
        clearTimeout(timer)
    }
}