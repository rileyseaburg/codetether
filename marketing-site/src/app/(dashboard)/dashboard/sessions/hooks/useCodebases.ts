import { useState, useEffect, useCallback } from 'react'
import { API_URL, Codebase } from '../types'
import { listCodebasesV1OpencodeCodebasesListGet } from '@/lib/api'

export function useCodebases() {
    const [codebases, setCodebases] = useState<Codebase[]>([])

    const loadCodebases = useCallback(async () => {
        try {
            const result = await listCodebasesV1OpencodeCodebasesListGet()
            if (result.data) {
                const items: any[] = Array.isArray(result.data) ? result.data : (result.data as any)?.codebases ?? []
                setCodebases(
                    items
                        .map((cb) => ({
                            id: String(cb?.id ?? ''),
                            name: String(cb?.name ?? cb?.id ?? ''),
                            path: String(cb?.path ?? ''),
                            status: String(cb?.status ?? 'unknown'),
                            worker_id: typeof cb?.worker_id === 'string' ? cb.worker_id : null,
                            opencode_port:
                                typeof cb?.opencode_port === 'number'
                                    ? cb.opencode_port
                                    : cb?.opencode_port
                                        ? Number(cb.opencode_port)
                                        : null,
                        }))
                        .filter((cb) => cb.id)
                )
            }
        } catch (error) {
            console.error('Failed to load codebases:', error)
        }
    }, [])

    useEffect(() => {
        loadCodebases()
    }, [loadCodebases])

    return { codebases, loadCodebases }
}
