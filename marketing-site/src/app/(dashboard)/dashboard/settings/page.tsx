'use client'

import { useState, useEffect } from 'react'
import { useSession } from 'next-auth/react'
import Link from 'next/link'
import { getApiAuth } from '@/lib/auth-token'
import {
  nonNegativeNumber,
  quotaNumber,
  formatNumber,
  formatQuota,
  usagePercentage,
  subscriptionPlan,
} from '@/lib/billing-display'
import {
  listProvidersV1AgentProvidersGet,
  vaultStatusV1AgentVaultStatusGet,
  listApiKeysV1AgentApiKeysGet,
  createOrUpdateApiKeyV1AgentApiKeysPost,
  deleteApiKeyV1AgentApiKeysProviderIdDelete,
  testApiKeyEndpointV1AgentApiKeysTestPost,
  getSubscriptionV1BillingSubscriptionGet,
  getUsageV1BillingUsageGet,
  client,
} from '@/lib/api'

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
  authorized?: boolean
  authorization_error?: string
  authorization_status?: number
  error?: string
}

interface BillingStatus {
  tier: string
  tier_name: string
  tasks_used: number | null
  tasks_limit: number | null
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

const errorDetail = (error: unknown, fallback: string) => {
  if (
    error &&
    typeof error === 'object' &&
    'detail' in error &&
    typeof error.detail === 'string'
  ) {
    return error.detail
  }
  return fallback
}

const getAuthHeaders = () => {
  const headers: Record<string, string> = {}
  if (typeof window !== 'undefined') {
    const storedToken = localStorage.getItem('a2a_token')
    if (storedToken) {
      headers['Authorization'] = `Bearer ${storedToken}`
    }
  }
  return headers
}

export default function SettingsPage() {
  const { data: session, status } = useSession()
  const [providers, setProviders] = useState<Provider[]>([])
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([])
  const [vaultStatus, setVaultStatus] = useState<VaultStatus | null>(null)
  const [vaultAccessError, setVaultAccessError] = useState<string | null>(null)
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const [selectedProvider, setSelectedProvider] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [baseUrlInput, setBaseUrlInput] = useState('')

  const { token: authToken } = getApiAuth(session)
  const getAuthToken = () => authToken || null

  useEffect(() => {
    if (status !== 'loading' && authToken) {
      loadData()
    }
  }, [status, authToken])

  const loadData = async () => {
    setLoading(true)
    setError(null)
    setVaultAccessError(null)

    try {
      const token = getAuthToken()
      const headers: Record<string, string> = {}
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const [providersRes, vaultRes, keysRes, billingRes, usageRes] =
        await Promise.all([
          listProvidersV1AgentProvidersGet(),
          token
            ? vaultStatusV1AgentVaultStatusGet({ headers })
            : vaultStatusV1AgentVaultStatusGet(),
          token
            ? listApiKeysV1AgentApiKeysGet({ headers })
            : Promise.resolve({ data: undefined, error: undefined }),
          token
            ? getSubscriptionV1BillingSubscriptionGet({ headers })
            : Promise.resolve({ data: undefined, error: undefined }),
          token
            ? getUsageV1BillingUsageGet({ headers })
            : Promise.resolve({ data: undefined, error: undefined }),
        ])

      if (!providersRes.error && providersRes.data) {
        const response = providersRes.data as any
        setProviders(
          Array.isArray(response) ? response : (response?.providers ?? []),
        )
      }

      if (!vaultRes.error && vaultRes.data) {
        setVaultStatus(vaultRes.data as any)
      }

      if (!keysRes.error && keysRes.data) {
        const response = keysRes.data as any
        setApiKeys(Array.isArray(response) ? response : (response?.keys ?? []))
        if (response?.vault_error) {
          setVaultAccessError(response.vault_error)
        }
      } else if (
        keysRes.error &&
        typeof keysRes.error === 'object' &&
        'status' in keysRes.error &&
        (keysRes.error as any).status === 401
      ) {
        setError('Please sign in to manage your API keys')
      } else if (keysRes.error) {
        setError((keysRes.error as any)?.detail || 'Failed to load API keys')
      }

      if (!billingRes.error && billingRes.data) {
        const response = billingRes.data as any
        const usage = !usageRes?.error ? (usageRes?.data as any) : undefined
        setBillingStatus({
          ...subscriptionPlan(response),
          tasks_used: nonNegativeNumber(usage?.tasks_used),
          tasks_limit:
            quotaNumber(usage?.tasks_limit) ??
            quotaNumber(response.tasks_limit),
        })
      }
    } catch (err) {
      console.error('Failed to load data:', err)
      setError('Failed to load settings. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const validateKeyInput = () => {
    if (!selectedProvider || !apiKey.trim())
      return 'Please select a provider and enter an API key'
    const provider = providers.find((p) => p.id === selectedProvider)
    if (provider?.requires_base_url && !baseUrlInput.trim())
      return 'Please enter the provider base URL'
    if (baseUrlInput.trim()) {
      try {
        const url = new URL(baseUrlInput.trim())
        if (!['http:', 'https:'].includes(url.protocol))
          return 'Base URL must use HTTP or HTTPS'
      } catch {
        return 'Please enter a valid base URL'
      }
    }
    return null
  }

  const clearFeedback = () => {
    setError(null)
    setSuccess(null)
  }

  const handleSaveKey = async (e: React.FormEvent) => {
    e.preventDefault()
    if (saving || testing !== null) return
    clearFeedback()
    const inputError = validateKeyInput()
    if (inputError) {
      setError(inputError)
      return
    }

    setSaving(true)
    setError(null)
    setSuccess(null)

    try {
      const token = getAuthToken()
      const headers: Record<string, string> = {}
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const { error, data } = await createOrUpdateApiKeyV1AgentApiKeysPost({
        headers,
        body: {
          provider_id: selectedProvider,
          api_key: apiKey.trim(),
          ...(baseUrlInput.trim() && { base_url: baseUrlInput.trim() }),
        },
      })

      if (!error) {
        setSuccess(
          typeof (data as any)?.message === 'string'
            ? (data as any).message
            : 'API key saved successfully',
        )
        setSelectedProvider('')
        setApiKey('')
        setBaseUrlInput('')
        loadData()
      } else {
        setError(
          errorDetail(error, 'Failed to save API key. Please try again.'),
        )
      }
    } catch (err) {
      console.error('Failed to save API key:', err)
      setError('Failed to save API key. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  const handleTestKey = async () => {
    if (saving || testing !== null) return
    clearFeedback()
    const inputError = validateKeyInput()
    if (inputError) {
      setError(inputError)
      return
    }
    // The server currently tests only its built-in provider endpoints.
    if (
      baseUrlInput.trim() ||
      providers.find((p) => p.id === selectedProvider)?.requires_base_url
    ) {
      setError(
        'Custom endpoint testing is not supported yet. You can save this key, but its connection has not been tested.',
      )
      return
    }
    const providerId = selectedProvider

    setTesting(providerId)
    setError(null)
    setSuccess(null)

    try {
      const token = getAuthToken()
      const headers: Record<string, string> = {}
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const { error, data } = await testApiKeyEndpointV1AgentApiKeysTestPost({
        headers,
        body: {
          provider_id: providerId,
          api_key: apiKey.trim(),
        },
      })

      const response = data as any
      if (!error && response?.tested === false) {
        setError(
          'No connection test is available for this provider. This action has not saved or verified the key.',
        )
      } else if (!error && response?.success === true) {
        setSuccess(
          typeof response?.message === 'string'
            ? response.message
            : 'API key test passed',
        )
      } else {
        setError(
          typeof response?.message === 'string'
            ? response.message
            : errorDetail(
                error,
                'API key test failed. Check the key and try again.',
              ),
        )
      }
    } catch (err) {
      console.error('Failed to test API key:', err)
      setError('Failed to test API key')
    } finally {
      setTesting(null)
    }
  }

  const handleDeleteKey = async (providerId: string) => {
    if (
      !confirm(`Are you sure you want to delete the API key for ${providerId}?`)
    ) {
      return
    }

    setError(null)
    setSuccess(null)

    try {
      const token = getAuthToken()
      const headers: Record<string, string> = {}
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const { error } = await deleteApiKeyV1AgentApiKeysProviderIdDelete({
        path: { provider_id: providerId },
        headers,
      })

      if (!error) {
        setSuccess('API key deleted successfully')
        loadData()
      } else {
        setError(errorDetail(error, 'Failed to delete API key'))
      }
    } catch (err) {
      console.error('Failed to delete API key:', err)
      setError('Failed to delete API key')
    }
  }

  if (status === 'loading' || (loading && authToken)) {
    return (
      <div className="flex min-h-100 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-indigo-600" />
      </div>
    )
  }

  if (!authToken) {
    return (
      <div className="py-12 text-center">
        <h2 className="mb-4 text-xl font-semibold text-gray-900 dark:text-white">
          Sign in to manage your settings
        </h2>
        <p className="text-gray-600 dark:text-gray-400">
          You need to be signed in to manage your API keys and preferences.
        </p>
      </div>
    )
  }

  const selectedProviderInfo = providers.find((p) => p.id === selectedProvider)
  const vaultAuthorizationError =
    vaultAccessError || vaultStatus?.authorization_error || null
  const vaultConnected = !!(
    vaultStatus?.connected && vaultStatus?.authenticated
  )
  const vaultReady =
    vaultConnected &&
    !vaultAuthorizationError &&
    vaultStatus?.authorized !== false

  const usagePercent = usagePercentage(
    billingStatus?.tasks_used,
    billingStatus?.tasks_limit,
  )

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Settings
        </h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
          Manage your account, billing, and API keys
        </p>
      </div>

      {/* Billing Summary Card */}
      <div className="rounded-lg bg-white shadow dark:bg-gray-800">
        <div className="flex items-center justify-between border-b border-gray-200 p-6 dark:border-gray-700">
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
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    Current plan
                  </span>
                  <div className="text-lg font-semibold text-gray-900 dark:text-white">
                    {billingStatus.tier_name}
                  </div>
                </div>
                {billingStatus.tier === 'free' && (
                  <Link
                    href="/dashboard/billing"
                    className="rounded-md bg-cyan-600 px-4 py-2 text-sm font-medium text-white hover:bg-cyan-700"
                  >
                    Upgrade to Pro
                  </Link>
                )}
              </div>
              <div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">
                    Tasks this month
                  </span>
                  <span className="font-medium text-gray-900 dark:text-white">
                    {formatNumber(billingStatus.tasks_used)} /{' '}
                    {formatQuota(billingStatus.tasks_limit)}
                  </span>
                </div>
                <div
                  hidden={
                    billingStatus.tasks_used == null ||
                    billingStatus.tasks_limit == null ||
                    billingStatus.tasks_limit === -1
                  }
                  className="mt-2 h-2 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700"
                >
                  <div
                    className={`h-full rounded-full transition-all ${
                      usagePercent >= 90
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
      <div className="rounded-lg bg-white p-6 shadow dark:bg-gray-800">
        <h2 className="mb-4 text-lg font-medium text-gray-900 dark:text-white">
          Secrets Storage Status
        </h2>
        {vaultStatus ? (
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span
                className={`h-3 w-3 rounded-full ${
                  vaultReady
                    ? 'bg-green-500'
                    : vaultConnected
                      ? 'bg-yellow-500'
                      : 'bg-red-500'
                }`}
              />
              <span className="text-sm text-gray-600 dark:text-gray-400">
                {vaultReady
                  ? 'Connected to HashiCorp Vault'
                  : vaultConnected
                    ? 'Connected to Vault, but API key access is blocked'
                    : 'Vault unavailable'}
              </span>
            </div>
            {(vaultAuthorizationError || vaultStatus.error) && (
              <span className="text-sm text-red-600">
                {vaultAuthorizationError || vaultStatus.error}
              </span>
            )}
          </div>
        ) : (
          <span className="text-sm text-gray-500">Checking status...</span>
        )}
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20">
          <p role="alert" className="text-sm text-red-800 dark:text-red-200">
            {error}
          </p>
        </div>
      )}
      {success && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-900/20">
          <p
            role="status"
            className="text-sm text-green-800 dark:text-green-200"
          >
            {success}
          </p>
        </div>
      )}

      {/* Current API Keys */}
      <div className="rounded-lg bg-white shadow dark:bg-gray-800">
        <div className="border-b border-gray-200 p-6 dark:border-gray-700">
          <h2 className="text-lg font-medium text-gray-900 dark:text-white">
            Your API Keys
          </h2>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            API keys are securely stored in HashiCorp Vault and synced to your
            workers.
          </p>
        </div>

        {apiKeys.length === 0 ? (
          vaultAuthorizationError ? (
            <div className="p-6 text-center text-red-600 dark:text-red-400">
              Unable to list API keys: {vaultAuthorizationError}
            </div>
          ) : (
            <div className="p-6 text-center text-gray-500 dark:text-gray-400">
              No API keys configured. Add one below to get started.
            </div>
          )
        ) : (
          <ul className="divide-y divide-gray-200 dark:divide-gray-700">
            {apiKeys.map((key) => (
              <li
                key={key.provider_id}
                className="flex items-center justify-between p-6"
              >
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
      <div className="rounded-lg bg-white shadow dark:bg-gray-800">
        <div className="border-b border-gray-200 p-6 dark:border-gray-700">
          <h2 className="text-lg font-medium text-gray-900 dark:text-white">
            Add API Key
          </h2>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            Add a new LLM provider API key to use with your agents.
          </p>
        </div>

        <form onSubmit={handleSaveKey} className="space-y-4 p-6">
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
              disabled={saving || testing !== null}
              onChange={(e) => {
                setSelectedProvider(e.target.value)
                setApiKey('')
                setBaseUrlInput('')
                clearFeedback()
              }}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700"
            >
              <option value="">Select a provider...</option>
              {providers.map((provider) => (
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
              disabled={saving || testing !== null}
              onChange={(e) => {
                setApiKey(e.target.value)
                clearFeedback()
              }}
              placeholder="Enter your API key"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700"
            />
          </div>

          {(selectedProviderInfo?.has_base_url ||
            selectedProviderInfo?.requires_base_url) && (
            <div>
              <label
                htmlFor="baseUrl"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Base URL (
                {selectedProviderInfo?.requires_base_url
                  ? 'required'
                  : 'optional'}
                )
              </label>
              <input
                type="url"
                id="baseUrl"
                value={baseUrlInput}
                required={selectedProviderInfo?.requires_base_url}
                disabled={saving || testing !== null}
                onChange={(e) => {
                  setBaseUrlInput(e.target.value)
                  clearFeedback()
                }}
                placeholder="https://your-endpoint.example.com/v1"
                className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700"
              />
              <p className="mt-1 text-xs text-gray-500">
                Custom endpoint URLs can be saved, but cannot currently be
                connection-tested here.
              </p>
            </div>
          )}

          <div className="flex gap-4">
            <button
              type="submit"
              disabled={
                saving ||
                testing !== null ||
                !selectedProvider ||
                !apiKey.trim()
              }
              className="rounded-md bg-indigo-600 px-4 py-2 text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save API Key'}
            </button>
            <button
              type="button"
              onClick={handleTestKey}
              disabled={
                saving ||
                testing !== null ||
                !selectedProvider ||
                !apiKey.trim()
              }
              className="rounded-md bg-gray-200 px-4 py-2 text-gray-800 hover:bg-gray-300 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
            >
              {testing === selectedProvider ? 'Testing...' : 'Test Key'}
            </button>
          </div>
        </form>
      </div>

      {/* Available Providers Reference */}
      <div className="rounded-lg bg-white shadow dark:bg-gray-800">
        <div className="border-b border-gray-200 p-6 dark:border-gray-700">
          <h2 className="text-lg font-medium text-gray-900 dark:text-white">
            Supported Providers
          </h2>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {providers.map((provider) => (
              <div
                key={provider.id}
                className="rounded-lg border border-gray-200 p-4 dark:border-gray-700"
              >
                <h3 className="font-medium text-gray-900 dark:text-white">
                  {provider.name}
                </h3>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  {provider.description}
                </p>
                {provider.auth_type === 'oauth' && (
                  <span className="mt-2 inline-block rounded bg-blue-100 px-2 py-1 text-xs text-blue-800 dark:bg-blue-900 dark:text-blue-200">
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
