import { API_URL } from '../../types'
import type { ApiAuth, ResumePayload, Submission } from './contracts'

export function authHeaders(auth: ApiAuth): Record<string, string> {
    if (!auth.token) throw new Error('Sign in before resuming a session.')
    return {
        Authorization: `Bearer ${auth.token}`,
        ...(auth.tenantId ? { 'X-Tenant-ID': auth.tenantId } : {}),
    }
}
export async function submit({ props, session, message, auth, run }: Submission): Promise<ResumePayload> {
    const headers = authHeaders(auth)
    const timer = setTimeout(() => run.controller.abort('submission-timeout'), 30000)
    try {
        // A lost response is not evidence that the prompt was not executed. Never replay this POST.
        const response = await fetch(
            API_URL + '/v1/agent/workspaces/' + encodeURIComponent(props.selectedWorkspace) + '/sessions/' + encodeURIComponent(session.id) + '/resume',
            {
                method: 'POST',
                headers: { ...headers, 'Content-Type': 'application/json' },
                signal: run.controller.signal,
                body: JSON.stringify({ message: message || undefined, mode: props.selectedMode, model: props.selectedModel || undefined }),
            },
        )
        const data = await response.json()
        if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : 'Resume request failed (HTTP ' + response.status + ').')
        if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Invalid resume response; execution outcome is unknown.')
        return data
    } finally {
        clearTimeout(timer)
    }
}
