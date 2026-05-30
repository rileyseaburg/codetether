'use client'

import { useCallback, useEffect, useState } from 'react'
import { useTenantApi } from '@/hooks/useTenantApi'

import type { GithubAppWorkflowResponse } from './types'

const emptyWorkflowResponse = (): GithubAppWorkflowResponse => ({
  generated_at: new Date().toISOString(),
  totals: {},
  route_states: {},
  failure_classes: {},
  workflows: [],
  tasks: [],
  runs: [],
})

function normalizeWorkflowResponse(value: unknown): GithubAppWorkflowResponse {
  if (!value || Array.isArray(value) || typeof value !== 'object') {
    return emptyWorkflowResponse()
  }

  const response = value as Partial<GithubAppWorkflowResponse>
  return {
    generated_at: response.generated_at || new Date().toISOString(),
    totals: response.totals || {},
    route_states: response.route_states || {},
    failure_classes: response.failure_classes || {},
    workflows: Array.isArray(response.workflows) ? response.workflows : [],
    tasks: Array.isArray(response.tasks) ? response.tasks : [],
    runs: Array.isArray(response.runs) ? response.runs : [],
  }
}

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
    else setData(normalizeWorkflowResponse(res.data))
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
