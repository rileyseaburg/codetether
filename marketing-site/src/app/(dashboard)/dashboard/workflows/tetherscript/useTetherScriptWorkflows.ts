'use client'

import { useCallback, useEffect, useState } from 'react'
import { useTenantApi } from '@/hooks/useTenantApi'
import { DEFAULT_REPOS } from './utils'
import type { TetherScriptWorkflowResponse } from './types'

export function useTetherScriptWorkflows() {
  const { tenantFetch, isLoading: tenantLoading } = useTenantApi()
  const [data, setData] = useState<TetherScriptWorkflowResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [repos, setRepos] = useState(DEFAULT_REPOS)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    const query = new URLSearchParams({ repos, limit: '250' })
    const res = await tenantFetch<TetherScriptWorkflowResponse>(
      `/v1/agent/workflows/tetherscript?${query.toString()}`,
    )
    if (res.error) setError(res.error)
    else if (res.data) setData(res.data)
    setLoading(false)
  }, [repos, tenantFetch])

  useEffect(() => {
    if (tenantLoading) return
    const timer = window.setTimeout(() => void load(), 0)
    return () => window.clearTimeout(timer)
  }, [tenantLoading, load])

  useEffect(() => {
    if (!autoRefresh) return
    const timer = window.setInterval(() => void load(), 15000)
    return () => window.clearInterval(timer)
  }, [autoRefresh, load])

  return {
    data, error, loading, repos, setRepos, load, autoRefresh, setAutoRefresh,
  }
}
