'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, type ReactNode } from 'react'
import { useTenantApi } from '@/hooks/useTenantApi'
import type { GithubAppWorkflowResponse } from './types'
import {
  githubAppWorkflowsApiPath,
  githubAppWorkflowsReducer,
  initialGithubAppWorkflowsState,
  normalizeWorkflowResponse,
} from './GithubAppWorkflowsState'

type GithubAppWorkflowsContextValue = {
  data: GithubAppWorkflowResponse | null
  error: string | null
  loading: boolean
  repos: string
  autoRefresh: boolean
  setRepos: (value: string) => void
  setAutoRefresh: (value: boolean) => void
  load: () => Promise<void>
}

const GithubAppWorkflowsContext = createContext<GithubAppWorkflowsContextValue | undefined>(undefined)
GithubAppWorkflowsContext.displayName = 'GithubAppWorkflowsContext'

export function GithubAppWorkflowsProvider({ children }: { children: ReactNode }) {
  const { tenantFetch, apiUrl, isLoading: tenantLoading } = useTenantApi()
  const [state, dispatch] = useReducer(githubAppWorkflowsReducer, initialGithubAppWorkflowsState)
  const { data, error, loading, repos, autoRefresh } = state

  const load = useCallback(async () => {
    dispatch({ type: 'loading' })
    const path = githubAppWorkflowsApiPath(repos, apiUrl)
    const res = await tenantFetch<GithubAppWorkflowResponse>(path)
    if (res.error) dispatch({ type: 'failed', error: res.error })
    else dispatch({ type: 'loaded', data: normalizeWorkflowResponse(res.data) })
  }, [apiUrl, repos, tenantFetch])

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

  const value = useMemo(() => ({
    data,
    error,
    loading,
    repos,
    autoRefresh,
    setRepos: (value: string) => dispatch({ type: 'setRepos', repos: value }),
    setAutoRefresh: (value: boolean) => dispatch({ type: 'setAutoRefresh', autoRefresh: value }),
    load,
  }), [autoRefresh, data, error, load, loading, repos])

  return <GithubAppWorkflowsContext.Provider value={value}>{children}</GithubAppWorkflowsContext.Provider>
}

export function useGithubAppWorkflows() {
  const context = useContext(GithubAppWorkflowsContext)
  if (!context) throw new Error('useGithubAppWorkflows must be used within GithubAppWorkflowsProvider')
  return context
}
