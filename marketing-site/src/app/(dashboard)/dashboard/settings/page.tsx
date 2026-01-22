'use client'

import { useState, useEffect } from 'react'
import { useSession } from 'next-auth/react'
import Link from 'next/link'

interface Provider {
    id: string
    name: string
    description: string
    npm: string
    has_base_url: boolean
    requires_base_url: boolean
    has_models: boolean
    auth_type: string
}

interface ApiKey {
    provider_id: string
    provider_name: string
    key_preview: string
    updated_at: string
    has_base_url: boolean
}

interface VaultStatus {
    connected: boolean
    authenticated: boolean
    vault_addr: string
    error?: string
}

interface BillingStatus {
    tier: string
    tier_name: string
    tasks_used: number
    tasks_limit: number
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

export default function SettingsPage() {
    const { data: session, status } = useSession()
    const [providers, setProviders] = useState<Provider[]>([])
    const [apiKeys, setApiKeys] = useState<ApiKey[]>([])
    const [vaultStatus, setVaultStatus] = useState<VaultStatus | null>(null)
    const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null)
    const [loading, setLoading] = useState(true)
    const [saving, setSaving] = useState(false)
    const [testing, setTesting] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [success, setSuccess] = useState<string | null>(null)

    // Form state for adding new key
    const [selectedProvider, setSelectedProvider] = useState('')
    const [apiKey, setApiKey] = useState('')
    const [baseUrl, setBaseUrl] = useState('')

    const getAuthToken = () => {
        // @ts-ignore - accessToken/idToken may be on session
        const sessionToken = session?.accessToken || session?.idToken
        if (sessionToken) {
            return sessionToken as string
        }
        if (typeof window !== 'undefined') {
            const storedToken = localStorage.getItem('a2a_token')
            if (storedToken) {
                return storedToken
            }
        }
        return null
    }

    const getAuthHeaders = () => {
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
        }
        const token = getAuthToken()
        if (token) {
            headers['Authorization'] = `Bearer ${token}`
        }
        return headers
    }

    useEffect(() => {
        if (status === 'authenticated') {
            loadData()
        }
    }, [status])

    const loadData = async () => {
        setLoading(true)
        setError(null)

        try {
            // Load providers
            const providersRes = await fetch(`${API_BASE_URL}/v1/opencode/providers`)
            if (providersRes.ok) {
                const data = await providersRes.json()
                setProviders(data.providers || [])
            }

            // Load vault status
            const vaultRes = await fetch(`${API_BASE_URL}/v1/opencode/vault/status`)
            if (vaultRes.ok) {
                const data = await vaultRes.json()
                setVaultStatus(data)
            }

            // Load user's API keys
            const keysRes = await fetch(`${API_BASE_URL}/v1/opencode/api-keys`, {
                headers: getAuthHeaders(),
            })
            if (keysRes.ok) {
                const data = await keysRes.json()
                setApiKeys(data.keys || [])
            } else if (keysRes.status === 401) {
                setError('Please sign in to manage your API keys')
            }

            // Load billing status
            const billingRes = await fetch(`${API_BASE_URL}/v1/users/billing/status`, {
                headers: getAuthHeaders(),
            })
            if (billingRes.ok) {
                const data = await billingRes.json()
                setBillingStatus(data)
            }
        } catch (err) {
            console.error('Failed to load data:', err)
            setError('Failed to load settings. Please try again.')
        } finally {
            setLoading(false)
        }
    }

    const handleSaveKey = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!selectedProvider || !apiKey) {
            setError('Please select a provider and enter an API key')
            return
        }

        setSaving(true)
        setError(null)
        setSuccess(null)

        try {
            const res = await fetch(`${API_BASE_URL}/v1/opencode/api-keys`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    provider_id: selectedProvider,
                    api_key: apiKey,
                    base_url: baseUrl || undefined,
                }),
            })

            if (res.ok) {
                const data = await res.json()
                setSuccess(data.message || 'API key saved successfully')
                setSelectedProvider('')
                setApiKey('')
                setBaseUrl('')
                loadData() // Refresh the list
            } else {
                const data = await res.json()
                setError(data.detail || 'Failed to save API key')
            }
        } catch (err) {
            console.error('Failed to save API key:', err)
            setError('Failed to save API key. Please try again.')
        } finally {
            setSaving(false)
        }
    }

    const handleTestKey = async (providerId: string) => {
        const key = apiKeys.find(k => k.provider_id === providerId)
        if (!key) return

        setTesting(providerId)
        setError(null)
        setSuccess(null)

        try {
            // For testing, we need the user to provide the full key
            // This is a simplified test using the existing key
            const res = await fetch(`${API_BASE_URL}/v1/opencode/api-keys/test`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    provider_id: providerId,
                    api_key: apiKey || 'test', // Placeholder - in real UI, prompt for key
                }),
            })

            const data = await res.json()
            if (data.success) {
                setSuccess(data.message)
            } else {
                setError(data.message || 'API key test failed')
            }
        } catch (err) {
            console.error('Failed to test API key:', err)
            setError('Failed to test API key')
        } finally {
            setTesting(null)
        }
    }

    const handleDeleteKey = async (providerId: string) => {
        if (!confirm(`Are you sure you want to delete the API key for ${providerId}?`)) {
            return
        }

        setError(null)
        setSuccess(null)

        try {
            const res = await fetch(`${API_BASE_URL}/v1/opencode/api-keys/${providerId}`, {
                method: 'DELETE',
                headers: getAuthHeaders(),
            })

            if (res.ok) {
                setSuccess('API key deleted successfully')
                loadData()
            } else {
                const data = await res.json()
                setError(data.detail || 'Failed to delete API key')
            }
        } catch (err) {
            console.error('Failed to delete API key:', err)
            setError('Failed to delete API key')
        }
    }

    if (status === 'loading' || loading) {
        return (
            <div className="flex items-center justify-center min-h-100">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
            </div>
        )
    }

    if (status === 'unauthenticated') {
        return (
            <div className="text-center py-12">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
                    Sign in to manage your settings
                </h2>
                <p className="text-gray-600 dark:text-gray-400">
                    You need to be signed in to manage your API keys and preferences.
                </p>
            </div>
        )
    }

    const selectedProviderInfo = providers.find(p => p.id === selectedProvider)

    const usagePercent = billingStatus
        ? Math.min(100, Math.round((billingStatus.tasks_used / billingStatus.tasks_limit) * 100))
        : 0

    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Settings</h1>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                    Manage your account, billing, and API keys
                </p>
            </div>

            {/* Billing Summary Card */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                    <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                        Subscription & Usage
                    </h2>
                    <Link
                        href="/dashboard/billing"
                        className="text-sm font-medium text-cyan-600 hover:text-cyan-500"
                    >
                        Manage billing &rarr;
                    </Link>
                </div>
                <div className="p-6">
                    {billingStatus ? (
                        <div className="space-y-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <span className="text-sm text-gray-600 dark:text-gray-400">Current plan</span>
                                    <div className="text-lg font-semibold text-gray-900 dark:text-white">
                                        {billingStatus.tier_name}
                                    </div>
                                </div>
                                {billingStatus.tier === 'free' && (
                                    <Link
                                        href="/dashboard/billing"
                                        className="px-4 py-2 bg-cyan-600 text-white text-sm font-medium rounded-md hover:bg-cyan-700"
                                    >
                                        Upgrade to Pro
                                    </Link>
                                )}
                            </div>
                            <div>
                                <div className="flex items-center justify-between text-sm">
                                    <span className="text-gray-600 dark:text-gray-400">Tasks this month</span>
                                    <span className="font-medium text-gray-900 dark:text-white">
                                        {billingStatus.tasks_used} / {billingStatus.tasks_limit}
                                    </span>
                                </div>
                                <div className="mt-2 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                    <div
                                        className={`h-full rounded-full transition-all ${usagePercent >= 90
                                                ? 'bg-red-500'
                                                : usagePercent >= 75
                                                    ? 'bg-yellow-500'
                                                    : 'bg-cyan-500'
                                            }`}
                                        style={{ width: `${usagePercent}%` }}
                                    />
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div className="text-sm text-gray-500">Loading billing info...</div>
                    )}
                </div>
            </div>

            {/* Vault Status */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
                <h2 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                    Secrets Storage Status
                </h2>
                {vaultStatus ? (
                    <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                            <span
                                className={`h-3 w-3 rounded-full ${vaultStatus.connected && vaultStatus.authenticated
                                        ? 'bg-green-500'
                                        : 'bg-red-500'
                                    }`}
                            />
                            <span className="text-sm text-gray-600 dark:text-gray-400">
                                {vaultStatus.connected && vaultStatus.authenticated
                                    ? 'Connected to HashiCorp Vault'
                                    : 'Vault unavailable'}
                            </span>
                        </div>
                        {vaultStatus.error && (
                            <span className="text-sm text-red-600">{vaultStatus.error}</span>
                        )}
                    </div>
                ) : (
                    <span className="text-sm text-gray-500">Checking status...</span>
                )}
            </div>

            {/* Error/Success Messages */}
            {error && (
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                    <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
                </div>
            )}
            {success && (
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
                    <p className="text-sm text-green-800 dark:text-green-200">{success}</p>
                </div>
            )}

            {/* Current API Keys */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                    <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                        Your API Keys
                    </h2>
                    <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                        API keys are securely stored in HashiCorp Vault and synced to your workers.
                    </p>
                </div>

                {apiKeys.length === 0 ? (
                    <div className="p-6 text-center text-gray-500 dark:text-gray-400">
                        No API keys configured. Add one below to get started.
                    </div>
                ) : (
                    <ul className="divide-y divide-gray-200 dark:divide-gray-700">
                        {apiKeys.map(key => (
                            <li key={key.provider_id} className="p-6 flex items-center justify-between">
                                <div>
                                    <h3 className="text-sm font-medium text-gray-900 dark:text-white">
                                        {key.provider_name}
                                    </h3>
                                    <p className="text-sm text-gray-500 dark:text-gray-400">
                                        Key: {key.key_preview}
                                        {key.updated_at && (
                                            <span className="ml-2">
                                                Updated: {new Date(key.updated_at).toLocaleDateString()}
                                            </span>
                                        )}
                                    </p>
                                </div>
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => handleDeleteKey(key.provider_id)}
                                        className="px-3 py-1 text-sm text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300"
                                    >
                                        Delete
                                    </button>
                                </div>
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            {/* Add New API Key */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                    <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                        Add API Key
                    </h2>
                    <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                        Add a new LLM provider API key to use with your agents.
                    </p>
                </div>

                <form onSubmit={handleSaveKey} className="p-6 space-y-4">
                    <div>
                        <label
                            htmlFor="provider"
                            className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                        >
                            Provider
                        </label>
                        <select
                            id="provider"
                            value={selectedProvider}
                            onChange={e => setSelectedProvider(e.target.value)}
                            className="mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                        >
                            <option value="">Select a provider...</option>
                            {providers.map(provider => (
                                <option key={provider.id} value={provider.id}>
                                    {provider.name} - {provider.description}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label
                            htmlFor="apiKey"
                            className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                        >
                            API Key
                        </label>
                        <input
                            type="password"
                            id="apiKey"
                            value={apiKey}
                            onChange={e => setApiKey(e.target.value)}
                            placeholder="Enter your API key"
                            className="mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                        />
                    </div>

                    {selectedProviderInfo?.requires_base_url && (
                        <div>
                            <label
                                htmlFor="baseUrl"
                                className="block text-sm font-medium text-gray-700 dark:text-gray-300"
                            >
                                Base URL (required)
                            </label>
                            <input
                                type="url"
                                id="baseUrl"
                                value={baseUrl}
                                onChange={e => setBaseUrl(e.target.value)}
                                placeholder="https://your-endpoint.example.com/v1"
                                className="mt-1 block w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
                            />
                            <p className="mt-1 text-xs text-gray-500">
                                This provider requires a custom endpoint URL.
                            </p>
                        </div>
                    )}

                    <div className="flex gap-4">
                        <button
                            type="submit"
                            disabled={saving || !selectedProvider || !apiKey}
                            className="px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {saving ? 'Saving...' : 'Save API Key'}
                        </button>
                        <button
                            type="button"
                            onClick={() => handleTestKey(selectedProvider)}
                            disabled={testing !== null || !selectedProvider || !apiKey}
                            className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-md hover:bg-gray-300 dark:hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {testing === selectedProvider ? 'Testing...' : 'Test Key'}
                        </button>
                    </div>
                </form>
            </div>

            {/* Available Providers Reference */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                    <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                        Supported Providers
                    </h2>
                </div>
                <div className="p-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {providers.map(provider => (
                            <div
                                key={provider.id}
                                className="p-4 border border-gray-200 dark:border-gray-700 rounded-lg"
                            >
                                <h3 className="font-medium text-gray-900 dark:text-white">
                                    {provider.name}
                                </h3>
                                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                                    {provider.description}
                                </p>
                                {provider.auth_type === 'oauth' && (
                                    <span className="inline-block mt-2 px-2 py-1 text-xs bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded">
                                        OAuth
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    )
}
