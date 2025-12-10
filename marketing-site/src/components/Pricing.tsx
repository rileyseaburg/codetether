'use client'

import { useState } from 'react'
import clsx from 'clsx'

import { Button } from '@/components/Button'
import { Container } from '@/components/Container'

const plans = [
    {
        name: 'Open Source',
        featured: false,
        price: { monthly: 'Free', annually: 'Free' },
        description: 'Self-host CodeTether with full protocol support.',
        button: {
            label: 'Get Started',
            href: 'https://github.com/rileyseaburg/A2A-Server-MCP',
        },
        features: [
            'Full A2A protocol implementation',
            'MCP tool integration',
            'Redis message broker',
            'Distributed workers',
            'Community support',
            'Helm charts for Kubernetes',
            'Apache 2.0 license',
        ],
        logomarkClassName: 'fill-gray-500',
    },
    {
        name: 'Pro',
        featured: true,
        price: { monthly: '$299', annually: '$249' },
        description: 'Managed CodeTether for production teams.',
        button: {
            label: 'Start Free Trial',
            href: '/register',
        },
        features: [
            'Everything in Open Source',
            'Managed cloud hosting',
            'Multi-region deployment',
            'Session history & resumption',
            'Real-time output streaming',
            'Keycloak SSO integration',
            'Email support + 99.9% SLA',
            'Usage analytics dashboard',
        ],
        logomarkClassName: 'fill-cyan-500',
    },
    {
        name: 'Enterprise',
        featured: false,
        price: { monthly: 'Custom', annually: 'Custom' },
        description: 'For regulated industries and custom deployments.',
        button: {
            label: 'Contact Sales',
            href: 'mailto:enterprise@codetether.run?subject=CodeTether%20Enterprise%20Inquiry',
        },
        features: [
            'Everything in Pro',
            'Dedicated VPC / single-tenant',
            'Custom SLA (up to 99.99%)',
            'SAML/LDAP + fine-grained RBAC',
            'Audit logs & compliance',
            'Secret management (Vault/SSM)',
            'On-premise deployment',
            '24/7 support + dedicated TAM',
            'Migration assistance',
        ],
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
    name,
    price,
    description,
    button,
    features,
    featured,
    activePeriod,
}: {
    name: string
    price: {
        monthly: string
        annually: string
    }
    description: string
    button: {
        label: string
        href: string
    }
    features: Array<string>
    featured: boolean
    activePeriod: 'monthly' | 'annually'
}) {
    return (
        <section
            className={clsx(
                'flex flex-col overflow-hidden rounded-3xl p-6 shadow-lg shadow-gray-900/5',
                featured ? 'order-first bg-gray-900 lg:order-none' : 'bg-white',
            )}
        >
            <h3
                className={clsx(
                    'flex items-center text-sm font-semibold',
                    featured ? 'text-white' : 'text-gray-900',
                )}
            >
                <span>{name}</span>
                {featured && (
                    <span className="ml-3 rounded-full bg-cyan-500 px-2.5 py-0.5 text-xs font-medium text-white">
                        Popular
                    </span>
                )}
            </h3>
            <p
                className={clsx(
                    'mt-5 flex text-3xl tracking-tight',
                    featured ? 'text-white' : 'text-gray-900',
                )}
            >
                {price.monthly === price.annually ? (
                    price.monthly
                ) : (
                    <>
                        <span>{price[activePeriod]}</span>
                        {price[activePeriod] !== 'Custom' && price[activePeriod] !== 'Free' && (
                            <span className="ml-1 text-sm font-normal text-gray-500">/mo</span>
                        )}
                    </>
                )}
            </p>
            {activePeriod === 'annually' && price.monthly !== price.annually && price.annually !== 'Custom' && price.annually !== 'Free' && (
                <p className={clsx('mt-1 text-sm', featured ? 'text-gray-400' : 'text-gray-500')}>
                    Billed annually (save 17%)
                </p>
            )}
            <p
                className={clsx(
                    'mt-3 text-sm',
                    featured ? 'text-gray-300' : 'text-gray-700',
                )}
            >
                {description}
            </p>
            <div className="order-last mt-6">
                <ul
                    role="list"
                    className={clsx(
                        '-my-2 divide-y text-sm',
                        featured
                            ? 'divide-gray-800 text-gray-300'
                            : 'divide-gray-200 text-gray-700',
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
                href={button.href}
                color={featured ? 'cyan' : 'gray'}
                className="mt-6"
                aria-label={`${button.label} on the ${name} plan`}
            >
                {button.label}
            </Button>
        </section>
    )
}

export function Pricing() {
    let [activePeriod, setActivePeriod] = useState<'monthly' | 'annually'>(
        'annually',
    )

    return (
        <section
            id="pricing"
            aria-labelledby="pricing-title"
            className="border-t border-gray-200 bg-gray-100 py-20 sm:py-32"
        >
            <Container>
                <div className="mx-auto max-w-2xl text-center">
                    <h2
                        id="pricing-title"
                        className="text-3xl font-medium tracking-tight text-gray-900"
                    >
                        Simple, transparent pricing
                    </h2>
                    <p className="mt-2 text-lg text-gray-600">
                        Start free with open source, or get managed hosting and premium support.
                    </p>
                </div>

                <div className="mt-8 flex justify-center">
                    <div className="relative">
                        <div className="flex rounded-full bg-white p-1 shadow-sm ring-1 ring-gray-200">
                            {(['monthly', 'annually'] as const).map((period) => (
                                <button
                                    key={period}
                                    className={clsx(
                                        'px-4 py-2 text-sm font-medium transition-colors',
                                        activePeriod === period
                                            ? 'rounded-full bg-gray-900 text-white'
                                            : 'text-gray-700 hover:text-gray-900',
                                    )}
                                    onClick={() => setActivePeriod(period)}
                                >
                                    {period === 'monthly' ? 'Monthly' : 'Annually'}
                                </button>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="mx-auto mt-16 grid max-w-2xl grid-cols-1 items-start gap-x-8 gap-y-10 sm:mt-20 lg:max-w-none lg:grid-cols-3">
                    {plans.map((plan) => (
                        <Plan key={plan.name} {...plan} activePeriod={activePeriod} />
                    ))}
                </div>
            </Container>
        </section>
    )
}
