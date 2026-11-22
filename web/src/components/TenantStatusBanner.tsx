'use client'

import { useSession } from 'next-auth/react'
import { useState, useEffect } from 'react'

interface TenantHealth {
  status: 'healthy' | 'degraded' | 'offline' | 'loading'
  latency?: number
  timestamp?: string
}

function ShieldCheckIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
  return (
    <svg fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
    </svg>
  )
}

function ServerIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
  return (
    <svg fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 17.25v-.228a4.5 4.5 0 00-.12-1.03l-2.268-9.64a3.375 3.375 0 00-3.285-2.602H7.923a3.375 3.375 0 00-3.285 2.602l-2.268 9.64a4.5 4.5 0 00-.12 1.03v.228m19.5 0a3 3 0 01-3 3H5.25a3 3 0 01-3-3m19.5 0a3 3 0 00-3-3H5.25a3 3 0 00-3 3m16.5 0h.008v.008h-.008v-.008zm-3 0h.008v.008h-.008v-.008z" />
    </svg>
  )
}

function LockClosedIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
  return (
    <svg fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
    </svg>
  )
}

function GlobeIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
  return (
    <svg fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
    </svg>
  )
}

export default function TenantStatusBanner() {
  const { data: session, status } = useSession()
  const [health, setHealth] = useState<TenantHealth>({ status: 'loading' })
  const [expanded, setExpanded] = useState(false)

  const tenantSlug = session?.tenantSlug
  const tenantApiUrl = session?.tenantApiUrl
  const hasDedicatedInstance = !!(tenantSlug && tenantApiUrl?.includes(tenantSlug))

  // Check health of tenant's API
  useEffect(() => {
    if (!tenantApiUrl || status !== 'authenticated') {
      setHealth({ status: 'loading' })
      return
    }

    const checkHealth = async () => {
      const start = Date.now()
      try {
        const response = await fetch(`${tenantApiUrl}/health`, {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
        })
        const latency = Date.now() - start
        
        if (response.ok) {
          const data = await response.json()
          setHealth({
            status: 'healthy',
            latency,
            timestamp: data.timestamp || new Date().toISOString(),
          })
        } else {
          setHealth({ status: 'degraded', latency })
        }
      } catch {
        setHealth({ status: 'offline' })
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 30000) // Check every 30s
    return () => clearInterval(interval)
  }, [tenantApiUrl, status])

  if (status === 'loading') {
    return (
      <div className="rounded-lg bg-gray-100 dark:bg-gray-800 p-4 animate-pulse">
        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/3"></div>
      </div>
    )
  }

  if (status !== 'authenticated' || !session) {
    return null
  }

  const statusColors = {
    healthy: 'bg-green-500',
    degraded: 'bg-yellow-500',
    offline: 'bg-red-500',
    loading: 'bg-gray-400 animate-pulse',
  }

  const statusText = {
    healthy: 'Connected',
    degraded: 'Degraded',
    offline: 'Offline',
    loading: 'Connecting...',
  }

  return (
    <div className="mb-6 rounded-lg bg-gradient-to-r from-cyan-950/40 to-gray-900 border border-cyan-500/20 overflow-hidden">
      {/* Main Banner */}
      <div 
        className="p-4 cursor-pointer hover:bg-cyan-950/20 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Status Indicator */}
            <div className="flex items-center gap-2">
              <span className={`h-3 w-3 rounded-full ${statusColors[health.status]}`} />
              <span className="text-sm font-medium text-gray-200">
                {statusText[health.status]}
              </span>
            </div>

            {/* Tenant Info */}
            <div className="flex items-center gap-2 text-cyan-400">
              {hasDedicatedInstance ? (
                <>
                  <ShieldCheckIcon className="h-5 w-5" />
                  <span className="text-sm font-semibold">Isolated Instance</span>
                </>
              ) : (
                <>
                  <GlobeIcon className="h-5 w-5" />
                  <span className="text-sm font-semibold">Shared Instance</span>
                </>
              )}
            </div>
          </div>

          {/* URL Badge */}
          <div className="flex items-center gap-3">
            {tenantApiUrl && (
              <code className="text-xs bg-gray-800 text-cyan-300 px-2 py-1 rounded font-mono">
                {tenantApiUrl.replace('https://', '')}
              </code>
            )}
            <svg
              className={`h-5 w-5 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-cyan-500/10 pt-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Isolation Status */}
            <div className="bg-gray-800/50 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <LockClosedIcon className="h-4 w-4 text-cyan-400" />
                <span className="text-xs font-medium text-gray-300">Data Isolation</span>
              </div>
              <p className="text-sm text-gray-400">
                {hasDedicatedInstance 
                  ? 'Your data is isolated in a dedicated Kubernetes namespace with Row-Level Security.'
                  : 'Your data is protected by Row-Level Security policies on shared infrastructure.'}
              </p>
              <div className="mt-2 flex items-center gap-1">
                <span className="inline-flex items-center rounded-full bg-green-500/20 px-2 py-0.5 text-xs font-medium text-green-400">
                  RLS Enabled
                </span>
                {hasDedicatedInstance && (
                  <span className="inline-flex items-center rounded-full bg-cyan-500/20 px-2 py-0.5 text-xs font-medium text-cyan-400">
                    Dedicated K8s
                  </span>
                )}
              </div>
            </div>

            {/* Instance Details */}
            <div className="bg-gray-800/50 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <ServerIcon className="h-4 w-4 text-cyan-400" />
                <span className="text-xs font-medium text-gray-300">Instance Details</span>
              </div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Tenant ID:</span>
                  <code className="text-gray-300 text-xs font-mono">
                    {session.tenantId ? `${session.tenantId.slice(0, 8)}...` : 'N/A'}
                  </code>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Namespace:</span>
                  <code className="text-gray-300 text-xs font-mono">
                    {tenantSlug ? `tenant-${tenantSlug}` : 'shared'}
                  </code>
                </div>
                {health.latency && (
                  <div className="flex justify-between">
                    <span className="text-gray-500">Latency:</span>
                    <span className={`text-xs ${health.latency < 100 ? 'text-green-400' : health.latency < 300 ? 'text-yellow-400' : 'text-red-400'}`}>
                      {health.latency}ms
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Quick Stats */}
            <div className="bg-gray-800/50 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-2">
                <GlobeIcon className="h-4 w-4 text-cyan-400" />
                <span className="text-xs font-medium text-gray-300">API Endpoint</span>
              </div>
              <div className="space-y-2">
                <a 
                  href={`${tenantApiUrl}/.well-known/agent-card.json`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-xs text-cyan-400 hover:text-cyan-300 truncate"
                >
                  {tenantApiUrl}/.well-known/agent-card.json
                </a>
                <a 
                  href={`${tenantApiUrl}/openapi.json`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-xs text-cyan-400 hover:text-cyan-300 truncate"
                >
                  {tenantApiUrl}/openapi.json
                </a>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
