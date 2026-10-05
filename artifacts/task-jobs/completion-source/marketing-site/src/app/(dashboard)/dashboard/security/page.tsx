'use client'

import { useState, useEffect, useCallback } from 'react'
import Link from 'next/link'
import { useTenantApi } from '@/hooks/useTenantApi'

interface HealthStatus {
    status?: string
    uptime?: number
    version?: string
    [key: string]: unknown
}

interface VaultStatus {
    connected?: boolean
    status?: string
    address?: string
    [key: string]: unknown
}

interface ReaperHealth {
    status?: string
    active?: boolean
    [key: string]: unknown
}

interface Alert {
    id?: string
    level?: string
    message?: string
    timestamp?: string
    [key: string]: unknown
}

interface AuthStatus {
    authenticated?: boolean
    method?: string
    user?: string
    [key: string]: unknown
}

function StatusDot({ ok }: { ok: boolean | undefined }) {
    return (
        <span className={`inline-block h-2.5 w-2.5 rounded-full ${ok ? 'bg-green-500' : ok === false ? 'bg-red-500' : 'bg-gray-500'}`} />
    )
}

export default function SecurityPage() {
    const [activeTab, setActiveTab] = useState<'health' | 'alerts' | 'policies'>('health')
    const { tenantFetch, isAuthenticated, isLoading: authLoading } = useTenantApi()

    const [health, setHealth] = useState<HealthStatus | null>(null)
    const [vault, setVault] = useState<VaultStatus | null>(null)
    const [reaper, setReaper] = useState<ReaperHealth | null>(null)
    const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null)
    const [alerts, setAlerts] = useState<Alert[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const fetchHealth = useCallback(async () => {
        const [healthRes, vaultRes, reaperRes, authRes] = await Promise.all([
            tenantFetch<HealthStatus>('/v1/admin/health'),
            tenantFetch<VaultStatus>('/v1/agent/vault/status'),
            tenantFetch<ReaperHealth>('/v1/agent/reaper/health'),
            tenantFetch<AuthStatus>('/v1/auth/status'),
        ])

        const authErrors = [
            healthRes.error,
            vaultRes.error,
            reaperRes.error,
            authRes.error,
        ].filter((value): value is string => Boolean(value))
        if (authErrors.some((value) => value.toLowerCase().includes('session expired'))) {
            setError('Session expired. Please sign in again.')
            return
        }

        if (healthRes.data) setHealth(healthRes.data)
        if (vaultRes.data) setVault(vaultRes.data)
        if (reaperRes.data) setReaper(reaperRes.data)
        if (authRes.data) setAuthStatus(authRes.data)
        if (healthRes.error && vaultRes.error) setError('Failed to connect to server')
        else setError(null)
    }, [tenantFetch])

    const fetchAlerts = useCallback(async () => {
        const { data, error: alertsError } = await tenantFetch<Alert[]>('/v1/admin/alerts')
        if (alertsError?.toLowerCase().includes('session expired')) {
            setError('Session expired. Please sign in again.')
            return
        }
        if (data && Array.isArray(data)) setAlerts(data)
    }, [tenantFetch])

    useEffect(() => {
        if (!isAuthenticated) return
        setLoading(true)
        Promise.all([fetchHealth(), fetchAlerts()]).finally(() => setLoading(false))
        const interval = setInterval(() => { fetchHealth(); fetchAlerts() }, 30000)
        return () => clearInterval(interval)
    }, [isAuthenticated, fetchHealth, fetchAlerts])

    const systemOk = health?.status === 'ok' || health?.status === 'healthy'
    const vaultOk = vault?.connected === true || vault?.status === 'ok' || vault?.status === 'connected'
    const reaperOk = reaper?.active === true || reaper?.status === 'ok' || reaper?.status === 'healthy'
    const alertCount = alerts.length

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Security</h1>
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        Defense-in-depth architecture: mandatory auth, signed plugins, sandboxed execution, and full audit trail.
                    </p>
                </div>
                {isAuthenticated && (
                    <button
                        onClick={() => { setLoading(true); Promise.all([fetchHealth(), fetchAlerts()]).finally(() => setLoading(false)) }}
                        disabled={loading}
                        className="px-4 py-2 text-sm bg-cyan-600 text-white rounded-lg hover:bg-cyan-500 disabled:opacity-50"
                    >
                        {loading ? 'Checking...' : 'Refresh'}
                    </button>
                )}
            </div>

            {/* Live status bar */}
            {isAuthenticated && !authLoading && !loading && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                        <div className="flex items-center gap-2 mb-1">
                            <StatusDot ok={systemOk} />
                            <span className="text-xs font-medium text-gray-500 dark:text-gray-400">System</span>
                        </div>
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">
                            {health?.status || 'Unknown'}
                        </div>
                    </div>
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                        <div className="flex items-center gap-2 mb-1">
                            <StatusDot ok={vaultOk} />
                            <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Vault</span>
                        </div>
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">
                            {vault ? (vaultOk ? 'Connected' : 'Disconnected') : 'Unknown'}
                        </div>
                    </div>
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                        <div className="flex items-center gap-2 mb-1">
                            <StatusDot ok={reaperOk} />
                            <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Reaper</span>
                        </div>
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">
                            {reaper ? (reaperOk ? 'Active' : 'Inactive') : 'Unknown'}
                        </div>
                    </div>
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
                        <div className="flex items-center gap-2 mb-1">
                            <StatusDot ok={authStatus?.authenticated} />
                            <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Auth</span>
                        </div>
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">
                            {authStatus?.method || 'Bearer'}
                        </div>
                    </div>
                    <div className={`bg-white dark:bg-gray-800 rounded-lg p-4 border ${alertCount > 0 ? 'border-red-200 dark:border-red-800' : 'border-gray-200 dark:border-gray-700'}`}>
                        <div className="text-2xl font-bold text-gray-900 dark:text-white">{alertCount}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">Active Alerts</div>
                    </div>
                </div>
            )}

            {/* Tabs */}
            <div className="border-b border-gray-700">
                <nav className="flex gap-4">
                    {([
                        { key: 'health' as const, label: 'System Health' },
                        { key: 'alerts' as const, label: `Alerts${alertCount > 0 ? ` (${alertCount})` : ''}` },
                        { key: 'policies' as const, label: 'Policies & Signing' },
                    ]).map(tab => (
                        <button
                            key={tab.key}
                            onClick={() => setActiveTab(tab.key)}
                            className={`pb-3 px-1 text-sm font-medium border-b-2 transition-colors ${activeTab === tab.key
                                ? 'border-cyan-500 text-cyan-400'
                                : 'border-transparent text-gray-400 hover:text-gray-300'
                                }`}
                        >
                            {tab.label}
                        </button>
                    ))}
                </nav>
            </div>

            {activeTab === 'health' && (
                <div className="space-y-6">
                    {!isAuthenticated && !authLoading ? (
                        <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-8 text-center">
                            <h3 className="text-lg font-semibold text-white mb-2">Sign in to view system health</h3>
                            <p className="text-sm text-gray-400">Connect your account to see live security and health status.</p>
                        </div>
                    ) : loading ? (
                        <div className="flex items-center gap-2 text-gray-400 py-12 justify-center">
                            <div className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
                            Checking system health...
                        </div>
                    ) : error ? (
                        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4 text-sm text-red-400">{error}</div>
                    ) : (
                        <>
                            {/* Detailed health cards */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {health && (
                                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-5">
                                        <div className="flex items-center gap-2 mb-3">
                                            <StatusDot ok={systemOk} />
                                            <h3 className="text-sm font-semibold text-white">Admin Health</h3>
                                        </div>
                                        <div className="space-y-2 text-xs">
                                            {Object.entries(health).map(([key, value]) => (
                                                <div key={key} className="flex justify-between">
                                                    <span className="text-gray-400">{key}</span>
                                                    <span className="text-gray-300 font-mono">{String(value)}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {vault && (
                                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-5">
                                        <div className="flex items-center gap-2 mb-3">
                                            <StatusDot ok={vaultOk} />
                                            <h3 className="text-sm font-semibold text-white">Vault Connectivity</h3>
                                        </div>
                                        <div className="space-y-2 text-xs">
                                            {Object.entries(vault).map(([key, value]) => (
                                                <div key={key} className="flex justify-between">
                                                    <span className="text-gray-400">{key}</span>
                                                    <span className="text-gray-300 font-mono">{String(value)}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {reaper && (
                                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-5">
                                        <div className="flex items-center gap-2 mb-3">
                                            <StatusDot ok={reaperOk} />
                                            <h3 className="text-sm font-semibold text-white">Task Reaper</h3>
                                        </div>
                                        <div className="space-y-2 text-xs">
                                            {Object.entries(reaper).map(([key, value]) => (
                                                <div key={key} className="flex justify-between">
                                                    <span className="text-gray-400">{key}</span>
                                                    <span className="text-gray-300 font-mono">{String(value)}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {authStatus && (
                                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-5">
                                        <div className="flex items-center gap-2 mb-3">
                                            <StatusDot ok={authStatus.authenticated} />
                                            <h3 className="text-sm font-semibold text-white">Authentication</h3>
                                        </div>
                                        <div className="space-y-2 text-xs">
                                            {Object.entries(authStatus).map(([key, value]) => (
                                                <div key={key} className="flex justify-between">
                                                    <span className="text-gray-400">{key}</span>
                                                    <span className="text-gray-300 font-mono">{String(value)}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Security architecture */}
                            <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                                <h3 className="text-lg font-semibold text-white mb-4">Security Layers</h3>
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {[
                                        { title: 'Mandatory Authentication', desc: 'Every MCP connection and A2A request requires valid credentials.', icon: '🔐', scope: 'both' },
                                        { title: 'Ed25519 Plugin Signing', desc: 'Plugins are cryptographically signed and verified at load time.', icon: '🔏', scope: 'both' },
                                        { title: 'Sandboxed Execution', desc: 'CPU, memory, disk, and network are constrained per-tool.', icon: '📦', scope: 'both' },
                                        { title: 'Full Audit Trail', desc: 'Every action logged to tamper-evident JSONL audit log.', icon: '📋', scope: 'both' },
                                        { title: 'HashiCorp Vault', desc: 'Secrets fetched at runtime, never stored in config files.', icon: '🗝️', scope: 'both' },
                                        { title: 'K8s Self-Healing', desc: 'Auto-restart with exponential backoff, health probes.', icon: '🔄', scope: 'k8s' },
                                    ].map(item => (
                                        <div key={item.title} className="rounded-lg bg-gray-700/50 p-4">
                                            <div className="flex items-start justify-between mb-2">
                                                <span className="text-2xl">{item.icon}</span>
                                                <span className={`text-[10px] px-1.5 py-0.5 rounded ${item.scope === 'k8s' ? 'bg-purple-500/20 text-purple-400' : 'bg-gray-500/20 text-gray-300'}`}>
                                                    {item.scope === 'k8s' ? '☸️ K8s' : '🖥️ + ☸️'}
                                                </span>
                                            </div>
                                            <h4 className="text-sm font-semibold text-white">{item.title}</h4>
                                            <p className="mt-1 text-xs text-gray-400">{item.desc}</p>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </>
                    )}
                </div>
            )}

            {activeTab === 'alerts' && (
                <div className="space-y-6">
                    {!isAuthenticated && !authLoading ? (
                        <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-8 text-center">
                            <h3 className="text-lg font-semibold text-white mb-2">Sign in to view alerts</h3>
                            <p className="text-sm text-gray-400">Connect your account to see live system alerts.</p>
                        </div>
                    ) : loading ? (
                        <div className="flex items-center gap-2 text-gray-400 py-12 justify-center">
                            <div className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
                            Loading alerts...
                        </div>
                    ) : alerts.length === 0 ? (
                        <div className="rounded-xl border border-green-500/30 bg-green-500/5 p-8 text-center">
                            <span className="text-3xl mb-3 block">✅</span>
                            <h3 className="text-lg font-semibold text-white mb-2">All clear</h3>
                            <p className="text-sm text-gray-400">No active alerts. System is operating normally.</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {alerts.map((alert, i) => (
                                <div key={alert.id || i} className={`rounded-lg border p-4 ${alert.level === 'critical' || alert.level === 'error'
                                        ? 'border-red-500/30 bg-red-500/5'
                                        : alert.level === 'warning'
                                            ? 'border-yellow-500/30 bg-yellow-500/5'
                                            : 'border-gray-700 bg-gray-800/50'
                                    }`}>
                                    <div className="flex items-start gap-3">
                                        <span className={`px-2 py-0.5 text-xs font-medium rounded-full shrink-0 ${alert.level === 'critical' || alert.level === 'error'
                                                ? 'bg-red-500/20 text-red-400'
                                                : alert.level === 'warning'
                                                    ? 'bg-yellow-500/20 text-yellow-400'
                                                    : 'bg-gray-500/20 text-gray-400'
                                            }`}>
                                            {alert.level || 'info'}
                                        </span>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm text-gray-300">{alert.message || JSON.stringify(alert)}</p>
                                            {alert.timestamp && (
                                                <p className="text-xs text-gray-500 mt-1">{new Date(alert.timestamp).toLocaleString()}</p>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Tracked events reference */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-4">Tracked Events</h3>
                        <div className="space-y-2">
                            {[
                                { event: 'tool_execution', desc: 'Every MCP tool call — input, output hash, duration, sandbox config' },
                                { event: 'okr_approval', desc: 'OKR approve/deny decisions with user identity and timestamp' },
                                { event: 'auth_failure', desc: 'Failed authentication attempts with source IP' },
                                { event: 'policy_deny', desc: 'OPA policy denied an action — includes the policy rule that triggered' },
                                { event: 'secret_access', desc: 'Vault secret read — key path (not value) logged' },
                            ].map(item => (
                                <div key={item.event} className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4 rounded-lg bg-gray-700/50 px-4 py-3">
                                    <code className="text-sm text-cyan-400 font-mono shrink-0">{item.event}</code>
                                    <span className="text-xs text-gray-400">{item.desc}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {activeTab === 'policies' && (
                <div className="max-w-3xl space-y-6">
                    <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-6">
                        <h3 className="text-lg font-semibold text-white mb-2">Admin Policy Editor</h3>
                        <p className="text-sm text-gray-300 mb-4">
                            Non-technical admins can manage OPA RBAC roles with checkboxes and inheritance instead of editing Rego files.
                        </p>
                        <div className="flex items-center gap-2">
                            <Link
                                href="/dashboard/admin/policies"
                                className="inline-flex items-center rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-500"
                            >
                                Open OPA Policy Editor
                            </Link>
                            <Link
                                href="/dashboard/admin/users"
                                className="inline-flex items-center rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-sm font-semibold text-emerald-300 hover:bg-emerald-500/20"
                            >
                                Open User Management
                            </Link>
                        </div>
                    </div>

                    {/* OPA */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-2">OPA Policy Engine</h3>
                        <p className="text-sm text-gray-400 mb-4">
                            Authorization is enforced by Open Policy Agent. Policies are written in Rego and evaluated on every request.
                        </p>
                        <pre className="rounded-lg bg-gray-900 p-4 text-xs text-gray-300 font-mono overflow-x-auto">{`# policies/authz.rego
package authz

default allow = false

allow {
    input.role == "admin"
}

allow {
    input.role == "editor"
    input.action == "task:read"
}`}</pre>
                        <p className="mt-3 text-xs text-gray-500">
                            RBAC hierarchy: admin &gt; a2a-admin &gt; operator &gt; editor &gt; viewer
                        </p>
                    </div>

                    {/* Plugin signing */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-2">Plugin Signing (Ed25519)</h3>
                        <p className="text-sm text-gray-400 mb-4">
                            Plugins must be signed with an Ed25519 key. The agent verifies signatures at load time.
                        </p>
                        <div className="space-y-3 font-mono text-sm">
                            {[
                                { cmd: 'codetether plugin sign --key private.pem plugin.wasm', desc: 'Sign a plugin' },
                                { cmd: 'codetether plugin verify plugin.wasm', desc: 'Verify signature' },
                                { cmd: 'codetether plugin install plugin.wasm', desc: 'Install (auto-verifies)' },
                            ].map(item => (
                                <div key={item.cmd} className="flex flex-col sm:flex-row sm:items-center gap-1 sm:gap-4 rounded-lg bg-gray-700/50 px-4 py-3">
                                    <code className="text-cyan-400 shrink-0">{item.cmd}</code>
                                    <span className="text-gray-400 text-xs">{item.desc}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Sandbox Resource Limits */}
                    <div className="rounded-xl border border-gray-700 bg-gray-800/50 p-6">
                        <h3 className="text-lg font-semibold text-white mb-4">Sandbox Resource Limits</h3>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm text-left">
                                <thead className="text-xs text-gray-400 border-b border-gray-700">
                                    <tr>
                                        <th className="py-2 pr-4">Resource</th>
                                        <th className="py-2 pr-4">Default</th>
                                        <th className="py-2">Config Flag</th>
                                    </tr>
                                </thead>
                                <tbody className="text-gray-300 font-mono">
                                    {[
                                        { resource: 'CPU', def: '100m', flag: '--sandbox-cpu' },
                                        { resource: 'Memory', def: '256Mi', flag: '--sandbox-memory' },
                                        { resource: 'Disk I/O', def: '50MB/s', flag: '--sandbox-disk-io' },
                                        { resource: 'Network', def: 'Deny by default', flag: '--sandbox-network' },
                                        { resource: 'Timeout', def: '30s', flag: '--sandbox-timeout' },
                                        { resource: 'Process count', def: '10', flag: '--sandbox-max-procs' },
                                    ].map(row => (
                                        <tr key={row.resource} className="border-b border-gray-800">
                                            <td className="py-2 pr-4 text-white">{row.resource}</td>
                                            <td className="py-2 pr-4 text-cyan-400">{row.def}</td>
                                            <td className="py-2 text-gray-400">{row.flag}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
