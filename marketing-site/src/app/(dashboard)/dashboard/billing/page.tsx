'use client'

import { useState, useEffect, Suspense } from 'react'
import { useSession } from 'next-auth/react'
import { useSearchParams } from 'next/navigation'

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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

const tierDetails: Record<string, { price: string; description: string; color: string }> = {
    free: {
        price: '$0/mo',
        description: 'Try CodeTether with no commitment',
        color: 'gray',
    },
    pro: {
        price: '$297/mo',
        description: 'For builders replacing Zapier + VAs',
        color: 'cyan',
    },
    agency: {
        price: '$497/mo',
        description: 'For teams and multi-client ops',
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
        }
    }, [authStatus])

    const loadBillingStatus = async () => {
        setLoading(true)
        setError(null)

        try {
            const response = await fetch(`${API_BASE_URL}/v1/users/billing/status`, {
                headers: getAuthHeaders(),
            })

            if (!response.ok) {
                const data = await response.json()
                throw new Error(data.detail || 'Failed to load billing status')
            }

            const data = await response.json()
            setBillingStatus(data)
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
            const baseUrl = typeof window !== 'undefined' ? window.location.origin : ''

            const response = await fetch(`${API_BASE_URL}/v1/users/billing/checkout`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    tier: tierId,
                    success_url: `${baseUrl}/dashboard/billing?upgraded=true`,
                    cancel_url: `${baseUrl}/dashboard/billing`,
                }),
            })

            if (!response.ok) {
                const data = await response.json()
                throw new Error(data.detail || 'Failed to create checkout session')
            }

            const data = await response.json()

            if (data.checkout_url) {
                window.location.href = data.checkout_url
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
            const baseUrl = typeof window !== 'undefined' ? window.location.origin : ''

            const response = await fetch(`${API_BASE_URL}/v1/users/billing/portal`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({
                    return_url: `${baseUrl}/dashboard/billing`,
                }),
            })

            if (!response.ok) {
                const data = await response.json()
                throw new Error(data.detail || 'Failed to create portal session')
            }

            const data = await response.json()

            if (data.portal_url) {
                window.location.href = data.portal_url
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
                                Running low on tasks. Upgrade to Pro for 300 tasks/month.
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

            {/* Upgrade Options (show if not on highest tier) */}
            {billingStatus?.tier !== 'agency' && (
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
                                        For builders replacing Zapier + VAs
                                    </p>
                                    <p className="mt-3 text-2xl font-bold text-gray-900 dark:text-white">
                                        $297<span className="text-sm font-normal text-gray-500">/mo</span>
                                    </p>
                                    <ul className="mt-4 space-y-2 text-sm text-gray-600 dark:text-gray-400">
                                        <li>300 tasks / month</li>
                                        <li>3 concurrent tasks</li>
                                        <li>30 min max runtime</li>
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

                            {/* Agency tier card */}
                            <div className={`border border-gray-200 dark:border-gray-700 rounded-lg p-6 relative ${billingStatus?.tier === 'pro' ? 'border-2 border-indigo-500' : ''}`}>
                                {billingStatus?.tier === 'pro' && (
                                    <span className="absolute -top-3 left-4 px-2 bg-indigo-500 text-white text-xs font-medium rounded">
                                        Next tier
                                    </span>
                                )}
                                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Agency</h3>
                                <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                                    For teams and multi-client ops
                                </p>
                                <p className="mt-3 text-2xl font-bold text-gray-900 dark:text-white">
                                    $497<span className="text-sm font-normal text-gray-500">/mo</span>
                                </p>
                                <ul className="mt-4 space-y-2 text-sm text-gray-600 dark:text-gray-400">
                                    <li>2,000 tasks / month</li>
                                    <li>10 concurrent tasks</li>
                                    <li>60 min max runtime</li>
                                </ul>
                                <button
                                    onClick={() => handleUpgrade('agency')}
                                    disabled={upgrading === 'agency'}
                                    className={`mt-4 w-full px-4 py-2 rounded-md transition-colors disabled:opacity-50 ${billingStatus?.tier === 'pro'
                                            ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                                            : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 hover:bg-gray-200 dark:hover:bg-gray-600'
                                        }`}
                                >
                                    {upgrading === 'agency' ? 'Redirecting...' : 'Upgrade to Agency'}
                                </button>
                            </div>
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
