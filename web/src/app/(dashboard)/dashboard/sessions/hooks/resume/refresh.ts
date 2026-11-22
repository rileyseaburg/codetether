import type { ResumeProps, ResumeRun } from './contracts'

export async function refresh(props: ResumeProps, sessionId: string, run: ResumeRun): Promise<void> {
    if (!run.isCurrent() || run.controller.signal.aborted) return
    await props.loadSessions(props.selectedWorkspace)
    if (!run.isCurrent() || run.controller.signal.aborted) return
    props.onSessionUpdate(sessionId)
    await props.loadSessionMessages(sessionId, true)
}
