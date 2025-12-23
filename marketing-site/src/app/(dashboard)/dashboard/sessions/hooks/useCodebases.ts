import { useState, useEffect, useCallback } from 'react'
import { API_URL, Codebase } from '../types'

export function useCodebases() {
    const [codebases, setCodebases] = useState<Codebase[]>([])

    const loadCodebases = useCallback(async () => {
        try {
            const response = await fetch(`${API_URL}/v1/opencode/codebases/list`)
            if (response.ok) {
                const data = await response.json()
                const items = Array.isArray(data) ? data : (data?.codebases ?? [])
                setCodebases(
                    (items as any[])
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
