import { useState, useEffect, useRef } from 'react'
import { API_URL, Codebase, Session } from '../types'

interface Props {
    selectedCodebase: string
    selectedCodebaseMeta: Codebase | null
    selectedSession: Session | null
    onIdle: () => void
}

const BACKOFF_MIN = 1000
const BACKOFF_MAX = 30000

export function useSessionStream({ selectedCodebase, selectedCodebaseMeta, selectedSession, onIdle }: Props) {
    const [streamConnected, setStreamConnected] = useState(false)
    const [streamStatus, setStreamStatus] = useState('')
    const [liveDraft, setLiveDraft] = useState('')
    const esRef = useRef<EventSource | null>(null)
    const attempts = useRef(0)
    const timeout = useRef<ReturnType<typeof setTimeout> | null>(null)

    useEffect(() => {
        esRef.current?.close()
        if (timeout.current) clearTimeout(timeout.current)
        setStreamConnected(false); setStreamStatus(''); setLiveDraft('')
        attempts.current = 0
        if (!selectedCodebase || !selectedSession || !selectedCodebaseMeta) return
        if (!selectedCodebaseMeta.worker_id && !selectedCodebaseMeta.opencode_port) { setStreamStatus('Unavailable'); return }

        const connect = () => {
            const es = new EventSource(`${API_URL}/v1/opencode/codebases/${selectedCodebase}/events`)
            esRef.current = es

            es.onopen = () => {
                attempts.current = 0
                setStreamConnected(true)
                setStreamStatus('Live')
            }

            es.onerror = (err) => {
                console.error('EventSource error:', err)
                setStreamConnected(false)
                setStreamStatus('Disconnected')
                es.close()
                const delay = Math.min(BACKOFF_MIN * Math.pow(2, attempts.current), BACKOFF_MAX)
                attempts.current++
                timeout.current = setTimeout(connect, delay)
            }

            const handler = (e: MessageEvent) => {
                try {
                    const d = JSON.parse(e.data)
                    if (d?.session_id && selectedSession?.id && d.session_id !== selectedSession.id) return
                    if (d?.message || d?.status) setStreamStatus((d.message || d.status).toString())
                    if (d?.status === 'idle' || d?.event_type === 'idle') { onIdle(); setLiveDraft('') }
                    const t = d?.event_type || d?.type || ''
                    if (t === 'part.text' || t === 'text') setLiveDraft((p) => p + (d?.delta || d?.content || d?.text || ''))
                } catch (err) {
                    console.error('Failed to parse EventSource message:', err)
                }
            }
            ;['status', 'idle', 'message', 'part.text'].forEach((e) => es.addEventListener(e, handler))
        }

        connect()

        return () => {
            esRef.current?.close()
            if (timeout.current) clearTimeout(timeout.current)
        }
    }, [selectedCodebase, selectedCodebaseMeta, selectedSession, onIdle])

    return { streamConnected, streamStatus, liveDraft, resetStream: () => { setStreamConnected(false); setStreamStatus(''); setLiveDraft('') } }
}
