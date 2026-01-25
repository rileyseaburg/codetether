'use client'

import { useState, useEffect } from 'react'
import { useSession, signOut } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import {
  getAdminDashboardV1AdminDashboardGet,
  getSystemAlertsV1AdminAlertsGet,
  listTenantsV1AdminTenantsGet,
  listUsersV1AdminUsersGet,
  listK8sInstancesV1AdminInstancesGet,
  suspendInstanceV1AdminInstancesNamespaceSuspendPost,
  resumeInstanceV1AdminInstancesNamespaceResumePost,
  deleteInstanceV1AdminInstancesNamespaceDelete,
} from '@/lib/api'

interface UserStats {
    total_users: number
    active_users: number
    users_last_24h: number
    users_last_7d: number
    users_last_30d: number
    pending_verification: number
    suspended: number
}

interface TenantStats {
    total_tenants: number
    tenants_by_plan: Record<string, number>
    tenants_with_k8s: number
    tenants_last_24h: number
    tenants_last_7d: number
}

interface SubscriptionStats {
    total_subscriptions: number
    active_subscriptions: number
    mrr_estimate: number
    subscriptions_by_tier: Record<string, number>
    past_due: number
    canceled_last_30d: number
}

interface K8sClusterStats {
    total_namespaces: number
    running_instances: number
    suspended_instances: number
    total_pods: number
    healthy_pods: number
    unhealthy_pods: number
}

interface DashboardData {
    users: UserStats
    tenants: TenantStats
    subscriptions: SubscriptionStats
    k8s_cluster: K8sClusterStats | null
    recent_signups: any[]
}

interface User {
    id: string
    email: string
    name: string | null
    created_at: string
    last_login: string | null
    tenant_id: string | null
    tenant_name: string | null
}

interface Tenant {
    id: string
    realm_name: string
    display_name: string | null
    plan: string
    created_at: string
    user_count: number
    k8s_namespace: string | null
    k8s_external_url: string | null
}

interface Instance {
    tenant_id: string
    tenant_name: string
    namespace: string
    status: string
    tier: string
    external_url: string | null
    created_at: string
}

interface Alert {
    level: string
    message: string
    tenant_id?: string
    details?: string
}

function ShieldIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
        </svg>
    )
}

function UsersIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
    )
}

function ServerIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
        </svg>
    )
}

function CurrencyIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    )
}

function RefreshIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
    )
}

function AlertIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
    )
}

export default function AdminDashboard() {
    const { data: session, status } = useSession()
    const router = useRouter()
    const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'tenants' | 'instances'>('overview')
    const [dashboardData, setDashboardData] = useState<DashboardData | null>(null)
    const [users, setUsers] = useState<User[]>([])
    const [tenants, setTenants] = useState<Tenant[]>([])
    const [instances, setInstances] = useState<Instance[]>([])
    const [alerts, setAlerts] = useState<Alert[]>([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [actionLoading, setActionLoading] = useState<string | null>(null)

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

    // Check if user has admin role
    const isAdmin = (session?.user as any)?.roles?.includes('admin') || 
                    (session?.user as any)?.roles?.includes('a2a-admin') ||
                    (session?.user as any)?.role === 'admin'

    useEffect(() => {
        if (status === 'loading') return
        if (!session) {
            router.push('/login')
            return
        }
        
        // Check if token refresh failed - force re-login
        if ((session as any)?.error === 'RefreshAccessTokenError') {
            console.error('Token refresh failed, signing out...')
            signOut({ callbackUrl: '/login?error=session_expired' })
            return
        }
        
        if (!isAdmin) {
            router.push('/dashboard')
            return
        }
        fetchDashboardData()
    }, [session, status, isAdmin])

    const fetchDashboardData = async () => {
        setLoading(true)
        setError(null)
        try {
            // accessToken is on the session object directly, not session.user
            const token = (session as any)?.accessToken
            console.log('Admin dashboard - full session:', JSON.stringify(session, null, 2))
            console.log('Admin dashboard - token:', token ? `${token.substring(0, 50)}...` : 'NO TOKEN')
            console.log('Admin dashboard - session keys:', session ? Object.keys(session) : 'no session')
            
            if (!token) {
                throw new Error('No access token available')
            }
            
            const headers = {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }

            const [dashboardRes, alertsRes, tenantsRes] = await Promise.all([
                fetch(`${API_BASE}/v1/admin/dashboard`, { headers }),
                fetch(`${API_BASE}/v1/admin/alerts`, { headers }),
                fetch(`${API_BASE}/v1/admin/tenants?limit=50`, { headers })
            ])

            if (!dashboardRes.ok) {
                // Handle 401 - token expired or invalid
                if (dashboardRes.status === 401) {
                    console.error('API returned 401, signing out...')
                    signOut({ callbackUrl: '/login?error=session_expired' })
                    return
                }
                throw new Error(`Failed to fetch dashboard: ${dashboardRes.status}`)
            }

            const data = await dashboardRes.json()
            setDashboardData(data)
            // Map recent_signups to users format for overview
            setUsers((data.recent_signups || []).map((u: any) => ({
                id: u.id,
                email: u.email,
                name: u.name,
                created_at: u.created_at,
                last_login: null,
                tenant_id: null,
                tenant_name: u.tenant
            })))

            if (alertsRes.ok) {
                const alertsData = await alertsRes.json()
                setAlerts(alertsData.alerts || [])
            }

            if (tenantsRes.ok) {
                const tenantsData = await tenantsRes.json()
                setTenants(tenantsData.tenants || [])
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load dashboard')
        } finally {
            setLoading(false)
        }
    }

    const fetchUsers = async () => {
        try {
            const token = (session as any)?.accessToken
            const res = await fetch(`${API_BASE}/v1/admin/users?limit=50`, {
                headers: { 'Authorization': `Bearer ${token}` }
            })
            if (res.ok) {
                const data = await res.json()
                setUsers(data.users || [])
            }
        } catch (err) {
            console.error('Failed to fetch users:', err)
        }
    }

    const fetchTenants = async () => {
        try {
            const token = (session as any)?.accessToken
            const res = await fetch(`${API_BASE}/v1/admin/tenants?limit=50`, {
                headers: { 'Authorization': `Bearer ${token}` }
            })
            if (res.ok) {
                const data = await res.json()
                setTenants(data.tenants || [])
            }
        } catch (err) {
            console.error('Failed to fetch tenants:', err)
        }
    }

    const fetchInstances = async () => {
        try {
            const token = (session as any)?.accessToken
            const res = await fetch(`${API_BASE}/v1/admin/instances`, {
                headers: { 'Authorization': `Bearer ${token}` }
            })
            if (res.ok) {
                const data = await res.json()
                setInstances(data.instances || [])
            }
        } catch (err) {
            console.error('Failed to fetch instances:', err)
        }
    }

    const handleInstanceAction = async (tenantId: string, action: 'suspend' | 'resume' | 'delete') => {
        setActionLoading(`${tenantId}-${action}`)
        try {
            const token = (session as any)?.accessToken
            const res = await fetch(`${API_BASE}/v1/admin/instances/${tenantId}/${action}`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            })
            if (res.ok) {
                fetchInstances()
            } else {
                const data = await res.json()
                alert(data.detail || `Failed to ${action} instance`)
            }
        } catch (err) {
            alert(`Failed to ${action} instance`)
        } finally {
            setActionLoading(null)
        }
    }

    useEffect(() => {
        if (activeTab === 'users') fetchUsers()
        if (activeTab === 'tenants') fetchTenants()
        if (activeTab === 'instances') fetchInstances()
    }, [activeTab])

     if (status === 'loading' || loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-cyan-600"></div>
            </div>
        )
    }

    if (!isAdmin) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <ShieldIcon className="h-16 w-16 text-red-500 mx-auto mb-4" />
                    <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Access Denied</h2>
                    <p className="text-gray-600 dark:text-gray-400 mt-2">You do not have admin privileges.</p>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <AlertIcon className="h-16 w-16 text-red-500 mx-auto mb-4" />
                    <h2 className="text-xl font-semibold text-gray-900 dark:text-white">Error Loading Dashboard</h2>
                    <p className="text-gray-600 dark:text-gray-400 mt-2">{error}</p>
                     <button
                        onClick={fetchDashboardData}
                        className="mt-4 px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700"
                    >
                        Retry
                    </button>
                </div>
            </div>
        )
    }

    return (
        <div className="h-full flex flex-col overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                 <div className="flex items-center gap-3">
                    <ShieldIcon className="h-8 w-8 text-cyan-600" />
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Admin Dashboard</h1>
                </div>
                <button
                    onClick={fetchDashboardData}
                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                    <RefreshIcon className="h-4 w-4" />
                    Refresh
                </button>
            </div>

            {/* Alerts */}
            {alerts.length > 0 && (
                <div className="mb-6 space-y-2">
                    {alerts.map((alert, idx) => (
                        <div
                            key={idx}
                            className={`p-4 rounded-lg flex items-start gap-3 ${
                                alert.level === 'critical' ? 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200' :
                                alert.level === 'warning' ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200' :
                                'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200'
                            }`}
                        >
                            <AlertIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />
                            <div>
                                <p className="font-medium">{alert.message}</p>
                                {alert.details && <p className="text-sm mt-1 opacity-80">{alert.details}</p>}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-cyan-100 dark:bg-cyan-900/50 rounded-lg">
                            <UsersIcon className="h-6 w-6 text-cyan-600 dark:text-cyan-400" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-600 dark:text-gray-400">Total Users</p>
                            <p className="text-2xl font-bold text-gray-900 dark:text-white">{dashboardData?.users?.total_users || 0}</p>
                            <p className="text-xs text-gray-500 dark:text-gray-500">{dashboardData?.users?.users_last_24h || 0} new (24h)</p>
                        </div>
                    </div>
                </div>

                <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-green-100 dark:bg-green-900/50 rounded-lg">
                            <ServerIcon className="h-6 w-6 text-green-600 dark:text-green-400" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-600 dark:text-gray-400">Total Tenants</p>
                            <p className="text-2xl font-bold text-gray-900 dark:text-white">{dashboardData?.tenants?.total_tenants || 0}</p>
                            <p className="text-xs text-gray-500 dark:text-gray-500">{dashboardData?.tenants?.tenants_with_k8s || 0} with K8s</p>
                        </div>
                    </div>
                </div>

                <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-cyan-100 dark:bg-cyan-900/50 rounded-lg">
                            <ServerIcon className="h-6 w-6 text-cyan-600 dark:text-cyan-400" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-600 dark:text-gray-400">K8s Instances</p>
                            <p className="text-2xl font-bold text-gray-900 dark:text-white">{dashboardData?.k8s_cluster?.total_namespaces || 0}</p>
                            <p className="text-xs text-gray-500 dark:text-gray-500">{dashboardData?.k8s_cluster?.running_instances || 0} running</p>
                        </div>
                    </div>
                </div>

                <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
                    <div className="flex items-center gap-4">
                        <div className="p-3 bg-yellow-100 dark:bg-yellow-900/50 rounded-lg">
                            <CurrencyIcon className="h-6 w-6 text-yellow-600 dark:text-yellow-400" />
                        </div>
                        <div>
                            <p className="text-sm text-gray-600 dark:text-gray-400">Estimated MRR</p>
                            <p className="text-2xl font-bold text-gray-900 dark:text-white">
                                ${dashboardData?.subscriptions?.mrr_estimate?.toLocaleString() || 0}
                            </p>
                            <p className="text-xs text-gray-500 dark:text-gray-500">{dashboardData?.subscriptions?.active_subscriptions || 0} active subs</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Tier Distribution */}
            {dashboardData?.subscriptions?.subscriptions_by_tier && Object.keys(dashboardData.subscriptions.subscriptions_by_tier).length > 0 && (
                <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700 mb-6">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Tier Distribution</h3>
                    <div className="flex flex-wrap gap-4">
                        {Object.entries(dashboardData.subscriptions.subscriptions_by_tier).map(([tier, count]) => (
                            <div key={tier} className="flex items-center gap-2">
                                <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                                    tier === 'enterprise' ? 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/50 dark:text-cyan-300' :
                                    tier === 'agency' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300' :
                                    tier === 'pro' ? 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300' :
                                    'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                                }`}>
                                    {tier}: {count}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Tabs */}
            <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
                <nav className="flex gap-4">
                    {(['overview', 'users', 'tenants', 'instances'] as const).map((tab) => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            className={`py-2 px-4 text-sm font-medium border-b-2 -mb-px transition-colors ${
                                activeTab === tab
                                    ? 'border-cyan-600 text-cyan-600 dark:border-cyan-400 dark:text-cyan-400'
                                    : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                            }`}
                        >
                            {tab.charAt(0).toUpperCase() + tab.slice(1)}
                        </button>
                    ))}
                </nav>
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-auto">
                {activeTab === 'overview' && (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                        {/* Recent Users */}
                        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
                            <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Recent Users</h3>
                            </div>
                            <div className="divide-y divide-gray-200 dark:divide-gray-700">
                                {users.slice(0, 5).map((user) => (
                                    <div key={user.id} className="p-4 flex items-center justify-between">
                                        <div>
                                            <p className="font-medium text-gray-900 dark:text-white">{user.name || user.email}</p>
                                            <p className="text-sm text-gray-500 dark:text-gray-400">{user.email}</p>
                                        </div>
                                        <span className="text-xs text-gray-400">
                                            {new Date(user.created_at).toLocaleDateString()}
                                        </span>
                                    </div>
                                ))}
                                {users.length === 0 && (
                                    <p className="p-4 text-gray-500 dark:text-gray-400 text-center">No users yet</p>
                                )}
                            </div>
                        </div>

                        {/* Recent Tenants */}
                        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700">
                            <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Recent Tenants</h3>
                            </div>
                            <div className="divide-y divide-gray-200 dark:divide-gray-700">
                                {tenants.slice(0, 5).map((tenant) => (
                                    <div key={tenant.id} className="p-4 flex items-center justify-between">
                                        <div>
                                            <p className="font-medium text-gray-900 dark:text-white">{tenant.display_name || 'Unnamed'}</p>
                                            <p className="text-sm text-gray-500 dark:text-gray-400">{tenant.realm_name}</p>
                                        </div>
                                        <span className={`px-2 py-1 text-xs rounded-full ${
                                                tenant.plan === 'enterprise' ? 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/50 dark:text-cyan-300' :
                                            tenant.plan === 'agency' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300' :
                                            tenant.plan === 'pro' ? 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300' :
                                            'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                                        }`}>
                                            {tenant.plan || 'free'}
                                        </span>
                                    </div>
                                ))}
                                {tenants.length === 0 && (
                                    <p className="p-4 text-gray-500 dark:text-gray-400 text-center">No tenants yet</p>
                                )}
                            </div>
                        </div>
                    </div>
                )}

                {activeTab === 'users' && (
                    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
                        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                            <thead className="bg-gray-50 dark:bg-gray-900">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">User</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Tenant</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Created</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Last Login</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                                {users.map((user) => (
                                    <tr key={user.id}>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <div>
                                                <div className="font-medium text-gray-900 dark:text-white">{user.name || '-'}</div>
                                                <div className="text-sm text-gray-500 dark:text-gray-400">{user.email}</div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                            {user.tenant_name || '-'}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                            {new Date(user.created_at).toLocaleDateString()}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                            {user.last_login ? new Date(user.last_login).toLocaleDateString() : '-'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {activeTab === 'tenants' && (
                    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
                        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                            <thead className="bg-gray-50 dark:bg-gray-900">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Tenant</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Plan</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Users</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Created</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">K8s URL</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                                {tenants.map((tenant) => (
                                    <tr key={tenant.id}>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <div>
                                                <div className="font-medium text-gray-900 dark:text-white">{tenant.display_name || 'Unnamed'}</div>
                                                <div className="text-sm text-gray-500 dark:text-gray-400">{tenant.realm_name}</div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <span className={`px-2 py-1 text-xs rounded-full ${
                                            tenant.plan === 'enterprise' ? 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/50 dark:text-cyan-300' :
                                                tenant.plan === 'agency' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300' :
                                                tenant.plan === 'pro' ? 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300' :
                                                'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                                            }`}>
                                                {tenant.plan || 'free'}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                            {tenant.user_count}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                            {new Date(tenant.created_at).toLocaleDateString()}
                                        </td>
                                         <td className="px-6 py-4 whitespace-nowrap">
                                            {tenant.k8s_external_url ? (
                                                <a href={tenant.k8s_external_url} target="_blank" rel="noopener noreferrer" className="text-cyan-600 hover:underline">
                                                    {tenant.k8s_external_url}
                                                </a>
                                            ) : '-'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}

                {activeTab === 'instances' && (
                    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
                        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                            <thead className="bg-gray-50 dark:bg-gray-900">
                                <tr>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Instance</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Namespace</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Status</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Tier</th>
                                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                                {instances.map((instance) => (
                                    <tr key={instance.tenant_id}>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <div className="font-medium text-gray-900 dark:text-white">{instance.tenant_name}</div>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                            {instance.namespace}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap">
                                            <span className={`px-2 py-1 text-xs rounded-full ${
                                                instance.status === 'running' ? 'bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300' :
                                                instance.status === 'suspended' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300' :
                                                'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
                                            }`}>
                                                {instance.status}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                            {instance.tier}
                                        </td>
                                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                                            <div className="flex gap-2">
                                                {instance.status === 'running' ? (
                                                    <button
                                                        onClick={() => handleInstanceAction(instance.tenant_id, 'suspend')}
                                                        disabled={actionLoading === `${instance.tenant_id}-suspend`}
                                                        className="px-3 py-1 text-xs bg-yellow-100 text-yellow-800 rounded hover:bg-yellow-200 disabled:opacity-50"
                                                    >
                                                        {actionLoading === `${instance.tenant_id}-suspend` ? '...' : 'Suspend'}
                                                    </button>
                                                ) : (
                                                    <button
                                                        onClick={() => handleInstanceAction(instance.tenant_id, 'resume')}
                                                        disabled={actionLoading === `${instance.tenant_id}-resume`}
                                                        className="px-3 py-1 text-xs bg-green-100 text-green-800 rounded hover:bg-green-200 disabled:opacity-50"
                                                    >
                                                        {actionLoading === `${instance.tenant_id}-resume` ? '...' : 'Resume'}
                                                    </button>
                                                )}
                                                <button
                                                    onClick={() => {
                                                        if (confirm('Are you sure you want to delete this instance? This cannot be undone.')) {
                                                            handleInstanceAction(instance.tenant_id, 'delete')
                                                        }
                                                    }}
                                                    disabled={actionLoading === `${instance.tenant_id}-delete`}
                                                    className="px-3 py-1 text-xs bg-red-100 text-red-800 rounded hover:bg-red-200 disabled:opacity-50"
                                                >
                                                    {actionLoading === `${instance.tenant_id}-delete` ? '...' : 'Delete'}
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                                {instances.length === 0 && (
                                    <tr>
                                        <td colSpan={5} className="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
                                            No K8s instances provisioned yet
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    )
}
