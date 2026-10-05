'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { signOut, useSession } from 'next-auth/react'

interface PolicyRole {
    description: string
    permissions: string[]
    inherits?: string | null
}

interface PolicyMetadata {
    opa_local_mode: boolean
    changes_apply_immediately: boolean
    reload_required: boolean
    data_file: string
    writable: boolean
    updated_at?: string | null
}

interface PolicyData {
    roles: Record<string, PolicyRole>
    permissions: string[]
    permissions_by_resource: Record<string, string[]>
    metadata: PolicyMetadata
}

interface RoleDraft {
    name: string
    description: string
    mode: 'custom' | 'inherit'
    inherits: string
    permissions: string[]
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const ROLE_NAME_PATTERN = /^[a-z0-9][a-z0-9_-]{1,63}$/
const PRIORITY_ROLE_ORDER = ['admin', 'a2a-admin', 'operator', 'editor', 'viewer']

const uniqueSorted = (items: string[]) =>
    Array.from(new Set(items.filter(Boolean))).sort((a, b) => a.localeCompare(b))

const toRoleDraft = (name: string, role: PolicyRole): RoleDraft => {
    if (role.inherits) {
        return {
            name,
            description: role.description || '',
            mode: 'inherit',
            inherits: role.inherits,
            permissions: [],
        }
    }
    return {
        name,
        description: role.description || '',
        mode: 'custom',
        inherits: '',
        permissions: uniqueSorted(role.permissions || []),
    }
}

const getStoredUser = (): any => {
    if (typeof window === 'undefined') {
        return null
    }
    try {
        const raw = localStorage.getItem('a2a_user')
        return raw ? JSON.parse(raw) : null
    } catch {
        return null
    }
}

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
    const roles: string[] = Array.isArray(user.roles)
        ? user.roles
        : user.role
            ? [user.role]
            : []
    return roles.includes('admin') || roles.includes('a2a-admin')
}

export default function AdminPoliciesPage() {
    const { data: session, status } = useSession()
    const typedSession = session as any

    const [policyData, setPolicyData] = useState<PolicyData | null>(null)
    const [selectedRole, setSelectedRole] = useState<string | null>(null)
    const [draft, setDraft] = useState<RoleDraft | null>(null)
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)
    const [roleQuery, setRoleQuery] = useState('')
    const [permissionQuery, setPermissionQuery] = useState('')

    const getAuthToken = (): string | null => {
        const sessionToken = typedSession?.accessToken
        if (sessionToken) {
            return sessionToken as string
        }
        return getStoredToken()
    }

    const isAdmin = useMemo(() => {
        return hasAdminRole(typedSession?.user) || hasAdminRole(getStoredUser())
    }, [typedSession])

    const loadPolicyData = async (preferredRole?: string) => {
        const token = getAuthToken()
        if (!token) {
            setError('Sign in to manage policy roles.')
            setLoading(false)
            return
        }

        try {
            const response = await fetch(`${API_BASE_URL}/v1/admin/policy/rbac`, {
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            })

            if (response.status === 401) {
                await signOut({ callbackUrl: '/login?error=session_expired' })
                return
            }

            if (!response.ok) {
                const payload = await response.json().catch(() => ({}))
                throw new Error(payload?.detail || `Failed to load policy roles (${response.status})`)
            }

            const payload = (await response.json()) as PolicyData
            setPolicyData(payload)

            const roleNames = Object.keys(payload.roles || {})
            const nextRole =
                (preferredRole && roleNames.includes(preferredRole) && preferredRole) ||
                (selectedRole && roleNames.includes(selectedRole) && selectedRole) ||
                PRIORITY_ROLE_ORDER.find((name) => roleNames.includes(name)) ||
                roleNames.sort((a, b) => a.localeCompare(b))[0] ||
                null

            setSelectedRole(nextRole)
            setDraft(nextRole ? toRoleDraft(nextRole, payload.roles[nextRole]) : null)
            setError(null)
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load policy roles')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        if (status === 'loading') {
            return
        }
        if (!isAdmin) {
            setError('Admin role required to edit OPA policies.')
            setLoading(false)
            return
        }
        loadPolicyData()
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [status, isAdmin])

    const orderedRoleNames = useMemo(() => {
        if (!policyData?.roles) {
            return []
        }
        const all = Object.keys(policyData.roles)
        const priority = PRIORITY_ROLE_ORDER.filter((name) => all.includes(name))
        const remaining = all
            .filter((name) => !priority.includes(name))
            .sort((a, b) => a.localeCompare(b))
        return [...priority, ...remaining]
    }, [policyData])

    const filteredRoleNames = useMemo(() => {
        if (!roleQuery.trim()) {
            return orderedRoleNames
        }
        const query = roleQuery.trim().toLowerCase()
        return orderedRoleNames.filter((name) => {
            const role = policyData?.roles[name]
            const description = role?.description?.toLowerCase() || ''
            return name.toLowerCase().includes(query) || description.includes(query)
        })
    }, [orderedRoleNames, policyData, roleQuery])

    const filteredPermissionsByResource = useMemo(() => {
        const source = policyData?.permissions_by_resource || {}
        const query = permissionQuery.trim().toLowerCase()
        const grouped: Record<string, string[]> = {}

        Object.entries(source).forEach(([resource, permissions]) => {
            const matches = permissions.filter((permission) =>
                query ? permission.toLowerCase().includes(query) : true
            )
            if (matches.length > 0) {
                grouped[resource] = matches
            }
        })

        return grouped
    }, [policyData, permissionQuery])

    const selectRole = (roleName: string) => {
        if (!policyData?.roles[roleName]) {
            return
        }
        setSelectedRole(roleName)
        setDraft(toRoleDraft(roleName, policyData.roles[roleName]))
        setSuccess(null)
        setError(null)
    }

    const createRoleDraft = () => {
        if (!policyData) {
            return
        }
        let candidate = 'custom-role'
        let index = 1
        while (policyData.roles[candidate]) {
            candidate = `custom-role-${index}`
            index += 1
        }

        setSelectedRole(null)
        setDraft({
            name: candidate,
            description: '',
            mode: 'custom',
            inherits: '',
            permissions: [],
        })
        setSuccess(null)
        setError(null)
    }

    const togglePermission = (permission: string) => {
        if (!draft || draft.mode !== 'custom') {
            return
        }
        const hasPermission = draft.permissions.includes(permission)
        const next = hasPermission
            ? draft.permissions.filter((item) => item !== permission)
            : [...draft.permissions, permission]

        setDraft({
            ...draft,
            permissions: uniqueSorted(next),
        })
    }

    const resetDraft = () => {
        if (!policyData || !selectedRole) {
            return
        }
        setDraft(toRoleDraft(selectedRole, policyData.roles[selectedRole]))
        setSuccess(null)
        setError(null)
    }

    const saveRole = async () => {
        if (!draft) {
            return
        }
        if (!ROLE_NAME_PATTERN.test(draft.name)) {
            setError('Role name must be 2-64 chars: lowercase letters, numbers, "_" or "-".')
            return
        }
        if (draft.mode === 'inherit' && !draft.inherits) {
            setError('Pick a parent role when using inherited mode.')
            return
        }
        if (draft.mode === 'custom' && draft.permissions.length === 0) {
            setError('Custom roles need at least one permission.')
            return
        }

        const token = getAuthToken()
        if (!token) {
            setError('Sign in to save policy changes.')
            return
        }

        setSaving(true)
        setError(null)
        setSuccess(null)

        try {
            const response = await fetch(
                `${API_BASE_URL}/v1/admin/policy/roles/${encodeURIComponent(draft.name)}`,
                {
                    method: 'PUT',
                    headers: {
                        Authorization: `Bearer ${token}`,
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        description: draft.description,
                        inherits: draft.mode === 'inherit' ? draft.inherits : null,
                        permissions: draft.mode === 'custom' ? draft.permissions : [],
                    }),
                }
            )

            if (response.status === 401) {
                await signOut({ callbackUrl: '/login?error=session_expired' })
                return
            }

            if (!response.ok) {
                const payload = await response.json().catch(() => ({}))
                throw new Error(payload?.detail || `Failed to save role (${response.status})`)
            }

            const payload = (await response.json()) as {
                metadata?: PolicyMetadata
            }
            const modeText = payload?.metadata?.changes_apply_immediately
                ? 'Changes are active now (local OPA mode).'
                : 'Role saved. Reload/redeploy OPA to apply sidecar changes.'

            setSuccess(`Saved role "${draft.name}". ${modeText}`)
            await loadPolicyData(draft.name)
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to save role')
        } finally {
            setSaving(false)
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
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Policy Editor</h1>
                    <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                        Manage OPA RBAC roles with guided controls instead of editing Rego or JSON.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Link
                        href="/dashboard/admin/users"
                        className="inline-flex items-center rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-100 dark:border-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300 dark:hover:bg-emerald-900/50"
                    >
                        User Management
                    </Link>
                    <Link
                        href="/dashboard/admin"
                        className="inline-flex items-center rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
                    >
                        Back to Admin Dashboard
                    </Link>
                </div>
            </div>

            {policyData?.metadata && (
                <div
                    className={`rounded-xl border px-4 py-3 text-sm ${
                        policyData.metadata.changes_apply_immediately
                            ? 'border-green-200 bg-green-50 text-green-800 dark:border-green-900/40 dark:bg-green-950/30 dark:text-green-300'
                            : 'border-yellow-200 bg-yellow-50 text-yellow-800 dark:border-yellow-900/40 dark:bg-yellow-950/30 dark:text-yellow-300'
                    }`}
                >
                    <p className="font-semibold">
                        {policyData.metadata.changes_apply_immediately
                            ? 'Local mode detected'
                            : 'OPA sidecar mode detected'}
                    </p>
                    <p>
                        {policyData.metadata.changes_apply_immediately
                            ? 'Role updates apply immediately.'
                            : 'Role updates are saved, but OPA sidecar reload/redeploy is required.'}
                    </p>
                </div>
            )}

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

            <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
                <aside className="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
                    <div className="mb-3 flex items-center justify-between">
                        <h2 className="text-sm font-semibold text-gray-900 dark:text-white">Roles</h2>
                        <button
                            onClick={createRoleDraft}
                            className="rounded-md bg-cyan-600 px-2.5 py-1 text-xs font-semibold text-white hover:bg-cyan-700"
                        >
                            New
                        </button>
                    </div>
                    <input
                        value={roleQuery}
                        onChange={(event) => setRoleQuery(event.target.value)}
                        placeholder="Search roles..."
                        className="mb-3 w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none ring-cyan-500 focus:ring-2 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
                    />
                    <div className="max-h-[560px] space-y-1 overflow-y-auto pr-1">
                        {filteredRoleNames.map((roleName) => (
                            <button
                                key={roleName}
                                onClick={() => selectRole(roleName)}
                                className={`w-full rounded-lg px-3 py-2 text-left text-sm ${
                                    selectedRole === roleName
                                        ? 'bg-cyan-600 text-white'
                                        : 'text-gray-700 hover:bg-gray-100 dark:text-gray-200 dark:hover:bg-gray-700'
                                }`}
                            >
                                <p className="font-medium">{roleName}</p>
                                <p
                                    className={`text-xs ${
                                        selectedRole === roleName
                                            ? 'text-cyan-100'
                                            : 'text-gray-500 dark:text-gray-400'
                                    }`}
                                >
                                    {policyData?.roles[roleName]?.inherits
                                        ? `Inherits ${policyData.roles[roleName].inherits}`
                                        : `${policyData?.roles[roleName]?.permissions?.length || 0} permissions`}
                                </p>
                            </button>
                        ))}
                        {filteredRoleNames.length === 0 && (
                            <p className="px-2 py-4 text-xs text-gray-500 dark:text-gray-400">
                                No matching roles.
                            </p>
                        )}
                    </div>
                </aside>

                <section className="rounded-xl border border-gray-200 bg-white p-6 dark:border-gray-700 dark:bg-gray-800">
                    {!draft ? (
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                            Select a role on the left or create a new one.
                        </p>
                    ) : (
                        <div className="space-y-5">
                            <div className="grid gap-4 sm:grid-cols-2">
                                <label className="space-y-1">
                                    <span className="text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-400">
                                        Role Name
                                    </span>
                                    <input
                                        value={draft.name}
                                        onChange={(event) =>
                                            setDraft({
                                                ...draft,
                                                name: event.target.value.trim().toLowerCase(),
                                            })
                                        }
                                        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none ring-cyan-500 focus:ring-2 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
                                    />
                                </label>
                                <label className="space-y-1">
                                    <span className="text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-400">
                                        Description
                                    </span>
                                    <input
                                        value={draft.description}
                                        onChange={(event) =>
                                            setDraft({ ...draft, description: event.target.value })
                                        }
                                        placeholder="What this role can do"
                                        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none ring-cyan-500 focus:ring-2 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
                                    />
                                </label>
                            </div>

                            <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-900/40">
                                <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-400">
                                    Access Model
                                </p>
                                <div className="grid gap-3 sm:grid-cols-2">
                                    <button
                                        onClick={() =>
                                            setDraft({
                                                ...draft,
                                                mode: 'custom',
                                                inherits: '',
                                            })
                                        }
                                        className={`rounded-lg border px-3 py-2 text-left text-sm ${
                                            draft.mode === 'custom'
                                                ? 'border-cyan-500 bg-cyan-50 text-cyan-800 dark:border-cyan-400 dark:bg-cyan-950/30 dark:text-cyan-300'
                                                : 'border-gray-300 bg-white text-gray-700 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200'
                                        }`}
                                    >
                                        <p className="font-semibold">Custom permissions</p>
                                        <p className="text-xs opacity-80">Pick exact capabilities.</p>
                                    </button>
                                    <button
                                        onClick={() =>
                                            setDraft({
                                                ...draft,
                                                mode: 'inherit',
                                                permissions: [],
                                                inherits:
                                                    draft.inherits ||
                                                    orderedRoleNames.find((name) => name !== draft.name) ||
                                                    '',
                                            })
                                        }
                                        className={`rounded-lg border px-3 py-2 text-left text-sm ${
                                            draft.mode === 'inherit'
                                                ? 'border-cyan-500 bg-cyan-50 text-cyan-800 dark:border-cyan-400 dark:bg-cyan-950/30 dark:text-cyan-300'
                                                : 'border-gray-300 bg-white text-gray-700 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200'
                                        }`}
                                    >
                                        <p className="font-semibold">Inherit another role</p>
                                        <p className="text-xs opacity-80">Reuse a pre-approved role.</p>
                                    </button>
                                </div>
                            </div>

                            {draft.mode === 'inherit' ? (
                                <label className="space-y-1">
                                    <span className="text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-400">
                                        Parent Role
                                    </span>
                                    <select
                                        value={draft.inherits}
                                        onChange={(event) =>
                                            setDraft({ ...draft, inherits: event.target.value })
                                        }
                                        className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none ring-cyan-500 focus:ring-2 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
                                    >
                                        <option value="">Select role...</option>
                                        {orderedRoleNames
                                            .filter((name) => name !== draft.name)
                                            .map((name) => (
                                                <option key={name} value={name}>
                                                    {name}
                                                </option>
                                            ))}
                                    </select>
                                </label>
                            ) : (
                                <div className="space-y-3">
                                    <div className="flex items-center justify-between">
                                        <p className="text-xs font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-400">
                                            Permissions ({draft.permissions.length} selected)
                                        </p>
                                        <input
                                            value={permissionQuery}
                                            onChange={(event) =>
                                                setPermissionQuery(event.target.value)
                                            }
                                            placeholder="Filter permissions..."
                                            className="w-56 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 outline-none ring-cyan-500 focus:ring-2 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
                                        />
                                    </div>
                                    <div className="max-h-[420px] space-y-4 overflow-y-auto rounded-lg border border-gray-200 p-4 dark:border-gray-700">
                                        {Object.entries(filteredPermissionsByResource).map(
                                            ([resource, permissions]) => (
                                                <div key={resource}>
                                                    <p className="mb-2 text-sm font-semibold text-gray-800 dark:text-gray-100">
                                                        {resource}
                                                    </p>
                                                    <div className="grid gap-2 sm:grid-cols-2">
                                                        {permissions.map((permission) => (
                                                            <label
                                                                key={permission}
                                                                className="flex items-center gap-2 rounded-md border border-gray-200 px-2 py-1.5 text-sm text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-700/50"
                                                            >
                                                                <input
                                                                    type="checkbox"
                                                                    checked={draft.permissions.includes(
                                                                        permission
                                                                    )}
                                                                    onChange={() =>
                                                                        togglePermission(permission)
                                                                    }
                                                                    className="h-4 w-4 rounded border-gray-300 text-cyan-600 focus:ring-cyan-500"
                                                                />
                                                                <span className="font-mono text-xs">
                                                                    {permission}
                                                                </span>
                                                            </label>
                                                        ))}
                                                    </div>
                                                </div>
                                            )
                                        )}
                                        {Object.keys(filteredPermissionsByResource).length === 0 && (
                                            <p className="text-sm text-gray-500 dark:text-gray-400">
                                                No permissions match your filter.
                                            </p>
                                        )}
                                    </div>
                                </div>
                            )}

                            <div className="flex flex-wrap items-center gap-3 pt-1">
                                <button
                                    onClick={saveRole}
                                    disabled={saving || !policyData?.metadata.writable}
                                    className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-700 disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                    {saving ? 'Saving...' : 'Save Role'}
                                </button>
                                <button
                                    onClick={resetDraft}
                                    disabled={!selectedRole || saving}
                                    className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800"
                                >
                                    Reset
                                </button>
                                {!policyData?.metadata.writable && (
                                    <p className="text-xs text-red-600 dark:text-red-400">
                                        Policy file is not writable by this server process.
                                    </p>
                                )}
                            </div>
                        </div>
                    )}
                </section>
            </div>
        </div>
    )
}
