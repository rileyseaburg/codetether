'use client'

import { useState, useEffect, Suspense } from 'react'
import { useSession } from 'next-auth/react'
import { useSearchParams } from 'next/navigation'
import {
    getSubscriptionV1BillingSubscriptionGet,
    createCheckoutV1BillingCheckoutPost,
    createPortalV1BillingPortalPost,
    getUsageV1BillingUsageGet
} from '@/lib/api'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

interface BillingStatus {
    tier: string
    tier_name: string
    stripe_subscription_status: string | null
    current_period_end: string | null
    tasks_used: number
    tasks_limit: number
    concurrency_limit: number
    max_runtime_seconds: number
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



const tierDetails: Record<string, { price: string; description: string; color: string }> = {
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
    const [recommendations, setRecommendations] = useState<CostRecommendation[]>([])
    const [costTrend, setCostTrend] = useState<CostTrendPoint[]>([])
    const [policies, setPolicies] = useState<BudgetPolicy[]>([])
    const [finopsLoading, setFinopsLoading] = useState(false)

    const upgraded = searchParams.get('upgraded') === 'true'

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
        if (authStatus === 'authenticated') {
            loadBillingStatus()
            loadTokenUsage()
            loadFinOpsData()
        }
    }, [authStatus])

    const loadTokenUsage = async () => {
        setTokenLoading(true)
        try {
            const token = getAuthToken()
            const headers: Record<string, string> = { 'Content-Type': 'application/json' }
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
        } catch (err) {
            console.error('Failed to load token usage:', err)
        } finally {
            setTokenLoading(false)
        }
    }

    const loadFinOpsData = async () => {
        setFinopsLoading(true)
        try {
            const headers = getAuthHeaders()

            const [forecastRes, anomalyRes, alertRes, alertSumRes, recsRes, trendRes, policyRes] = await Promise.all([
                fetch(`${API_BASE_URL}/v1/finops/forecast`, { headers }).catch(() => null),
                fetch(`${API_BASE_URL}/v1/finops/anomalies`, { headers }).catch(() => null),
                fetch(`${API_BASE_URL}/v1/finops/alerts?unacknowledged_only=true&limit=10`, { headers }).catch(() => null),
                fetch(`${API_BASE_URL}/v1/finops/alerts/summary`, { headers }).catch(() => null),
                fetch(`${API_BASE_URL}/v1/finops/recommendations?status=open`, { headers }).catch(() => null),
                fetch(`${API_BASE_URL}/v1/finops/cost-trend?days=30`, { headers }).catch(() => null),
                fetch(`${API_BASE_URL}/v1/finops/policies`, { headers }).catch(() => null),
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
            const res = await fetch(`${API_BASE_URL}/v1/finops/alerts/${alertId}/acknowledge`, {
                method: 'POST',
                headers,
            })
            if (res.ok) {
                setAlerts(prev => prev.filter(a => a.id !== alertId))
                setAlertSummary(prev => prev ? { ...prev, total: Math.max(0, prev.total - 1) } : prev)
            }
        } catch (err) {
            console.error('Failed to acknowledge alert:', err)
        }
    }

    const handleDismissRecommendation = async (recId: number) => {
        try {
            const headers = getAuthHeaders()
            const res = await fetch(`${API_BASE_URL}/v1/finops/recommendations/${recId}/dismiss`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ reason: 'dismissed from dashboard' }),
            })
            if (res.ok) {
                setRecommendations(prev => prev.filter(r => r.id !== recId))
            }
        } catch (err) {
            console.error('Failed to dismiss recommendation:', err)
        }
    }

    const loadBillingStatus = async () => {
        setLoading(true)
        setError(null)

        try {
            const token = getAuthToken()
            const headers: Record<string, string> = {}
            if (token) {
                headers['Authorization'] = `Bearer ${token}`
            }

            const subscriptionRes = await getSubscriptionV1BillingSubscriptionGet({ headers })

            if (subscriptionRes.error) {
                throw new Error((subscriptionRes.error as any)?.detail || 'Failed to load billing status')
            }

            const subscription = subscriptionRes.data as any

            try {
                const usageRes = await getUsageV1BillingUsageGet({ headers })
                const usage = usageRes.data as any
                setBillingStatus({
                    ...subscription,
                    tasks_used: usage?.tasks_used ?? 0,
                    tasks_limit: usage?.tasks_limit ?? 0,
                    concurrency_limit: subscription?.concurrency_limit ?? 1,
                    max_runtime_seconds: subscription?.max_runtime_seconds ?? 600
                })
            } catch {
                setBillingStatus({
                    ...subscription,
                    tasks_used: 0,
                    tasks_limit: subscription?.tasks_limit ?? 0,
                    concurrency_limit: subscription?.concurrency_limit ?? 1,
                    max_runtime_seconds: subscription?.max_runtime_seconds ?? 600
                })
            }
        } catch (err) {
            console.error('Failed to load billing status:', err)
            setError(err instanceof Error ? err.message : 'Failed to load billing status')
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

            const baseUrl = typeof window !== 'undefined' ? window.location.origin : ''

            const { data, error: checkoutError } = await createCheckoutV1BillingCheckoutPost({
                headers,
                body: {
                    plan: tierId,
                    success_url: `${baseUrl}/dashboard/billing?upgraded=true`,
                    cancel_url: `${baseUrl}/dashboard/billing`,
                }
            })

            if (checkoutError) {
                throw new Error((checkoutError as any)?.detail || 'Failed to create checkout session')
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

            const baseUrl = typeof window !== 'undefined' ? window.location.origin : ''

            const { data, error: portalError } = await createPortalV1BillingPortalPost({
                headers,
                body: { return_url: `${baseUrl}/dashboard/billing` }
            })

            if (portalError) {
                throw new Error((portalError as any)?.detail || 'Failed to create portal session')
            }

            const response = data as any
            if (response?.portal_url) {
                window.location.href = response.portal_url
            } else {
                throw new Error('No portal URL returned')
            }
        } catch (err) {
            console.error('Portal error:', err)
            setError(err instanceof Error ? err.message : 'Failed to open billing portal')
            setPortalLoading(false)
        }
    }

    if (authStatus === 'loading' || loading) {
        return (
            <div className="flex items-center justify-center min-h-100">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
            </div>
        )
    }

    if (authStatus === 'unauthenticated') {
        return (
            <div className="text-center py-12">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
                    Sign in to manage billing
                </h2>
                <p className="text-gray-600 dark:text-gray-400">
                    You need to be signed in to view your billing status.
                </p>
            </div>
        )
    }

    const currentTierDetails = tierDetails[billingStatus?.tier || 'free'] || tierDetails.free

    const usagePercent = billingStatus
        ? Math.min(100, Math.round((billingStatus.tasks_used / billingStatus.tasks_limit) * 100))
        : 0

    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Billing</h1>
                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                    Manage your subscription and usage
                </p>
            </div>

            {/* Upgraded success message */}
            {upgraded && (
                <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
                    <div className="flex">
                        <div className="shrink-0">
                            <svg className="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
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
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                    <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
                </div>
            )}

            {/* Current Plan */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
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
                                <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${billingStatus?.stripe_subscription_status === 'active'
                                    ? 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200'
                                    : billingStatus?.stripe_subscription_status === 'past_due'
                                        ? 'bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200'
                                        : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200'
                                    }`}>
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
                                    Current period ends: {new Date(billingStatus.current_period_end).toLocaleDateString()}
                                </p>
                            )}
                        </div>
                        {billingStatus?.stripe_subscription_status && billingStatus.tier !== 'free' && (
                            <button
                                onClick={handleManageBilling}
                                disabled={portalLoading}
                                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50"
                            >
                                {portalLoading ? 'Opening...' : 'Manage billing'}
                            </button>
                        )}
                    </div>
                </div>
            </div>

            {/* Usage */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                    <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                        This Month&apos;s Usage
                    </h2>
                </div>
                <div className="p-6 space-y-6">
                    {/* Tasks used */}
                    <div>
                        <div className="flex items-center justify-between text-sm">
                            <span className="text-gray-600 dark:text-gray-400">Tasks used</span>
                            <span className="font-medium text-gray-900 dark:text-white">
                                {billingStatus?.tasks_used.toLocaleString()} / {billingStatus?.tasks_limit.toLocaleString()}
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
                        {usagePercent >= 90 && billingStatus?.tier === 'free' && (
                            <p className="mt-2 text-xs text-red-600 dark:text-red-400">
                                Running low on tasks. Upgrade to Pro for 5,000 tasks/month.
                            </p>
                        )}
                    </div>

                    {/* Limits grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                            <div className="text-2xl font-bold text-gray-900 dark:text-white">
                                {billingStatus?.concurrency_limit}
                            </div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">
                                concurrent tasks
                            </div>
                        </div>
                        <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                            <div className="text-2xl font-bold text-gray-900 dark:text-white">
                                {billingStatus?.max_runtime_seconds ? Math.round(billingStatus.max_runtime_seconds / 60) : 10} min
                            </div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">
                                max runtime
                            </div>
                        </div>
                        <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                            <div className="text-2xl font-bold text-gray-900 dark:text-white">
                                {billingStatus?.tasks_limit ? billingStatus.tasks_limit - billingStatus.tasks_used : 0}
                            </div>
                            <div className="text-sm text-gray-500 dark:text-gray-400">
                                tasks remaining
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Token Usage */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                    <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                        Token Usage
                    </h2>
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                        AI model token consumption this billing period
                    </p>
                </div>
                <div className="p-6">
                    {tokenLoading ? (
                        <div className="flex justify-center py-8">
                            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-cyan-600" />
                        </div>
                    ) : budgetStatus || tokenUsage ? (
                        <div className="space-y-6">
                            {/* Balance & Spend overview */}
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                                    <div className="text-2xl font-bold text-gray-900 dark:text-white">
                                        ${budgetStatus?.balance_dollars?.toFixed(2) ?? '0.00'}
                                    </div>
                                    <div className="text-sm text-gray-500 dark:text-gray-400">
                                        credit balance
                                    </div>
                                </div>
                                <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                                    <div className="text-2xl font-bold text-gray-900 dark:text-white">
                                        ${budgetStatus?.monthly_spend_dollars?.toFixed(2) ?? '0.00'}
                                    </div>
                                    <div className="text-sm text-gray-500 dark:text-gray-400">
                                        spent this month
                                    </div>
                                </div>
                                <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                                    <div className="text-2xl font-bold text-gray-900 dark:text-white">
                                        {budgetStatus?.monthly_limit_dollars
                                            ? `$${budgetStatus.monthly_limit_dollars.toFixed(2)}`
                                            : 'Unlimited'}
                                    </div>
                                    <div className="text-sm text-gray-500 dark:text-gray-400">
                                        monthly limit
                                    </div>
                                </div>
                            </div>

                            {/* Spending progress bar */}
                            {budgetStatus?.monthly_limit_dollars && budgetStatus.monthly_limit_dollars > 0 && (
                                <div>
                                    <div className="flex items-center justify-between text-sm">
                                        <span className="text-gray-600 dark:text-gray-400">Token spending</span>
                                        <span className="font-medium text-gray-900 dark:text-white">
                                            ${budgetStatus.monthly_spend_dollars.toFixed(2)} / ${budgetStatus.monthly_limit_dollars.toFixed(2)}
                                        </span>
                                    </div>
                                    <div className="mt-2 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                        <div
                                            className={`h-full rounded-full transition-all ${(budgetStatus.monthly_spend_dollars / budgetStatus.monthly_limit_dollars) >= 0.9
                                                ? 'bg-red-500'
                                                : (budgetStatus.monthly_spend_dollars / budgetStatus.monthly_limit_dollars) >= 0.75
                                                    ? 'bg-yellow-500'
                                                    : 'bg-cyan-500'
                                                }`}
                                            style={{ width: `${Math.min(100, (budgetStatus.monthly_spend_dollars / budgetStatus.monthly_limit_dollars) * 100)}%` }}
                                        />
                                    </div>
                                </div>
                            )}

                            {/* Budget warning */}
                            {budgetStatus && !budgetStatus.allowed && (
                                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                                    <p className="text-sm text-red-800 dark:text-red-200">
                                        {budgetStatus.reason}
                                    </p>
                                </div>
                            )}

                            {/* Token totals */}
                            {tokenUsage?.totals && (
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                                    <div className="text-center">
                                        <div className="text-lg font-semibold text-gray-900 dark:text-white">
                                            {(tokenUsage.totals.total_requests ?? 0).toLocaleString()}
                                        </div>
                                        <div className="text-xs text-gray-500 dark:text-gray-400">requests</div>
                                    </div>
                                    <div className="text-center">
                                        <div className="text-lg font-semibold text-gray-900 dark:text-white">
                                            {(tokenUsage.totals.total_input_tokens ?? 0).toLocaleString()}
                                        </div>
                                        <div className="text-xs text-gray-500 dark:text-gray-400">input tokens</div>
                                    </div>
                                    <div className="text-center">
                                        <div className="text-lg font-semibold text-gray-900 dark:text-white">
                                            {(tokenUsage.totals.total_output_tokens ?? 0).toLocaleString()}
                                        </div>
                                        <div className="text-xs text-gray-500 dark:text-gray-400">output tokens</div>
                                    </div>
                                    <div className="text-center">
                                        <div className="text-lg font-semibold text-cyan-600 dark:text-cyan-400">
                                            ${(tokenUsage.totals.total_cost_dollars ?? 0).toFixed(4)}
                                        </div>
                                        <div className="text-xs text-gray-500 dark:text-gray-400">total cost</div>
                                    </div>
                                </div>
                            )}

                            {/* Per-model breakdown */}
                            {tokenUsage?.by_model && tokenUsage.by_model.length > 0 && (
                                <div className="overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
                                    <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                                        <thead className="bg-gray-50 dark:bg-gray-700/50">
                                            <tr>
                                                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Model</th>
                                                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">Requests</th>
                                                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">Input</th>
                                                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">Output</th>
                                                <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">Cost</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-200 dark:divide-gray-700 text-sm">
                                            {tokenUsage.by_model.map((row, i) => (
                                                <tr key={i}>
                                                    <td className="px-4 py-2 text-gray-900 dark:text-white">
                                                        <span className="text-xs text-gray-500 dark:text-gray-400">{row.provider}/</span>
                                                        {row.model}
                                                    </td>
                                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">
                                                        {row.request_count.toLocaleString()}
                                                    </td>
                                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">
                                                        {row.input_tokens.toLocaleString()}
                                                    </td>
                                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">
                                                        {row.output_tokens.toLocaleString()}
                                                    </td>
                                                    <td className="px-4 py-2 text-right font-medium text-gray-900 dark:text-white">
                                                        ${row.cost_dollars.toFixed(4)}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    ) : (
                        <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">
                            No token usage data available yet. Usage will appear here once your agents start processing tasks.
                        </p>
                    )}
                </div>
            </div>

            {/* Upgrade Options (show if not on highest tier) */}
            {billingStatus?.tier !== 'enterprise' && (
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                    <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                        <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                            Upgrade Your Plan
                        </h2>
                    </div>
                    <div className="p-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {/* Pro tier card */}
                            {billingStatus?.tier === 'free' && (
                                <div className="border-2 border-cyan-500 rounded-lg p-6 relative">
                                    <span className="absolute -top-3 left-4 px-2 bg-cyan-500 text-white text-xs font-medium rounded">
                                        Recommended
                                    </span>
                                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Pro</h3>
                                    <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                                        For builders who need serious throughput
                                    </p>
                                    <p className="mt-3 text-2xl font-bold text-gray-900 dark:text-white">
                                        $49<span className="text-sm font-normal text-gray-500">/mo</span>
                                    </p>
                                    <ul className="mt-4 space-y-2 text-sm text-gray-600 dark:text-gray-400">
                                        <li>5,000 tasks / month</li>
                                        <li>5 workers</li>
                                        <li>20 workspaces</li>
                                    </ul>
                                    <button
                                        onClick={() => handleUpgrade('pro')}
                                        disabled={upgrading === 'pro'}
                                        className="mt-4 w-full px-4 py-2 bg-cyan-600 text-white rounded-md hover:bg-cyan-700 disabled:opacity-50 transition-colors"
                                    >
                                        {upgrading === 'pro' ? 'Redirecting...' : 'Upgrade to Pro'}
                                    </button>
                                </div>
                            )}

                            {/* Enterprise tier card */}
                            <div className={`border border-gray-200 dark:border-gray-700 rounded-lg p-6 relative ${billingStatus?.tier === 'pro' ? 'border-2 border-indigo-500' : ''}`}>
                                {billingStatus?.tier === 'pro' && (
                                    <span className="absolute -top-3 left-4 px-2 bg-indigo-500 text-white text-xs font-medium rounded">
                                        Next tier
                                    </span>
                                )}
                                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Enterprise</h3>
                                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                                    Unlimited tasks, workers, and workspaces
                                </p>
                                <p className="mt-3 text-2xl font-bold text-gray-900 dark:text-white">
                                    $199<span className="text-sm font-normal text-gray-500">/mo</span>
                                </p>
                                <ul className="mt-4 space-y-2 text-sm text-gray-600 dark:text-gray-400">
                                    <li>Unlimited tasks / month</li>
                                    <li>Unlimited workers</li>
                                    <li>Unlimited workspaces</li>
                                </ul>
                                <button
                                    onClick={() => handleUpgrade('enterprise')}
                                    disabled={upgrading === 'enterprise'}
                                    className={`mt-4 w-full px-4 py-2 rounded-md transition-colors disabled:opacity-50 ${billingStatus?.tier === 'pro'
                                        ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                                        : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600'
                                        }`}
                                >
                                    {upgrading === 'enterprise' ? 'Redirecting...' : 'Upgrade to Enterprise'}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* FinOps: Alerts Banner */}
            {alertSummary && alertSummary.total > 0 && (
                <div className={`rounded-lg p-4 border ${alertSummary.critical > 0
                    ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
                    : 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'
                    }`}>
                    <div className="flex items-center gap-3">
                        <svg className={`h-5 w-5 ${alertSummary.critical > 0 ? 'text-red-500' : 'text-yellow-500'}`} fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                        </svg>
                        <div className="flex-1">
                            <p className={`text-sm font-medium ${alertSummary.critical > 0 ? 'text-red-800 dark:text-red-200' : 'text-yellow-800 dark:text-yellow-200'}`}>
                                {alertSummary.total} unacknowledged cost alert{alertSummary.total !== 1 ? 's' : ''}
                                {alertSummary.critical > 0 && ` (${alertSummary.critical} critical)`}
                            </p>
                        </div>
                    </div>
                </div>
            )}

            {/* FinOps: Forecast & Trend */}
            {(forecast || costTrend.length > 0) && (
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                    <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                        <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                            Cost Forecast &amp; Trends
                        </h2>
                        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                            Projected spend and daily usage patterns
                        </p>
                    </div>
                    <div className="p-6 space-y-6">
                        {/* Forecast cards */}
                        {forecast && (
                            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                                <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                                    <div className="text-2xl font-bold text-gray-900 dark:text-white">
                                        ${forecast.projected_cost_dollars.toFixed(2)}
                                    </div>
                                    <div className="text-sm text-gray-500 dark:text-gray-400">projected this month</div>
                                </div>
                                <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                                    <div className="text-2xl font-bold text-gray-900 dark:text-white">
                                        ${forecast.daily_average_dollars.toFixed(2)}
                                    </div>
                                    <div className="text-sm text-gray-500 dark:text-gray-400">daily average</div>
                                </div>
                                <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                                    <div className={`text-2xl font-bold ${forecast.trend === 'increasing' ? 'text-red-600 dark:text-red-400' :
                                        forecast.trend === 'decreasing' ? 'text-green-600 dark:text-green-400' :
                                            'text-gray-900 dark:text-white'
                                        }`}>
                                        {forecast.trend === 'increasing' ? '↑' : forecast.trend === 'decreasing' ? '↓' : '→'} {forecast.trend}
                                    </div>
                                    <div className="text-sm text-gray-500 dark:text-gray-400">spending trend</div>
                                </div>
                                <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-4">
                                    <div className="text-2xl font-bold text-gray-900 dark:text-white">
                                        {forecast.pct_change_vs_last_period !== null
                                            ? `${forecast.pct_change_vs_last_period > 0 ? '+' : ''}${forecast.pct_change_vs_last_period}%`
                                            : 'N/A'}
                                    </div>
                                    <div className="text-sm text-gray-500 dark:text-gray-400">vs last month</div>
                                </div>
                            </div>
                        )}

                        {forecast && (
                            <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                                <span className={`px-2 py-0.5 rounded-full ${forecast.confidence === 'high' ? 'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300' :
                                    forecast.confidence === 'medium' ? 'bg-yellow-100 dark:bg-yellow-900 text-yellow-700 dark:text-yellow-300' :
                                        'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                                    }`}>
                                    {forecast.confidence} confidence
                                </span>
                                <span>Day {forecast.days_elapsed} of {forecast.days_in_period}</span>
                            </div>
                        )}

                        {/* Cost trend mini chart (text-based bar chart) */}
                        {costTrend.length > 0 && (
                            <div>
                                <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Daily Cost (last 30 days)</h3>
                                <div className="space-y-1">
                                    {(() => {
                                        const maxCost = Math.max(...costTrend.map(d => d.cost_dollars), 0.001)
                                        const recent = costTrend.slice(-14) // Show last 14 days
                                        return recent.map((day, i) => (
                                            <div key={i} className="flex items-center gap-2 text-xs">
                                                <span className="w-20 text-gray-500 dark:text-gray-400 text-right">
                                                    {day.date.slice(5)}
                                                </span>
                                                <div className="flex-1 h-4 bg-gray-100 dark:bg-gray-700 rounded overflow-hidden">
                                                    <div
                                                        className="h-full bg-cyan-500 rounded"
                                                        style={{ width: `${Math.max(1, (day.cost_dollars / maxCost) * 100)}%` }}
                                                    />
                                                </div>
                                                <span className="w-16 text-right text-gray-600 dark:text-gray-400">
                                                    ${day.cost_dollars.toFixed(2)}
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
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                    <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                        <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                            Cost Anomalies
                        </h2>
                        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                            Unusual spending patterns detected today
                        </p>
                    </div>
                    <div className="p-6 space-y-3">
                        {anomalies.map((anomaly, i) => (
                            <div key={i} className={`rounded-lg p-4 border ${anomaly.severity === 'critical'
                                ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
                                : 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'
                                }`}>
                                <div className="flex items-start gap-3">
                                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${anomaly.severity === 'critical'
                                        ? 'bg-red-100 dark:bg-red-800 text-red-800 dark:text-red-200'
                                        : 'bg-yellow-100 dark:bg-yellow-800 text-yellow-800 dark:text-yellow-200'
                                        }`}>
                                        {anomaly.anomaly_type.replace('_', ' ')}
                                    </span>
                                    <div className="flex-1">
                                        <p className="text-sm text-gray-800 dark:text-gray-200">{anomaly.description}</p>
                                        {anomaly.model && (
                                            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                                                Model: {anomaly.provider}/{anomaly.model}
                                            </p>
                                        )}
                                    </div>
                                    <span className="text-xs text-gray-500 dark:text-gray-400">
                                        {anomaly.deviation_factor.toFixed(1)}x
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* FinOps: Cost Optimization Recommendations */}
            {recommendations.length > 0 && (
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                    <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                        <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                            Cost Optimization Recommendations
                        </h2>
                        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                            Actionable suggestions to reduce your AI spend
                        </p>
                    </div>
                    <div className="p-6 space-y-4">
                        {recommendations.map((rec) => (
                            <div key={rec.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4">
                                <div className="flex items-start justify-between">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2">
                                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${rec.recommendation_type === 'model_downgrade' ? 'bg-blue-100 dark:bg-blue-800 text-blue-800 dark:text-blue-200' :
                                                rec.recommendation_type === 'cache_optimization' ? 'bg-green-100 dark:bg-green-800 text-green-800 dark:text-green-200' :
                                                    'bg-purple-100 dark:bg-purple-800 text-purple-800 dark:text-purple-200'
                                                }`}>
                                                {rec.recommendation_type.replace('_', ' ')}
                                            </span>
                                            <span className="text-sm font-medium text-green-600 dark:text-green-400">
                                                Save ~${rec.estimated_savings_dollars.toFixed(2)}/mo ({rec.estimated_savings_percent}%)
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
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                    <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                        <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                            Active Cost Alerts
                        </h2>
                    </div>
                    <div className="p-6 space-y-3">
                        {alerts.map((alert) => (
                            <div key={alert.id} className={`flex items-start gap-3 rounded-lg p-3 border ${alert.severity === 'critical'
                                ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'
                                : alert.severity === 'warning'
                                    ? 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-800'
                                    : 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
                                }`}>
                                <div className="flex-1">
                                    <h4 className="text-sm font-medium text-gray-900 dark:text-white">{alert.title}</h4>
                                    <p className="text-sm text-gray-600 dark:text-gray-400">{alert.message}</p>
                                    {alert.created_at && (
                                        <p className="mt-1 text-xs text-gray-400">{new Date(alert.created_at).toLocaleString()}</p>
                                    )}
                                </div>
                                <button
                                    onClick={() => handleAcknowledgeAlert(alert.id)}
                                    className="px-3 py-1 text-xs font-medium text-gray-600 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded hover:bg-gray-50 dark:hover:bg-gray-600"
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
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                    <div className="p-6 border-b border-gray-200 dark:border-gray-700">
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
                                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Policy</th>
                                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Scope</th>
                                        <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">Warn At</th>
                                        <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">Block At</th>
                                        <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 dark:text-gray-400">Period</th>
                                        <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 dark:text-gray-400">Status</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200 dark:divide-gray-700 text-sm">
                                    {policies.map((policy) => (
                                        <tr key={policy.id}>
                                            <td className="px-4 py-2 text-gray-900 dark:text-white font-medium">{policy.name}</td>
                                            <td className="px-4 py-2 text-gray-600 dark:text-gray-400">{policy.scope}</td>
                                            <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">
                                                {policy.soft_limit_cents ? `$${(policy.soft_limit_cents / 100).toFixed(0)}` : '—'}
                                            </td>
                                            <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">
                                                {policy.hard_limit_cents ? `$${(policy.hard_limit_cents / 100).toFixed(0)}` : '—'}
                                            </td>
                                            <td className="px-4 py-2 text-center text-gray-600 dark:text-gray-400">{policy.period}</td>
                                            <td className="px-4 py-2 text-center">
                                                <span className={`px-2 py-0.5 rounded-full text-xs ${policy.is_active
                                                    ? 'bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300'
                                                    : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
                                                    }`}>
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
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                    <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                        Billing FAQ
                    </h2>
                </div>
                <div className="p-6 space-y-4">
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
                            New tasks will be blocked until your limit resets or you upgrade. Running tasks won&apos;t be interrupted.
                        </p>
                    </div>
                    <div>
                        <h4 className="font-medium text-gray-900 dark:text-white">
                            Can I downgrade?
                        </h4>
                        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                            Yes, use &quot;Manage billing&quot; to change or cancel your plan. Changes take effect at your next billing date.
                        </p>
                    </div>
                    <div>
                        <h4 className="font-medium text-gray-900 dark:text-white">
                            Do I use my own API keys or yours?
                        </h4>
                        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                            Bring Your Own Model (BYOM). You add your own API keys (Anthropic, OpenAI, Google, etc.) in Settings. Keys are stored securely in HashiCorp Vault. The platform tracks your token usage and applies billing based on your plan&apos;s billing model (subscription, prepaid, or metered).
                        </p>
                    </div>
                    <div>
                        <h4 className="font-medium text-gray-900 dark:text-white">
                            How does token billing work?
                        </h4>
                        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                            Every AI request consumes tokens. We track input, output, reasoning, and cache tokens per request and deduct from your prepaid credit balance. Each model has transparent per-million-token pricing. You can set monthly spending limits and add credits anytime.
                        </p>
                    </div>
                    <div>
                        <h4 className="font-medium text-gray-900 dark:text-white">
                            What happens if my token credit runs out?
                        </h4>
                        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                            New AI requests will be paused until you add more credits. Running tasks won&apos;t be interrupted mid-stream. You can add credits at any time from this page.
                        </p>
                    </div>
                </div>
            </div>
        </div>
    )
}

export default function BillingPage() {
    return (
        <Suspense fallback={
            <div className="flex items-center justify-center min-h-100">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
            </div>
        }>
            <BillingContent />
        </Suspense>
    )
}
