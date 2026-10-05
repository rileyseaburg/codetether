import { useCallback, useEffect, useRef, useState } from 'react'
import { useSession } from 'next-auth/react'
import { useApiAuth } from '@/hooks/useApiAuth'
import { Session } from '../types'
import { ResumeProps, ResumeRun } from './resume/contracts'
import { initialState } from './resume/state'
import { executeResume } from './resume/execute'

export function useSessionResume(props: ResumeProps) {
    const { data: authSession } = useSession()
    const auth = useApiAuth(authSession)
    const scope = JSON.stringify([props.selectedWorkspace, auth.token, auth.tenantId])
    const scopeRef = useRef(scope)
    scopeRef.current = scope
    const current = useRef<ResumeRun | null>(null)
    const [state, setState] = useState(initialState)
    const stop = useCallback(() => {
        const run = current.current
        current.current = null
        run?.controller.abort('stopped')
    }, [])
    useEffect(() => {
        setState(initialState)
        return stop
    }, [scope, stop])
    const resumeSession = useCallback(async (session: Session, message: string | null) => {
        if (current.current) return
        const run: ResumeRun = {
            controller: new AbortController(),
            isCurrent: () => current.current === run && scopeRef.current === scope,
            update: patch => {
                if (run.isCurrent()) setState(previous => ({ ...previous, ...patch }))
            },
        }
        current.current = run
        run.update({ ...initialState, loading: true })
        try {
            await executeResume(props, session, message, auth, run)
        } finally {
            if (run.isCurrent()) {
                run.update({ loading: false })
                current.current = null
            }
        }
    }, [props, auth.token, auth.tenantId, scope])
    const cancelPolling = useCallback(() => {
        stop()
        setState(previous => ({ ...previous, loading: false, actionStatus: 'Stopped watching; the task may still be running.' }))
    }, [stop])
    return { ...state, resumeSession, cancelPolling }
}