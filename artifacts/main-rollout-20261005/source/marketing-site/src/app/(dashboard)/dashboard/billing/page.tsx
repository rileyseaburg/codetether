'use client'

import { useState, useEffect, Suspense } from 'react'
import { useSession } from 'next-auth/react'
import { useSearchParams } from 'next/navigation'
import { getApiAuth } from '@/lib/auth-token'
import {
  finiteNumber,
  nonNegativeNumber,
  formatNumber,
  usagePercentage,
  remainingTasks,
  quotaNumber,
  formatQuota,
  subscriptionPlan,
} from '@/lib/billing-display'
import {
  getSubscriptionV1BillingSubscriptionGet,
  createCheckoutV1BillingCheckoutPost,
  createPortalV1BillingPortalPost,
  getUsageV1BillingUsageGet,
} from '@/lib/api'

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

interface BillingStatus {
  tier: string
  tier_name: string
  stripe_subscription_status: string | null
  current_period_end: string | null
  tasks_used: number | null
  tasks_limit: number | null
  concurrency_limit: number | null
  max_runtime_seconds: number | null
}

interface TokenUsageSummary {
  tenant_id: string
  month: string
  billing_model: string
  balance_dollars: number
  monthly_limit_dollars: number | null
  totals: {
    total_requests: number
    total_input_tokens: number
    total_output_tokens: number
    total_cost_dollars: number
  }
  by_model: Array<{
    provider: string
    model: string
    request_count: number
    input_tokens: number
    output_tokens: number
    cost_dollars: number
  }>
}

interface BudgetStatus {
  allowed: boolean
  reason: string
  balance_dollars: number
  monthly_spend_dollars: number
  monthly_limit_dollars: number | null
  billing_model: string
}

interface CostForecast {
  projected_cost_dollars: number
  daily_average_dollars: number
  days_in_period: number
  days_elapsed: number
  confidence: string
  trend: string
  pct_change_vs_last_period: number | null
}

interface CostAnomaly {
  anomaly_type: string
  severity: string
  model: string | null
  provider: string | null
  description: string
  expected_value: number
  actual_value: number
  deviation_factor: number
}

interface CostAlert {
  id: number
  alert_type: string
  severity: string
  title: string
  message: string
  acknowledged: boolean
  created_at: string | null
}

interface AlertSummary {
  total: number
  critical: number
  warning: number
  info: number
}

interface CostRecommendation {
  id: number
  recommendation_type: string
  title: string
  description: string
  estimated_savings_percent: number
  estimated_savings_dollars: number
  current_model: string | null
  suggested_model: string | null
  status: string
}

interface CostTrendPoint {
  date: string
  requests: number
  cost_dollars: number
  tokens: number
}

interface BudgetPolicy {
  id: number
  name: string
  scope: string
  period: string
  soft_limit_cents: number | null
  hard_limit_cents: number | null
  action_on_soft: string
  action_on_hard: string
  is_active: boolean
}

const tierDetails: Record<
  string,
  { price: string; description: string; color: string }
> = {
  free: {
    price: '$0/mo',
    description: 'Get started with 100 tasks/month',
    color: 'gray',
  },
  pro: {
    price: '$49/mo',
    description: 'For builders who need serious throughput',
    color: 'cyan',
  },
  enterprise: {
    price: '$199/mo',
    description: 'Unlimited tasks, workers, and workspaces',
    color: 'indigo',
  },
}

function BillingContent() {
  const { data: session, status: authStatus } = useSession()
  const searchParams = useSearchParams()
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [usageError, setUsageError] = useState<string | null>(null)
  const [tokenError, setTokenError] = useState<string | null>(null)
  const [upgrading, setUpgrading] = useState<string | null>(null)
  const [portalLoading, setPortalLoading] = useState(false)
  const [tokenUsage, setTokenUsage] = useState<TokenUsageSummary | null>(null)
  const [budgetStatus, setBudgetStatus] = useState<BudgetStatus | null>(null)
  const [tokenLoading, setTokenLoading] = useState(false)
  // FinOps state
  const [forecast, setForecast] = useState<CostForecast | null>(null)
  const [anomalies, setAnomalies] = useState<CostAnomaly[]>([])
  const [alerts, setAlerts] = useState<CostAlert[]>([])
  const [alertSummary, setAlertSummary] = useState<AlertSummary | null>(null)
  const [recommendations, setRecommendations] = useState<CostRecommendation[]>(
    [],
  )
  const [costTrend, setCostTrend] = useState<CostTrendPoint[]>([])
  const [policies, setPolicies] = useState<BudgetPolicy[]>([])
  const [finopsLoading, setFinopsLoading] = useState(false)

  const upgraded = searchParams.get('upgraded') === 'true'

  const { token: authToken } = getApiAuth(session)
  const getAuthToken = () => authToken || null

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
    if (authStatus !== 'loading' && authToken) {
      loadBillingStatus()
      loadTokenUsage()
      loadFinOpsData()
    }
  }, [authStatus, authToken])

  const loadTokenUsage = async () => {
    setTokenLoading(true)
    setTokenError(null)
    setTokenUsage(null)
    setBudgetStatus(null)
    try {
      const token = getAuthToken()
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const [usageRes, budgetRes] = await Promise.all([
        fetch(`${API_BASE_URL}/v1/token-billing/usage/summary`, { headers }),
        fetch(`${API_BASE_URL}/v1/token-billing/budget`, { headers }),
      ])

      if (usageRes.ok) {
        setTokenUsage(await usageRes.json())
      }
      if (budgetRes.ok) {
        setBudgetStatus(await budgetRes.json())
      }
      if (!usageRes.ok || !budgetRes.ok) {
        setTokenError(
          'Some token usage or budget data is unavailable. Please retry.',
        )
      }
    } catch (err) {
      console.error('Failed to load token usage:', err)
      setTokenError('Token usage is unavailable. Please retry.')
    } finally {
      setTokenLoading(false)
    }
  }

  const loadFinOpsData = async () => {
    setFinopsLoading(true)
    try {
      const headers = getAuthHeaders()

      const [
        forecastRes,
        anomalyRes,
        alertRes,
        alertSumRes,
        recsRes,
        trendRes,
        policyRes,
      ] = await Promise.all([
        fetch(`${API_BASE_URL}/v1/finops/forecast`, { headers }).catch(
          () => null,
        ),
        fetch(`${API_BASE_URL}/v1/finops/anomalies`, { headers }).catch(
          () => null,
        ),
        fetch(
          `${API_BASE_URL}/v1/finops/alerts?unacknowledged_only=true&limit=10`,
          { headers },
        ).catch(() => null),
        fetch(`${API_BASE_URL}/v1/finops/alerts/summary`, { headers }).catch(
          () => null,
        ),
        fetch(`${API_BASE_URL}/v1/finops/recommendations?status=open`, {
          headers,
        }).catch(() => null),
        fetch(`${API_BASE_URL}/v1/finops/cost-trend?days=30`, {
          headers,
        }).catch(() => null),
        fetch(`${API_BASE_URL}/v1/finops/policies`, { headers }).catch(
          () => null,
        ),
      ])

      if (forecastRes?.ok) setForecast(await forecastRes.json())
      if (anomalyRes?.ok) setAnomalies(await anomalyRes.json())
      if (alertRes?.ok) setAlerts(await alertRes.json())
      if (alertSumRes?.ok) setAlertSummary(await alertSumRes.json())
      if (recsRes?.ok) setRecommendations(await recsRes.json())
      if (trendRes?.ok) setCostTrend(await trendRes.json())
      if (policyRes?.ok) setPolicies(await policyRes.json())
    } catch (err) {
      console.error('Failed to load FinOps data:', err)
    } finally {
      setFinopsLoading(false)
    }
  }

  const handleAcknowledgeAlert = async (alertId: number) => {
    try {
      const headers = getAuthHeaders()
      const res = await fetch(
        `${API_BASE_URL}/v1/finops/alerts/${alertId}/acknowledge`,
        {
          method: 'POST',
          headers,
        },
      )
      if (res.ok) {
        setAlerts((prev) => prev.filter((a) => a.id !== alertId))
        setAlertSummary((prev) =>
          prev ? { ...prev, total: Math.max(0, prev.total - 1) } : prev,
        )
      }
    } catch (err) {
      console.error('Failed to acknowledge alert:', err)
    }
  }

  const handleDismissRecommendation = async (recId: number) => {
    try {
      const headers = getAuthHeaders()
      const res = await fetch(
        `${API_BASE_URL}/v1/finops/recommendations/${recId}/dismiss`,
        {
          method: 'POST',
          headers,
          body: JSON.stringify({ reason: 'dismissed from dashboard' }),
        },
      )
      if (res.ok) {
        setRecommendations((prev) => prev.filter((r) => r.id !== recId))
      }
    } catch (err) {
      console.error('Failed to dismiss recommendation:', err)
    }
  }

  const loadBillingStatus = async () => {
    setLoading(true)
    setError(null)
    setUsageError(null)

    try {
      const token = getAuthToken()
      const headers: Record<string, string> = {}
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const subscriptionRes = await getSubscriptionV1BillingSubscriptionGet({
        headers,
      })

      if (subscriptionRes.error || !subscriptionRes.data) {
        throw new Error(
          (subscriptionRes.error as any)?.detail ||
            'Failed to load billing status',
        )
      }

      const subscription = subscriptionRes.data as any
      const subscriptionStatus = {
        ...subscription,
        ...subscriptionPlan(subscription),
        stripe_subscription_status:
          subscription.stripe_subscription_status ??
          subscription.status ??
          null,
        tasks_used: null,
        tasks_limit: quotaNumber(subscription.tasks_limit),
        concurrency_limit: nonNegativeNumber(subscription.concurrency_limit),
        max_runtime_seconds: nonNegativeNumber(
          subscription.max_runtime_seconds,
        ),
      }

      try {
        const usageRes = await getUsageV1BillingUsageGet({ headers })
        const usage = usageRes.data as any
        const used = nonNegativeNumber(usage?.tasks_used)
        if (usageRes.error || !usage || used === null) {
          throw new Error('Usage unavailable')
        }
        setBillingStatus({
          ...subscriptionStatus,
          tasks_used: used,
          tasks_limit:
            quotaNumber(usage.tasks_limit) ?? subscriptionStatus.tasks_limit,
        })
      } catch {
        setBillingStatus(subscriptionStatus)
        setUsageError(
          'Task usage is unavailable. Your subscription limits are still shown.',
        )
      }
    } catch (err) {
      console.error('Failed to load billing status:', err)
      setError(
        err instanceof Error ? err.message : 'Failed to load billing status',
      )
    } finally {
      setLoading(false)
    }
  }

  const handleUpgrade = async (tierId: string) => {
    setUpgrading(tierId)
    setError(null)

    try {
      const token = getAuthToken()
      const headers: Record<string, string> = {}
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const baseUrl =
        typeof window !== 'undefined' ? window.location.origin : ''

      const { data, error: checkoutError } =
        await createCheckoutV1BillingCheckoutPost({
          headers,
          body: {
            plan: tierId,
            success_url: `${baseUrl}/dashboard/billing?upgraded=true`,
            cancel_url: `${baseUrl}/dashboard/billing`,
          },
        })

      if (checkoutError) {
        throw new Error(
          (checkoutError as any)?.detail || 'Failed to create checkout session',
        )
      }

      const response = data as any
      if (response?.checkout_url) {
        window.location.href = response.checkout_url
      } else {
        throw new Error('No checkout URL returned')
      }
    } catch (err) {
      console.error('Upgrade error:', err)
      setError(err instanceof Error ? err.message : 'Failed to start upgrade')
      setUpgrading(null)
    }
  }

  const handleManageBilling = async () => {
    setPortalLoading(true)
    setError(null)

    try {
      const token = getAuthToken()
      const headers: Record<string, string> = {}
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const baseUrl =
        typeof window !== 'undefined' ? window.location.origin : ''

      const { data, error: portalError } =
        await createPortalV1BillingPortalPost({
          headers,
          body: { return_url: `${baseUrl}/dashboard/billing` },
        })

      if (portalError) {
        throw new Error(
          (portalError as any)?.detail || 'Failed to create portal session',
        )
      }

      const response = data as any
      if (response?.portal_url) {
        window.location.href = response.portal_url
      } else {
        throw new Error('No portal URL returned')
      }
    } catch (err) {
      console.error('Portal error:', err)
      setError(
        err instanceof Error ? err.message : 'Failed to open billing portal',
      )
      setPortalLoading(false)
    }
  }

  if (authStatus === 'loading' || (loading && authToken)) {
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
          Sign in to manage billing
        </h2>
        <p className="text-gray-600 dark:text-gray-400">
          You need to be signed in to view your billing status.
        </p>
      </div>
    )
  }

  const currentTierDetails =
    tierDetails[billingStatus?.tier || 'free'] || tierDetails.free

  const usagePercent = usagePercentage(
    billingStatus?.tasks_used,
    billingStatus?.tasks_limit,
  )

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Billing
        </h1>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
          Manage your subscription and usage
        </p>
      </div>

      {/* Upgraded success message */}
      {upgraded && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-900/20">
          <div className="flex">
            <div className="shrink-0">
              <svg
                className="h-5 w-5 text-green-400"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm font-medium text-green-800 dark:text-green-200">
                Subscription activated! Your new limits are now in effect.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20">
          <p role="alert" className="text-sm text-red-800 dark:text-red-200">
            {error}
          </p>
          <button
            type="button"
            onClick={loadBillingStatus}
            className="mt-2 text-sm underline"
          >
            Retry billing details
          </button>
        </div>
      )}

      {/* Current Plan */}
      <div className="rounded-lg bg-white shadow dark:bg-gray-800">
        <div className="border-b border-gray-200 p-6 dark:border-gray-700">
          <h2 className="text-lg font-medium text-gray-900 dark:text-white">
            Current Plan
          </h2>
        </div>
        <div className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-3">
                <span className="text-2xl font-bold text-gray-900 dark:text-white">
                  {billingStatus?.tier_name || 'Free'}
                </span>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    billingStatus?.stripe_subscription_status === 'active'
                      ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                      : billingStatus?.stripe_subscription_status === 'past_due'
                        ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                        : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                  }`}
                >
                  {billingStatus?.stripe_subscription_status === 'active'
                    ? 'Active'
                    : billingStatus?.stripe_subscription_status === 'past_due'
                      ? 'Past Due'
                      : billingStatus?.tier === 'free'
                        ? 'Free Tier'
                        : billingStatus?.stripe_subscription_status || 'Active'}
                </span>
              </div>
              <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                {currentTierDetails.description}
              </p>
              <p className="mt-2 text-lg font-semibold text-gray-900 dark:text-white">
                {currentTierDetails.price}
              </p>
              {billingStatus?.current_period_end && (
                <p className="mt-1 text-xs text-gray-500">
                  Current period ends:{' '}
                  {new Date(
                    billingStatus.current_period_end,
                  ).toLocaleDateString()}
                </p>
              )}
            </div>
            {billingStatus?.stripe_subscription_status &&
              billingStatus.tier !== 'free' && (
                <button
                  onClick={handleManageBilling}
                  disabled={portalLoading}
                  className="rounded-md bg-gray-100 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 disabled:opacity-50 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
                >
                  {portalLoading ? 'Opening...' : 'Manage billing'}
                </button>
              )}
          </div>
        </div>
      </div>

      {/* Usage */}
      <div className="rounded-lg bg-white shadow dark:bg-gray-800">
        <div className="border-b border-gray-200 p-6 dark:border-gray-700">
          <h2 className="text-lg font-medium text-gray-900 dark:text-white">
            This Month&apos;s Usage
          </h2>
        </div>
        <div className="space-y-6 p-6">
          {/* Tasks used */}
          <div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-600 dark:text-gray-400">
                Tasks used
              </span>
              <span className="font-medium text-gray-900 dark:text-white">
                {formatNumber(billingStatus?.tasks_used)} /{' '}
                {formatQuota(billingStatus?.tasks_limit)}
              </span>
            </div>
            <div
              hidden={
                billingStatus?.tasks_used == null ||
                billingStatus?.tasks_limit == null ||
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
            {usagePercent >= 90 && billingStatus?.tier === 'free' && (
              <p className="mt-2 text-xs text-red-600 dark:text-red-400">
                Running low on tasks. Upgrade to Pro for 5,000 tasks/month.
              </p>
            )}
          </div>

          {/* Limits grid */}
          {usageError && (
            <div
              role="alert"
              className="text-sm text-amber-700 dark:text-amber-300"
            >
              <p>{usageError}</p>
              <button
                type="button"
                onClick={loadBillingStatus}
                disabled={loading}
                className="mt-2 underline"
              >
                Retry task usage
              </button>
            </div>
          )}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="rounded-lg bg-gray-50 p-4 dark:bg-gray-700/50">
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {formatNumber(billingStatus?.concurrency_limit)}
              </div>
              <div className="text-sm text-gray-500 dark:text-gray-400">
                concurrent tasks
              </div>
            </div>
            <div className="rounded-lg bg-gray-50 p-4 dark:bg-gray-700/50">
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {formatNumber(
                  billingStatus?.max_runtime_seconds == null
                    ? null
                    : Math.round(billingStatus.max_runtime_seconds / 60),
                )}{' '}
                min
              </div>
              <div className="text-sm text-gray-500 dark:text-gray-400">
                max runtime
              </div>
            </div>
            <div className="rounded-lg bg-gray-50 p-4 dark:bg-gray-700/50">
              <div className="text-2xl font-bold text-gray-900 dark:text-white">
                {formatQuota(
                  remainingTasks(
                    billingStatus?.tasks_used,
                    billingStatus?.tasks_limit,
                  ),
                )}
              </div>
              <div className="text-sm text-gray-500 dark:text-gray-400">
                tasks remaining
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Token Usage */}
      <div className="rounded-lg bg-white shadow dark:bg-gray-800">
        <div className="border-b border-gray-200 p-6 dark:border-gray-700">
          <h2 className="text-lg font-medium text-gray-900 dark:text-white">
            Token Usage
          </h2>
          {tokenError && (
            <div
              role="alert"
              className="mt-2 text-sm text-amber-700 dark:text-amber-300"
            >
              <p>{tokenError}</p>
              <button
                type="button"
                onClick={loadTokenUsage}
                disabled={tokenLoading}
                className="mt-2 underline"
              >
                Retry token usage
              </button>
            </div>
          )}
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            AI model token consumption this billing period
          </p>
        </div>
        <div className="p-6">
          {tokenLoading ? (
            <div className="flex justify-center py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-b-2 border-cyan-600" />
            </div>
          ) : budgetStatus || tokenUsage ? (
            <div className="space-y-6">
              {/* Balance & Spend overview */}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="rounded-lg bg-gray-50 p-4 dark:bg-gray-700/50">
                  <div className="text-2xl font-bold text-gray-900 dark:text-white">
                    ${formatNumber(budgetStatus?.balance_dollars, 2)}
                  </div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    credit balance
                  </div>
                </div>
                <div className="rounded-lg bg-gray-50 p-4 dark:bg-gray-700/50">
                  <div className="text-2xl font-bold text-gray-900 dark:text-white">
                    ${formatNumber(budgetStatus?.monthly_spend_dollars, 2)}
                  </div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    spent this month
                  </div>
                </div>
                <div className="rounded-lg bg-gray-50 p-4 dark:bg-gray-700/50">
                  <div className="text-2xl font-bold text-gray-900 dark:text-white">
                    {budgetStatus?.monthly_limit_dollars === null
                      ? 'Unlimited'
                      : `$${formatNumber(budgetStatus?.monthly_limit_dollars, 2)}`}
                  </div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    monthly limit
                  </div>
                </div>
              </div>

              {/* Spending progress bar */}
              {budgetStatus &&
                (nonNegativeNumber(budgetStatus.monthly_limit_dollars) ?? 0) >
                  0 &&
                finiteNumber(budgetStatus.monthly_spend_dollars) !== null && (
                  <div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-600 dark:text-gray-400">
                        Token spending
                      </span>
                      <span className="font-medium text-gray-900 dark:text-white">
                        ${formatNumber(budgetStatus.monthly_spend_dollars, 2)} /
                        ${formatNumber(budgetStatus.monthly_limit_dollars, 2)}
                      </span>
                    </div>
                    <div className="mt-2 h-2 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                      <div
                        className={`h-full rounded-full transition-all ${
                          usagePercentage(
                            budgetStatus.monthly_spend_dollars,
                            budgetStatus.monthly_limit_dollars,
                          ) >= 90
                            ? 'bg-red-500'
                            : usagePercentage(
                                  budgetStatus.monthly_spend_dollars,
                                  budgetStatus.monthly_limit_dollars,
                                ) >= 75
                              ? 'bg-yellow-500'
                              : 'bg-cyan-500'
                        }`}
                        style={{
                          width: `${usagePercentage(budgetStatus.monthly_spend_dollars, budgetStatus.monthly_limit_dollars)}%`,
                        }}
                      />
                    </div>
                  </div>
                )}

              {/* Budget warning */}
              {budgetStatus && !budgetStatus.allowed && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20">
                  <p className="text-sm text-red-800 dark:text-red-200">
                    {budgetStatus.reason}
                  </p>
                </div>
              )}

              {/* Token totals */}
              {tokenUsage?.totals && (
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <div className="text-center">
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">
                      {formatNumber(tokenUsage.totals?.total_requests)}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      requests
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">
                      {formatNumber(tokenUsage.totals?.total_input_tokens)}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      input tokens
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-semibold text-gray-900 dark:text-white">
                      {formatNumber(tokenUsage.totals?.total_output_tokens)}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      output tokens
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-lg font-semibold text-cyan-600 dark:text-cyan-400">
                      ${formatNumber(tokenUsage.totals?.total_cost_dollars, 4)}
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      total cost
                    </div>
                  </div>
                </div>
              )}

              {/* Per-model breakdown */}
              {tokenUsage?.by_model && tokenUsage.by_model.length > 0 && (
                <div className="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
                  <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                    <thead className="bg-gray-50 dark:bg-gray-700/50">
                      <tr>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
                          Model
                        </th>
                        <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">
                          Requests
                        </th>
                        <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">
                          Input
                        </th>
                        <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">
                          Output
                        </th>
                        <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">
                          Cost
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 text-sm dark:divide-gray-700">
                      {tokenUsage.by_model.map((row, i) => (
                        <tr key={i}>
                          <td className="px-4 py-2 text-gray-900 dark:text-white">
                            <span className="text-xs text-gray-500 dark:text-gray-400">
                              {row.provider}/
                            </span>
                            {row.model}
                          </td>
                          <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">
                            {formatNumber(row.request_count)}
                          </td>
                          <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">
                            {formatNumber(row.input_tokens)}
                          </td>
                          <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">
                            {formatNumber(row.output_tokens)}
                          </td>
                          <td className="px-4 py-2 text-right font-medium text-gray-900 dark:text-white">
                            ${formatNumber(row.cost_dollars, 4)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
              {tokenError
                ? 'Usage could not be loaded. Retry to retrieve the current totals.'
                : 'No token usage data available yet. Usage will appear here once your agents start processing tasks.'}
            </p>
          )}
        </div>
      </div>

      {/* Upgrade Options (show if not on highest tier) */}
      {billingStatus?.tier !== 'enterprise' && (
        <div className="rounded-lg bg-white shadow dark:bg-gray-800">
          <div className="border-b border-gray-200 p-6 dark:border-gray-700">
            <h2 className="text-lg font-medium text-gray-900 dark:text-white">
              Upgrade Your Plan
            </h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {/* Pro tier card */}
              {billingStatus?.tier === 'free' && (
                <div className="relative rounded-lg border-2 border-cyan-500 p-6">
                  <span className="absolute -top-3 left-4 rounded bg-cyan-500 px-2 text-xs font-medium text-white">
                    Recommended
                  </span>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Pro
                  </h3>
                  <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                    For builders who need serious throughput
                  </p>
                  <p className="mt-3 text-2xl font-bold text-gray-900 dark:text-white">
                    $49
                    <span className="text-sm font-normal text-gray-500">
                      /mo
                    </span>
                  </p>
                  <ul className="mt-4 space-y-2 text-sm text-gray-600 dark:text-gray-400">
                    <li>5,000 tasks / month</li>
                    <li>5 workers</li>
                    <li>20 workspaces</li>
                  </ul>
                  <button
                    onClick={() => handleUpgrade('pro')}
                    disabled={upgrading === 'pro'}
                    className="mt-4 w-full rounded-md bg-cyan-600 px-4 py-2 text-white transition-colors hover:bg-cyan-700 disabled:opacity-50"
                  >
                    {upgrading === 'pro' ? 'Redirecting...' : 'Upgrade to Pro'}
                  </button>
                </div>
              )}

              {/* Enterprise tier card */}
              <div
                className={`relative rounded-lg border border-gray-200 p-6 dark:border-gray-700 ${billingStatus?.tier === 'pro' ? 'border-2 border-indigo-500' : ''}`}
              >
                {billingStatus?.tier === 'pro' && (
                  <span className="absolute -top-3 left-4 rounded bg-indigo-500 px-2 text-xs font-medium text-white">
                    Next tier
                  </span>
                )}
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Enterprise
                </h3>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                  Unlimited tasks, workers, and workspaces
                </p>
                <p className="mt-3 text-2xl font-bold text-gray-900 dark:text-white">
                  $199
                  <span className="text-sm font-normal text-gray-500">/mo</span>
                </p>
                <ul className="mt-4 space-y-2 text-sm text-gray-600 dark:text-gray-400">
                  <li>Unlimited tasks / month</li>
                  <li>Unlimited workers</li>
                  <li>Unlimited workspaces</li>
                </ul>
                <button
                  onClick={() => handleUpgrade('enterprise')}
                  disabled={upgrading === 'enterprise'}
                  className={`mt-4 w-full rounded-md px-4 py-2 transition-colors disabled:opacity-50 ${
                    billingStatus?.tier === 'pro'
                      ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                      : 'bg-gray-100 text-gray-800 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600'
                  }`}
                >
                  {upgrading === 'enterprise'
                    ? 'Redirecting...'
                    : 'Upgrade to Enterprise'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* FinOps: Alerts Banner */}
      {alertSummary && alertSummary.total > 0 && (
        <div
          className={`rounded-lg border p-4 ${
            alertSummary.critical > 0
              ? 'border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20'
              : 'border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-900/20'
          }`}
        >
          <div className="flex items-center gap-3">
            <svg
              className={`h-5 w-5 ${alertSummary.critical > 0 ? 'text-red-500' : 'text-yellow-500'}`}
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth="1.5"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
              />
            </svg>
            <div className="flex-1">
              <p
                className={`text-sm font-medium ${alertSummary.critical > 0 ? 'text-red-800 dark:text-red-200' : 'text-yellow-800 dark:text-yellow-200'}`}
              >
                {formatNumber(alertSummary.total)} unacknowledged cost alert
                {alertSummary.total !== 1 ? 's' : ''}
                {alertSummary.critical > 0 &&
                  ` (${formatNumber(alertSummary.critical)} critical)`}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* FinOps: Forecast & Trend */}
      {(forecast || costTrend.length > 0) && (
        <div className="rounded-lg bg-white shadow dark:bg-gray-800">
          <div className="border-b border-gray-200 p-6 dark:border-gray-700">
            <h2 className="text-lg font-medium text-gray-900 dark:text-white">
              Cost Forecast &amp; Trends
            </h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Projected spend and daily usage patterns
            </p>
          </div>
          <div className="space-y-6 p-6">
            {/* Forecast cards */}
            {forecast && (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
                <div className="rounded-lg bg-gray-50 p-4 dark:bg-gray-700/50">
                  <div className="text-2xl font-bold text-gray-900 dark:text-white">
                    ${formatNumber(forecast.projected_cost_dollars, 2)}
                  </div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    projected this month
                  </div>
                </div>
                <div className="rounded-lg bg-gray-50 p-4 dark:bg-gray-700/50">
                  <div className="text-2xl font-bold text-gray-900 dark:text-white">
                    ${formatNumber(forecast.daily_average_dollars, 2)}
                  </div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    daily average
                  </div>
                </div>
                <div className="rounded-lg bg-gray-50 p-4 dark:bg-gray-700/50">
                  <div
                    className={`text-2xl font-bold ${
                      forecast.trend === 'increasing'
                        ? 'text-red-600 dark:text-red-400'
                        : forecast.trend === 'decreasing'
                          ? 'text-green-600 dark:text-green-400'
                          : 'text-gray-900 dark:text-white'
                    }`}
                  >
                    {forecast.trend === 'increasing'
                      ? '↑'
                      : forecast.trend === 'decreasing'
                        ? '↓'
                        : '→'}{' '}
                    {forecast.trend}
                  </div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    spending trend
                  </div>
                </div>
                <div className="rounded-lg bg-gray-50 p-4 dark:bg-gray-700/50">
                  <div className="text-2xl font-bold text-gray-900 dark:text-white">
                    {finiteNumber(forecast.pct_change_vs_last_period) !== null
                      ? `${Number(forecast.pct_change_vs_last_period) > 0 ? '+' : ''}${formatNumber(forecast.pct_change_vs_last_period)}%`
                      : 'N/A'}
                  </div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">
                    vs last month
                  </div>
                </div>
              </div>
            )}

            {forecast && (
              <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                <span
                  className={`rounded-full px-2 py-0.5 ${
                    forecast.confidence === 'high'
                      ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                      : forecast.confidence === 'medium'
                        ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300'
                        : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                  }`}
                >
                  {forecast.confidence} confidence
                </span>
                <span>
                  Day {formatNumber(forecast.days_elapsed)} of{' '}
                  {formatNumber(forecast.days_in_period)}
                </span>
              </div>
            )}

            {/* Cost trend mini chart (text-based bar chart) */}
            {costTrend.length > 0 && (
              <div>
                <h3 className="mb-3 text-sm font-medium text-gray-700 dark:text-gray-300">
                  Daily Cost (last 30 days)
                </h3>
                <div className="space-y-1">
                  {(() => {
                    const maxCost = Math.max(
                      ...costTrend.map(
                        (d) => nonNegativeNumber(d.cost_dollars) ?? 0,
                      ),
                      0.001,
                    )
                    const recent = costTrend.slice(-14) // Show last 14 days
                    return recent.map((day, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <span className="w-20 text-right text-gray-500 dark:text-gray-400">
                          {day.date.slice(5)}
                        </span>
                        <div className="h-4 flex-1 overflow-hidden rounded bg-gray-100 dark:bg-gray-700">
                          <div
                            className="h-full rounded bg-cyan-500"
                            style={{
                              width: `${usagePercentage(day.cost_dollars, maxCost)}%`,
                            }}
                          />
                        </div>
                        <span className="w-16 text-right text-gray-600 dark:text-gray-400">
                          ${formatNumber(day.cost_dollars, 2)}
                        </span>
                      </div>
                    ))
                  })()}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* FinOps: Anomalies */}
      {anomalies.length > 0 && (
        <div className="rounded-lg bg-white shadow dark:bg-gray-800">
          <div className="border-b border-gray-200 p-6 dark:border-gray-700">
            <h2 className="text-lg font-medium text-gray-900 dark:text-white">
              Cost Anomalies
            </h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Unusual spending patterns detected today
            </p>
          </div>
          <div className="space-y-3 p-6">
            {anomalies.map((anomaly, i) => (
              <div
                key={i}
                className={`rounded-lg border p-4 ${
                  anomaly.severity === 'critical'
                    ? 'border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20'
                    : 'border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-900/20'
                }`}
              >
                <div className="flex items-start gap-3">
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-medium ${
                      anomaly.severity === 'critical'
                        ? 'bg-red-100 text-red-800 dark:bg-red-800 dark:text-red-200'
                        : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-800 dark:text-yellow-200'
                    }`}
                  >
                    {anomaly.anomaly_type.replace('_', ' ')}
                  </span>
                  <div className="flex-1">
                    <p className="text-sm text-gray-800 dark:text-gray-200">
                      {anomaly.description}
                    </p>
                    {anomaly.model && (
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        Model: {anomaly.provider}/{anomaly.model}
                      </p>
                    )}
                  </div>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {formatNumber(anomaly.deviation_factor, 1)}x
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* FinOps: Cost Optimization Recommendations */}
      {recommendations.length > 0 && (
        <div className="rounded-lg bg-white shadow dark:bg-gray-800">
          <div className="border-b border-gray-200 p-6 dark:border-gray-700">
            <h2 className="text-lg font-medium text-gray-900 dark:text-white">
              Cost Optimization Recommendations
            </h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Actionable suggestions to reduce your AI spend
            </p>
          </div>
          <div className="space-y-4 p-6">
            {recommendations.map((rec) => (
              <div
                key={rec.id}
                className="rounded-lg border border-gray-200 p-4 dark:border-gray-700"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-medium ${
                          rec.recommendation_type === 'model_downgrade'
                            ? 'bg-blue-100 text-blue-800 dark:bg-blue-800 dark:text-blue-200'
                            : rec.recommendation_type === 'cache_optimization'
                              ? 'bg-green-100 text-green-800 dark:bg-green-800 dark:text-green-200'
                              : 'bg-purple-100 text-purple-800 dark:bg-purple-800 dark:text-purple-200'
                        }`}
                      >
                        {rec.recommendation_type.replace('_', ' ')}
                      </span>
                      <span className="text-sm font-medium text-green-600 dark:text-green-400">
                        Save ~${formatNumber(rec.estimated_savings_dollars, 2)}
                        /mo ({formatNumber(rec.estimated_savings_percent)}%)
                      </span>
                    </div>
                    <h4 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">
                      {rec.title}
                    </h4>
                    <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                      {rec.description}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDismissRecommendation(rec.id)}
                    className="ml-4 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    title="Dismiss"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* FinOps: Active Alerts */}
      {alerts.length > 0 && (
        <div className="rounded-lg bg-white shadow dark:bg-gray-800">
          <div className="border-b border-gray-200 p-6 dark:border-gray-700">
            <h2 className="text-lg font-medium text-gray-900 dark:text-white">
              Active Cost Alerts
            </h2>
          </div>
          <div className="space-y-3 p-6">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className={`flex items-start gap-3 rounded-lg border p-3 ${
                  alert.severity === 'critical'
                    ? 'border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-900/20'
                    : alert.severity === 'warning'
                      ? 'border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-900/20'
                      : 'border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-900/20'
                }`}
              >
                <div className="flex-1">
                  <h4 className="text-sm font-medium text-gray-900 dark:text-white">
                    {alert.title}
                  </h4>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {alert.message}
                  </p>
                  {alert.created_at && (
                    <p className="mt-1 text-xs text-gray-400">
                      {new Date(alert.created_at).toLocaleString()}
                    </p>
                  )}
                </div>
                <button
                  onClick={() => handleAcknowledgeAlert(alert.id)}
                  className="rounded border border-gray-300 bg-white px-3 py-1 text-xs font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
                >
                  Acknowledge
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* FinOps: Budget Policies */}
      {policies.length > 0 && (
        <div className="rounded-lg bg-white shadow dark:bg-gray-800">
          <div className="border-b border-gray-200 p-6 dark:border-gray-700">
            <h2 className="text-lg font-medium text-gray-900 dark:text-white">
              Budget Policies
            </h2>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Automated spending rules and enforcement
            </p>
          </div>
          <div className="p-6">
            <div className="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-700/50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
                      Policy
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">
                      Scope
                    </th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">
                      Warn At
                    </th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">
                      Block At
                    </th>
                    <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 dark:text-gray-400">
                      Period
                    </th>
                    <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 dark:text-gray-400">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200 text-sm dark:divide-gray-700">
                  {policies.map((policy) => (
                    <tr key={policy.id}>
                      <td className="px-4 py-2 font-medium text-gray-900 dark:text-white">
                        {policy.name}
                      </td>
                      <td className="px-4 py-2 text-gray-600 dark:text-gray-400">
                        {policy.scope}
                      </td>
                      <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">
                        {finiteNumber(policy.soft_limit_cents) === null
                          ? '—'
                          : `$${formatNumber(Number(policy.soft_limit_cents) / 100, 0)}`}
                      </td>
                      <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">
                        {finiteNumber(policy.hard_limit_cents) === null
                          ? '—'
                          : `$${formatNumber(Number(policy.hard_limit_cents) / 100, 0)}`}
                      </td>
                      <td className="px-4 py-2 text-center text-gray-600 dark:text-gray-400">
                        {policy.period}
                      </td>
                      <td className="px-4 py-2 text-center">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs ${
                            policy.is_active
                              ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                              : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                          }`}
                        >
                          {policy.is_active ? 'active' : 'paused'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* FAQ */}
      <div className="rounded-lg bg-white shadow dark:bg-gray-800">
        <div className="border-b border-gray-200 p-6 dark:border-gray-700">
          <h2 className="text-lg font-medium text-gray-900 dark:text-white">
            Billing FAQ
          </h2>
        </div>
        <div className="space-y-4 p-6">
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white">
              When does my usage reset?
            </h4>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
              Usage resets on your billing anniversary date each month.
            </p>
          </div>
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white">
              What happens if I hit my limit?
            </h4>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
              New tasks will be blocked until your limit resets or you upgrade.
              Running tasks won&apos;t be interrupted.
            </p>
          </div>
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white">
              Can I downgrade?
            </h4>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
              Yes, use &quot;Manage billing&quot; to change or cancel your plan.
              Changes take effect at your next billing date.
            </p>
          </div>
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white">
              Do I use my own API keys or yours?
            </h4>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
              Bring Your Own Model (BYOM). You add your own API keys (Anthropic,
              OpenAI, Google, etc.) in Settings. Keys are stored securely in
              HashiCorp Vault. The platform tracks your token usage and applies
              billing based on your plan&apos;s billing model (subscription,
              prepaid, or metered).
            </p>
          </div>
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white">
              How does token billing work?
            </h4>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
              Every AI request consumes tokens. We track input, output,
              reasoning, and cache tokens per request and deduct from your
              prepaid credit balance. Each model has transparent
              per-million-token pricing. You can set monthly spending limits and
              add credits anytime.
            </p>
          </div>
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white">
              What happens if my token credit runs out?
            </h4>
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
              New AI requests will be paused until you add more credits. Running
              tasks won&apos;t be interrupted mid-stream. You can add credits at
              any time from this page.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function BillingPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-100 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-indigo-600" />
        </div>
      }
    >
      <BillingContent />
    </Suspense>
  )
}
