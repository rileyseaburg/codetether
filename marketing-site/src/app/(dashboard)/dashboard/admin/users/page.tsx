'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { signOut, useSession } from 'next-auth/react'

interface RoleCatalog {
    realm_name: string
    opa_roles: string[]
    keycloak_roles: string[]
    missing_in_keycloak: string[]
    metadata?: RBACMetadata
}

interface RBACUser {
    id: string
    email: string
    username: string
    name?: string | null
    enabled: boolean
    email_verified: boolean
    roles: string[]
    opa_roles: string[]
    db_opa_roles?: string[]
    db_synced?: boolean | null
}

interface RBACMetadata {
    tenant_id?: string | null
    postgres_rls_enabled?: boolean
    postgres_sync_enabled?: boolean
    postgres_synced?: boolean
    postgres_table?: string
}

interface RBACUsersResponse {
    realm_name: string
    users: RBACUser[]
    total: number
    metadata?: RBACMetadata
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const getStoredToken = (): string | null => {
    if (typeof window === 'undefined') {
        return null
    }
    return localStorage.getItem('a2a_token')
}

const hasAdminRole = (user: any): boolean => {
    if (!user) {
        return false
    }
    const roles = Array.isArray(user.roles)
        ? user.roles
        : user.role
            ? [user.role]
            : []
    return roles.includes('admin') || roles.includes('a2a-admin')
}

export default function AdminUsersPage() {
    const { data: session, status } = useSession()
    const typedSession = session as any

    const [catalog, setCatalog] = useState<RoleCatalog | null>(null)
    const [users, setUsers] = useState<RBACUser[]>([])
    const [selectedUserId, setSelectedUserId] = useState<string | null>(null)
    const [draftRoles, setDraftRoles] = useState<string[]>([])
    const [search, setSearch] = useState('')
    const [loading, setLoading] = useState(true)
    const [syncing, setSyncing] = useState(false)
    const [saving, setSaving] = useState(false)
    const [rbacMetadata, setRbacMetadata] = useState<RBACMetadata | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)

    const isAdmin = useMemo(() => hasAdminRole(typedSession?.user), [typedSession])

    const getAuthToken = (): string | null => {
        const sessionToken = typedSession?.accessToken as string | undefined
        return sessionToken || getStoredToken()
    }

    const selectedUser = useMemo(
        () => users.find((user) => user.id === selectedUserId) || null,
        [users, selectedUserId]
    )

    const filteredUsers = useMemo(() => {
        const q = search.trim().toLowerCase()
        if (!q) {
            return users
        }
        return users.filter((user) => {
            return (
                user.email.toLowerCase().includes(q) ||
                user.username.toLowerCase().includes(q) ||
                (user.name || '').toLowerCase().includes(q)
            )
        })
    }, [users, search])

    const loadData = async () => {
        const token = getAuthToken()
        if (!token) {
            setLoading(false)
            setError('Sign in to manage users and roles.')
            return
        }

        try {
            const [rolesRes, usersRes] = await Promise.all([
                fetch(`${API_BASE_URL}/v1/admin/rbac/roles`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
                fetch(`${API_BASE_URL}/v1/admin/rbac/users?limit=200`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
            ])

            if (rolesRes.status === 401 || usersRes.status === 401) {
                await signOut({ callbackUrl: '/login?error=session_expired' })
                return
            }

            if (!rolesRes.ok) {
                const payload = await rolesRes.json().catch(() => ({}))
                throw new Error(payload?.detail || `Failed to load role catalog (${rolesRes.status})`)
            }
            if (!usersRes.ok) {
                const payload = await usersRes.json().catch(() => ({}))
                throw new Error(payload?.detail || `Failed to load users (${usersRes.status})`)
            }

            const rolePayload = (await rolesRes.json()) as RoleCatalog
            const usersPayload = (await usersRes.json()) as RBACUsersResponse

            setCatalog(rolePayload)
            setUsers(usersPayload.users || [])
            setRbacMetadata(usersPayload.metadata || rolePayload.metadata || null)

            const preferredUserId =
                selectedUserId && usersPayload.users.some((u) => u.id === selectedUserId)
                    ? selectedUserId
                    : usersPayload.users[0]?.id || null

            setSelectedUserId(preferredUserId)
            const nextSelected = usersPayload.users.find((u) => u.id === preferredUserId)
            setDraftRoles([...(nextSelected?.opa_roles || [])].sort())
            setError(null)
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load RBAC data')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        if (status === 'loading') {
            return
        }
        if (!isAdmin) {
            setLoading(false)
            setError('Admin role required.')
            return
        }
        loadData()
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [status, isAdmin])

    useEffect(() => {
        if (!selectedUser) {
            setDraftRoles([])
            return
        }
        setDraftRoles([...(selectedUser.opa_roles || [])].sort())
    }, [selectedUser?.id])

    const toggleRole = (role: string) => {
        const hasRole = draftRoles.includes(role)
        const next = hasRole
            ? draftRoles.filter((item) => item !== role)
            : [...draftRoles, role]
        setDraftRoles(next.sort())
    }

    const saveUserRoles = async () => {
        if (!selectedUserId) {
            return
        }
        const token = getAuthToken()
        if (!token) {
            setError('Sign in to update roles.')
            return
        }

        setSaving(true)
        setError(null)
        setSuccess(null)
        try {
            const response = await fetch(
                `${API_BASE_URL}/v1/admin/rbac/users/${encodeURIComponent(selectedUserId)}/roles`,
                {
                    method: 'PUT',
                    headers: {
                        Authorization: `Bearer ${token}`,
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        roles: draftRoles,
                        sync_missing_roles: true,
                    }),
                }
            )

            if (response.status === 401) {
                await signOut({ callbackUrl: '/login?error=session_expired' })
                return
            }
            if (!response.ok) {
                const payload = await response.json().catch(() => ({}))
                throw new Error(payload?.detail || `Failed to update roles (${response.status})`)
            }

            setSuccess('User roles updated successfully.')
            await loadData()
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to update roles')
        } finally {
            setSaving(false)
        }
    }

    const syncRolesToKeycloak = async () => {
        const token = getAuthToken()
        if (!token) {
            setError('Sign in to sync roles.')
            return
        }
        setSyncing(true)
        setError(null)
        setSuccess(null)
        try {
            const response = await fetch(`${API_BASE_URL}/v1/admin/rbac/roles/sync`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${token}` },
            })
            if (response.status === 401) {
                await signOut({ callbackUrl: '/login?error=session_expired' })
                return
            }
            if (!response.ok) {
                const payload = await response.json().catch(() => ({}))
                throw new Error(payload?.detail || `Failed to sync roles (${response.status})`)
            }
            setSuccess('OPA roles synced to Keycloak.')
            await loadData()
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to sync roles')
        } finally {
            setSyncing(false)
        }
    }

    if (loading) {
        return (
            <div className="flex h-full items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">User Management & RBAC</h1>
                    <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                        First-class Keycloak + OPA role administration for non-technical admins.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Link
                        href="/dashboard/admin/policies"
                        className="inline-flex items-center rounded-lg border border-cyan-200 bg-cyan-50 px-4 py-2 text-sm font-medium text-cyan-700 hover:bg-cyan-100 dark:border-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-300 dark:hover:bg-cyan-900/50"
                    >
                        Manage OPA Roles
                    </Link>
                    <Link
                        href="/dashboard/admin"
                        className="inline-flex items-center rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
                    >
                        Back to Admin
                    </Link>
                </div>
            </div>

            {error && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-300">
                    {error}
                </div>
            )}
            {success && (
                <div className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800 dark:border-green-900/40 dark:bg-green-950/30 dark:text-green-300">
                    {success}
                </div>
            )}

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
                <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                    <p className="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Realm</p>
                    <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-white">
                        {catalog?.realm_name || 'Unknown'}
                    </p>
                </div>
                <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                    <p className="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">OPA Roles</p>
                    <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-white">
                        {catalog?.opa_roles?.length || 0}
                    </p>
                </div>
                <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                    <div className="flex items-center justify-between">
                        <div>
                            <p className="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Missing in Keycloak</p>
                            <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-white">
                                {catalog?.missing_in_keycloak?.length || 0}
                            </p>
                        </div>
                        <button
                            onClick={syncRolesToKeycloak}
                            disabled={syncing}
                            className="rounded-lg bg-cyan-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-cyan-700 disabled:opacity-50"
                        >
                            {syncing ? 'Syncing...' : 'Sync Roles'}
                        </button>
                    </div>
                </div>
                <div className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                    <p className="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Postgres RLS</p>
                    <p className="mt-1 text-sm font-semibold text-gray-900 dark:text-white">
                        {rbacMetadata?.postgres_rls_enabled ? 'Enabled' : 'Disabled'}
                    </p>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        {rbacMetadata?.tenant_id
                            ? `Tenant: ${rbacMetadata.tenant_id}`
                            : 'No tenant scope resolved'}
                    </p>
                </div>
            </div>

            <div className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
                <section className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                    <input
                        value={search}
                        onChange={(event) => setSearch(event.target.value)}
                        placeholder="Search users..."
                        className="mb-3 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none ring-cyan-500 focus:ring-2 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
                    />
                    <div className="max-h-[560px] space-y-1 overflow-y-auto">
                        {filteredUsers.map((user) => (
                            <button
                                key={user.id}
                                onClick={() => setSelectedUserId(user.id)}
                                className={`w-full rounded-lg px-3 py-2 text-left ${
                                    user.id === selectedUserId
                                        ? 'bg-cyan-600 text-white'
                                        : 'text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-700'
                                }`}
                            >
                                <p className="truncate text-sm font-semibold">
                                    {user.name || user.email || user.username}
                                </p>
                                <p className={`truncate text-xs ${user.id === selectedUserId ? 'text-cyan-100' : 'text-gray-500 dark:text-gray-400'}`}>
                                    {user.email || user.username}
                                </p>
                                <p className={`text-xs ${user.id === selectedUserId ? 'text-cyan-100' : 'text-gray-500 dark:text-gray-400'}`}>
                                    OPA roles: {(user.opa_roles || []).join(', ') || 'none'}
                                </p>
                                <p className={`text-xs ${user.id === selectedUserId ? 'text-cyan-100' : 'text-gray-500 dark:text-gray-400'}`}>
                                    DB roles: {(user.db_opa_roles || []).join(', ') || 'none'}
                                    {user.db_synced === false ? ' (out of sync)' : ''}
                                </p>
                            </button>
                        ))}
                        {filteredUsers.length === 0 && (
                            <p className="px-2 py-4 text-xs text-gray-500 dark:text-gray-400">
                                No users found.
                            </p>
                        )}
                    </div>
                </section>

                <section className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
                    {!selectedUser ? (
                        <p className="text-sm text-gray-500 dark:text-gray-400">Select a user to manage RBAC roles.</p>
                    ) : (
                        <div className="space-y-5">
                            <div>
                                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                                    {selectedUser.name || selectedUser.email || selectedUser.username}
                                </h2>
                                <p className="text-sm text-gray-500 dark:text-gray-400">
                                    {selectedUser.email || selectedUser.username}
                                </p>
                                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                    Keycloak user id: <span className="font-mono">{selectedUser.id}</span>
                                </p>
                            </div>

                            <div>
                                <p className="mb-2 text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
                                    OPA-Managed Roles
                                </p>
                                <div className="grid gap-2 sm:grid-cols-2">
                                    {(catalog?.opa_roles || []).map((role) => (
                                        <label
                                            key={role}
                                            className="flex items-center gap-2 rounded-md border border-gray-200 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-700/60"
                                        >
                                            <input
                                                type="checkbox"
                                                checked={draftRoles.includes(role)}
                                                onChange={() => toggleRole(role)}
                                                className="h-4 w-4 rounded border-gray-300 text-cyan-600 focus:ring-cyan-500"
                                            />
                                            <span className="font-mono text-xs">{role}</span>
                                        </label>
                                    ))}
                                </div>
                            </div>

                            <div className="rounded-lg border border-gray-200 bg-gray-50 p-3 text-xs text-gray-600 dark:border-gray-700 dark:bg-gray-900/40 dark:text-gray-300">
                                <p>
                                    Saving updates writes Keycloak realm roles for this user and keeps non-OPA roles untouched.
                                </p>
                                <p className="mt-1">
                                    Postgres RLS mirror table: {rbacMetadata?.postgres_table || 'rbac_user_roles'}.
                                </p>
                            </div>

                            <div className="flex items-center gap-3">
                                <button
                                    onClick={saveUserRoles}
                                    disabled={saving}
                                    className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-700 disabled:opacity-50"
                                >
                                    {saving ? 'Saving...' : 'Save Roles'}
                                </button>
                                <button
                                    onClick={() => setDraftRoles([...(selectedUser.opa_roles || [])].sort())}
                                    disabled={saving}
                                    className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800"
                                >
                                    Reset
                                </button>
                            </div>
                        </div>
                    )}
                </section>
            </div>
        </div>
    )
}
