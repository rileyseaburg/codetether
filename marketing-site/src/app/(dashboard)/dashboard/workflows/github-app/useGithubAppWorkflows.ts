'use client'

import { useCallback, useEffect, useState } from 'react'
import { useTenantApi } from '@/hooks/useTenantApi'

import type { GithubAppWorkflowResponse } from './types'

export function useGithubAppWorkflows() {
  const { tenantFetch, isLoading: tenantLoading } = useTenantApi()
  const [data, setData] = useState<GithubAppWorkflowResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [repos, setRepos] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    const query = new URLSearchParams({ repos, limit: '250' })
    const res = await tenantFetch<GithubAppWorkflowResponse>(
      `/v1/agent/workflows/github-app?${query.toString()}`,
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
