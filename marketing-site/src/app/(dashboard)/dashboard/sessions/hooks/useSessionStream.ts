import { useState, useEffect, useRef } from 'react'
import { API_URL, Codebase, Session } from '../types'

interface Props {
    selectedCodebase: string
    selectedCodebaseMeta: Codebase | null
    selectedSession: Session | null
    onIdle: () => void
}

export function useSessionStream({ selectedCodebase, selectedCodebaseMeta, selectedSession, onIdle }: Props) {
    const [streamConnected, setStreamConnected] = useState(false)
    const [streamStatus, setStreamStatus] = useState('')
    const [liveDraft, setLiveDraft] = useState('')
    const esRef = useRef<EventSource | null>(null)

    useEffect(() => {
        esRef.current?.close()
        setStreamConnected(false); setStreamStatus(''); setLiveDraft('')
        if (!selectedCodebase || !selectedSession || !selectedCodebaseMeta) return
        if (!selectedCodebaseMeta.worker_id && !selectedCodebaseMeta.opencode_port) { setStreamStatus('Unavailable'); return }

        const es = new EventSource(`${API_URL}/v1/opencode/codebases/${selectedCodebase}/events`)
        esRef.current = es
        es.onopen = () => { setStreamConnected(true); setStreamStatus('Live') }
        es.onerror = () => { setStreamConnected(false); setStreamStatus('Disconnected') }

        const handler = (e: MessageEvent) => {
            try {
                const d = JSON.parse(e.data)
                if (d?.session_id && selectedSession?.id && d.session_id !== selectedSession.id) return
                if (d?.message || d?.status) setStreamStatus((d.message || d.status).toString())
                if (d?.status === 'idle' || d?.event_type === 'idle') { onIdle(); setLiveDraft('') }
                const t = d?.event_type || d?.type || ''
                if (t === 'part.text' || t === 'text') setLiveDraft((p) => p + (d?.delta || d?.content || d?.text || ''))
            } catch {}
        }
        ;['status', 'idle', 'message', 'part.text'].forEach((e) => es.addEventListener(e, handler))
        return () => es.close()
    }, [selectedCodebase, selectedCodebaseMeta, selectedSession, onIdle])

    return { streamConnected, streamStatus, liveDraft, resetStream: () => { setStreamConnected(false); setStreamStatus(''); setLiveDraft('') } }
}
