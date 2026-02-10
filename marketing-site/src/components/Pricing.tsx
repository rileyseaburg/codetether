'use client'

import { useState } from 'react'
import { useSession } from 'next-auth/react'
import clsx from 'clsx'

import { Button } from '@/components/Button'
import { Container } from '@/components/Container'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.codetether.run'

const plans = [
    {
        id: 'free',
        name: 'Free',
        featured: false,
        price: { monthly: '$0', annually: '$0' },
        description: 'Try before you buy. Perfect for testing workflows.',
        bestFor: 'Testing & experimentation',
        tokenInfo: '$5 token credit included',
        button: {
            label: 'Start Free',
            href: '/register',
            action: 'signup',
        },
        features: [
            '10 tasks / month',
            '1 concurrent task',
            '10 min max runtime',
            '$5 prepaid token credit',
            'Per-token usage tracking',
            'Mandatory auth (HMAC-SHA256)',
            'Full audit trail',
            'Community Discord',
        ],
        limits: {
            tasks: 10,
            concurrency: 1,
            runtime: '10 min',
        },
        logomarkClassName: 'fill-gray-500',
    },
    {
        id: 'pro',
        name: 'Pro',
        featured: true,
        price: { monthly: '$297', annually: '$297' },
        description: 'For automation builders replacing Zapier + VAs.',
        bestFor: 'Solopreneurs & automation builders',
        tokenInfo: '$50 token credit / month included',
        button: {
            label: 'Upgrade to Pro',
            href: '/register',
            action: 'checkout',
        },
        features: [
            '300 tasks / month',
            '3 concurrent tasks',
            '30 min max runtime',
            '$50/mo prepaid token credit',
            'Per-model cost breakdown',
            'Monthly spending limits',
            'Mandatory auth + audit trail',
            'Ed25519 plugin signing',
            'OPA Rego authorization policies',
            'RLM unlimited context',
            'Reply-to-continue',
        ],
        limits: {
            tasks: 300,
            concurrency: 3,
            runtime: '30 min',
        },
        logomarkClassName: 'fill-cyan-500',
    },
    {
        id: 'agency',
        name: 'Agency',
        featured: false,
        price: { monthly: '$497', annually: '$497' },
        description: 'For teams running client automations at scale.',
        bestFor: 'Agencies & teams',
        tokenInfo: '$150 token credit / month included',
        button: {
            label: 'Upgrade to Agency',
            href: '/register',
            action: 'checkout',
        },
        features: [
            '2,000 tasks / month',
            '10 concurrent tasks',
            '60 min max runtime',
            '$150/mo prepaid token credit',
            'Per-tenant token isolation',
            'Custom spending limits & alerts',
            'Everything in Pro',
            'K8s self-deployment',
            'Team workspaces',
            'Dedicated support',
            'Custom security policies (OPA)',
        ],
        limits: {
            tasks: 2000,
            concurrency: 10,
            runtime: '60 min',
        },
        logomarkClassName: 'fill-gray-900',
    },
]

function CheckIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" aria-hidden="true" {...props}>
            <path
                d="M9.307 12.248a.75.75 0 1 0-1.114 1.004l1.114-1.004ZM11 15.25l-.557.502a.75.75 0 0 0 1.15-.043L11 15.25Zm4.844-5.041a.75.75 0 0 0-1.188-.918l1.188.918Zm-7.651 3.043 2.25 2.5 1.114-1.004-2.25-2.5-1.114 1.004Zm3.4 2.457 4.25-5.5-1.187-.918-4.25 5.5 1.188.918Z"
                fill="currentColor"
            />
        </svg>
    )
}

function Plan({
    id,
    name,
    price,
    description,
    bestFor,
    tokenInfo,
    button,
    features,
    limits,
    featured,
    activePeriod,
    onUpgrade,
    upgrading,
}: {
    id: string
    name: string
    price: {
        monthly: string
        annually: string
    }
    description: string
    bestFor: string
    tokenInfo: string
    button: {
        label: string
        href: string
        action: string
    }
    features: Array<string>
    limits: {
        tasks: number
        concurrency: number
        runtime: string
    }
    featured: boolean
    activePeriod: 'monthly' | 'annually'
    onUpgrade: (tierId: string) => void
    upgrading: string | null
}) {
    const isUpgrading = upgrading === id

    const handleClick = (e: React.MouseEvent) => {
        if (button.action === 'checkout') {
            e.preventDefault()
            onUpgrade(id)
        }
        // For 'signup' action, let the link work normally
    }

    return (
        <section
            className={clsx(
                'flex flex-col overflow-hidden rounded-3xl p-6 shadow-lg shadow-gray-900/5 dark:shadow-black/20',
                featured ? 'order-first bg-gray-900 lg:order-none' : 'bg-white dark:bg-gray-800',
            )}
        >
            <h3
                className={clsx(
                    'flex items-center text-sm font-semibold',
                    featured ? 'text-white' : 'text-gray-900 dark:text-white',
                )}
            >
                <span>{name}</span>
                {featured && (
                    <span className="ml-3 rounded-full bg-cyan-500 px-2.5 py-0.5 text-xs font-medium text-white">
                        Most Popular
                    </span>
                )}
            </h3>
            <p
                className={clsx(
                    'mt-5 flex text-3xl tracking-tight',
                    featured ? 'text-white' : 'text-gray-900 dark:text-white',
                )}
            >
                <span>{price[activePeriod]}</span>
                {price[activePeriod] !== '$0' && (
                    <span className="ml-1 text-sm font-normal text-gray-500 dark:text-gray-400">/mo</span>
                )}
            </p>
            <p
                className={clsx(
                    'mt-3 text-sm',
                    featured ? 'text-gray-300' : 'text-gray-700 dark:text-gray-300',
                )}
            >
                {description}
            </p>
            <p className="mt-2 text-xs font-medium text-cyan-500 dark:text-cyan-400">
                Best for: {bestFor}
            </p>
            <p className={clsx(
                'mt-1 text-xs font-medium',
                featured ? 'text-green-400' : 'text-green-600 dark:text-green-400',
            )}>
                {tokenInfo}
            </p>

            {/* Limits highlight */}
            <div className={clsx(
                'mt-4 rounded-lg p-3',
                featured ? 'bg-gray-800' : 'bg-gray-50 dark:bg-gray-700/50',
            )}>
                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                    <div>
                        <div className={clsx(
                            'font-semibold',
                            featured ? 'text-cyan-400' : 'text-cyan-600 dark:text-cyan-400',
                        )}>
                            {limits.tasks.toLocaleString()}
                        </div>
                        <div className={clsx(
                            featured ? 'text-gray-400' : 'text-gray-500 dark:text-gray-400',
                        )}>
                            tasks/mo
                        </div>
                    </div>
                    <div>
                        <div className={clsx(
                            'font-semibold',
                            featured ? 'text-cyan-400' : 'text-cyan-600 dark:text-cyan-400',
                        )}>
                            {limits.concurrency}
                        </div>
                        <div className={clsx(
                            featured ? 'text-gray-400' : 'text-gray-500 dark:text-gray-400',
                        )}>
                            concurrent
                        </div>
                    </div>
                    <div>
                        <div className={clsx(
                            'font-semibold',
                            featured ? 'text-cyan-400' : 'text-cyan-600 dark:text-cyan-400',
                        )}>
                            {limits.runtime}
                        </div>
                        <div className={clsx(
                            featured ? 'text-gray-400' : 'text-gray-500 dark:text-gray-400',
                        )}>
                            runtime
                        </div>
                    </div>
                </div>
            </div>

            <div className="order-last mt-6">
                <ul
                    role="list"
                    className={clsx(
                        '-my-2 divide-y text-sm',
                        featured
                            ? 'divide-gray-800 text-gray-300'
                            : 'divide-gray-200 dark:divide-gray-700 text-gray-700 dark:text-gray-300',
                    )}
                >
                    {features.map((feature) => (
                        <li key={feature} className="flex py-2">
                            <CheckIcon
                                className={clsx(
                                    'h-6 w-6 flex-none',
                                    featured ? 'text-cyan-400' : 'text-cyan-500',
                                )}
                            />
                            <span className="ml-4">{feature}</span>
                        </li>
                    ))}
                </ul>
            </div>
            <Button
                variant="solid"
                href={button.action === 'signup' ? button.href : undefined}
                onClick={handleClick}
                color={featured ? 'cyan' : 'gray'}
                className="mt-6"
                aria-label={`${button.label} on the ${name} plan`}
                disabled={isUpgrading}
            >
                {isUpgrading ? 'Redirecting...' : button.label}
            </Button>
        </section>
    )
}

export function Pricing() {
    const { data: session, status } = useSession()
    const [activePeriod, setActivePeriod] = useState<'monthly' | 'annually'>('monthly')
    const [upgrading, setUpgrading] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)

    const handleUpgrade = async (tierId: string) => {
        // If not logged in, redirect to register
        if (status !== 'authenticated') {
            window.location.href = '/register'
            return
        }

        setUpgrading(tierId)
        setError(null)

        try {
            const baseUrl = typeof window !== 'undefined' ? window.location.origin : ''

            const response = await fetch(`${API_BASE_URL}/v1/users/billing/checkout`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    // @ts-ignore
                    'Authorization': `Bearer ${session?.accessToken}`,
                },
                body: JSON.stringify({
                    tier: tierId,
                    success_url: `${baseUrl}/dashboard/billing?upgraded=true`,
                    cancel_url: `${baseUrl}/#pricing`,
                }),
            })

            if (!response.ok) {
                const data = await response.json()
                throw new Error(data.detail || 'Failed to create checkout session')
            }

            const data = await response.json()

            // Redirect to Stripe Checkout
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

    return (
        <section
            id="pricing"
            aria-labelledby="pricing-title"
            className="border-t border-gray-200 dark:border-gray-800 bg-gray-100 dark:bg-gray-900 py-20 sm:py-32"
        >
            <Container>
                <div className="mx-auto max-w-2xl text-center">
                    <h2
                        id="pricing-title"
                        className="text-3xl font-medium tracking-tight text-gray-900 dark:text-white"
                    >
                        Simple Pricing. Real Results.
                    </h2>
                    <p className="mt-2 text-lg text-gray-600 dark:text-gray-300">
                        Start free. Upgrade when you&apos;re hooked. Cancel anytime.
                    </p>
                </div>

                {/* Error message */}
                {error && (
                    <div className="mx-auto mt-8 max-w-md">
                        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                            <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
                        </div>
                    </div>
                )}

                <div className="mx-auto mt-16 grid max-w-2xl grid-cols-1 items-start gap-x-8 gap-y-10 sm:mt-20 lg:max-w-none lg:grid-cols-3">
                    {plans.map((plan) => (
                        <Plan
                            key={plan.name}
                            {...plan}
                            activePeriod={activePeriod}
                            onUpgrade={handleUpgrade}
                            upgrading={upgrading}
                        />
                    ))}
                </div>

                {/* Token Billing */}
                <div className="mx-auto mt-16 max-w-3xl">
                    <h3 className="text-lg font-medium text-gray-900 dark:text-white text-center">
                        Transparent Token-Based Billing
                    </h3>
                    <p className="mt-2 text-sm text-gray-600 dark:text-gray-400 text-center">
                        Every plan includes prepaid token credits. You only pay for what your agents actually use,
                        tracked per-request with full model-level cost breakdowns.
                    </p>
                    <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        <div className="p-4 rounded-lg bg-white dark:bg-gray-800 shadow text-center">
                            <div className="text-2xl font-bold text-cyan-600 dark:text-cyan-400">Per-Token</div>
                            <div className="mt-1 text-xs text-gray-600 dark:text-gray-400">
                                Billed by actual input, output, cache &amp; reasoning tokens
                            </div>
                        </div>
                        <div className="p-4 rounded-lg bg-white dark:bg-gray-800 shadow text-center">
                            <div className="text-2xl font-bold text-cyan-600 dark:text-cyan-400">Per-Model</div>
                            <div className="mt-1 text-xs text-gray-600 dark:text-gray-400">
                                Each AI model priced at cost. No hidden markup.
                            </div>
                        </div>
                        <div className="p-4 rounded-lg bg-white dark:bg-gray-800 shadow text-center">
                            <div className="text-2xl font-bold text-cyan-600 dark:text-cyan-400">Prepaid</div>
                            <div className="mt-1 text-xs text-gray-600 dark:text-gray-400">
                                Credits included with your plan. Add more anytime.
                            </div>
                        </div>
                        <div className="p-4 rounded-lg bg-white dark:bg-gray-800 shadow text-center">
                            <div className="text-2xl font-bold text-cyan-600 dark:text-cyan-400">Limits</div>
                            <div className="mt-1 text-xs text-gray-600 dark:text-gray-400">
                                Set monthly spending caps to stay in budget.
                            </div>
                        </div>
                    </div>

                    {/* Model pricing table */}
                    <div className="mt-8 overflow-hidden rounded-lg bg-white dark:bg-gray-800 shadow">
                        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
                            <h4 className="text-sm font-medium text-gray-900 dark:text-white">Model Pricing (per 1M tokens)</h4>
                        </div>
                        <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                            <thead className="bg-gray-50 dark:bg-gray-700/50">
                                <tr>
                                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Model</th>
                                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">Input</th>
                                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">Output</th>
                                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400">Cache Read</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200 dark:divide-gray-700 text-sm">
                                <tr>
                                    <td className="px-4 py-2 text-gray-900 dark:text-white">Claude Opus 4.5</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">$5.00</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">$25.00</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">$0.50</td>
                                </tr>
                                <tr>
                                    <td className="px-4 py-2 text-gray-900 dark:text-white">Claude Sonnet 4</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">$3.00</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">$15.00</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">$0.30</td>
                                </tr>
                                <tr>
                                    <td className="px-4 py-2 text-gray-900 dark:text-white">GPT-4.1</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">$2.00</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">$8.00</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">&mdash;</td>
                                </tr>
                                <tr>
                                    <td className="px-4 py-2 text-gray-900 dark:text-white">GPT-4.1 Mini</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">$0.40</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">$1.60</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">&mdash;</td>
                                </tr>
                                <tr>
                                    <td className="px-4 py-2 text-gray-900 dark:text-white">o3</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">$2.00</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">$8.00</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">&mdash;</td>
                                </tr>
                                <tr>
                                    <td className="px-4 py-2 text-gray-900 dark:text-white">Gemini 2.5 Pro</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">$1.25</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">$10.00</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">&mdash;</td>
                                </tr>
                                <tr>
                                    <td className="px-4 py-2 text-gray-900 dark:text-white">Gemini 2.5 Flash</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">$0.15</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">$0.60</td>
                                    <td className="px-4 py-2 text-right text-gray-600 dark:text-gray-400">&mdash;</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* How it works */}
                <div className="mx-auto mt-16 max-w-2xl text-center">
                    <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                        How It Works
                    </h3>
                    <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3 text-sm text-gray-600 dark:text-gray-400">
                        <div className="p-4 rounded-lg bg-white dark:bg-gray-800 shadow">
                            <div className="text-2xl mb-2">1. Trigger</div>
                            <div className="font-semibold text-gray-900 dark:text-white mb-1">Webhook or Dashboard</div>
                            <p>Send a POST request or start from the web interface</p>
                        </div>
                        <div className="p-4 rounded-lg bg-white dark:bg-gray-800 shadow">
                            <div className="text-2xl mb-2">2. Process</div>
                            <div className="font-semibold text-gray-900 dark:text-white mb-1">AI Agent Works</div>
                            <p>RLM processes your task with unlimited context</p>
                        </div>
                        <div className="p-4 rounded-lg bg-white dark:bg-gray-800 shadow">
                            <div className="text-2xl mb-2">3. Deliver</div>
                            <div className="font-semibold text-gray-900 dark:text-white mb-1">Email or Callback</div>
                            <p>Get files in your inbox or webhook callback</p>
                        </div>
                    </div>
                </div>

                {/* Money-back guarantee */}
                <div className="mx-auto mt-12 max-w-xl text-center">
                    <div className="inline-flex items-center gap-2 rounded-full bg-green-100 dark:bg-green-900/30 px-4 py-2 text-sm font-medium text-green-700 dark:text-green-400">
                        <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                        14-day money-back guarantee. No questions asked.
                    </div>
                </div>
            </Container>
        </section>
    )
}
