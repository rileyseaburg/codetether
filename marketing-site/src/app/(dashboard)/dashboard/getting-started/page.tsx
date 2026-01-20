'use client'

import Link from 'next/link'

const ZAPIER_INVITE_LINK = 'https://zapier.com/developer/public-invite/235522/dc2a275ee1ca4688be5a4f18bf214ecb/'

function ZapierIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="currentColor" {...props}>
            <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 14.036h-3.43l2.426 2.426a.5.5 0 010 .707l-.707.707a.5.5 0 01-.707 0l-2.426-2.426v3.43a.5.5 0 01-.5.5h-1a.5.5 0 01-.5-.5v-3.43l-2.426 2.426a.5.5 0 01-.707 0l-.707-.707a.5.5 0 010-.707l2.426-2.426h-3.43a.5.5 0 01-.5-.5v-1a.5.5 0 01.5-.5h3.43L7.21 9.61a.5.5 0 010-.707l.707-.707a.5.5 0 01.707 0l2.426 2.426v-3.43a.5.5 0 01.5-.5h1a.5.5 0 01.5.5v3.43l2.426-2.426a.5.5 0 01.707 0l.707.707a.5.5 0 010 .707l-2.426 2.426h3.43a.5.5 0 01.5.5v1a.5.5 0 01-.5.5z"/>
        </svg>
    )
}

function CheckIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
    )
}

function ArrowRightIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
        </svg>
    )
}

function TerminalIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
    )
}

function WebhookIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
        </svg>
    )
}

const integrationMethods = [
    {
        name: 'Zapier',
        description: 'Connect CodeTether to 6,000+ apps with no code. Create tasks from emails, Slack messages, form submissions, and more.',
        icon: ZapierIcon,
        color: 'bg-orange-500',
        href: ZAPIER_INVITE_LINK,
        external: true,
        featured: true,
        features: [
            'Trigger tasks from any Zapier-connected app',
            'Send messages to AI agents automatically',
            'Search and monitor task status',
            'No coding required'
        ],
        cta: 'Connect with Zapier',
    },
    {
        name: 'REST API',
        description: 'Full programmatic access to create tasks, send messages, and monitor agent activity.',
        icon: TerminalIcon,
        color: 'bg-indigo-500',
        href: 'https://docs.codetether.run/api',
        external: true,
        featured: false,
        features: [
            'Create and manage tasks programmatically',
            'Real-time webhooks for task updates',
            'Full conversation history access',
            'Bearer token authentication'
        ],
        cta: 'View API Docs',
    },
    {
        name: 'Webhooks',
        description: 'Receive real-time notifications when tasks complete, fail, or need attention.',
        icon: WebhookIcon,
        color: 'bg-purple-500',
        href: '/dashboard/settings',
        external: false,
        featured: false,
        features: [
            'Task completion notifications',
            'Error and failure alerts',
            'Custom payload formatting',
            'Retry with exponential backoff'
        ],
        cta: 'Configure Webhooks',
    },
]

const quickStartSteps = [
    {
        step: 1,
        title: 'Connect Zapier',
        description: 'Click the button below to add CodeTether to your Zapier account.',
        action: { label: 'Add to Zapier', href: ZAPIER_INVITE_LINK, external: true },
    },
    {
        step: 2,
        title: 'Create Your First Zap',
        description: 'Use any trigger (Gmail, Slack, etc.) and add CodeTether\'s "Create Task" action.',
        action: { label: 'Zapier Dashboard', href: 'https://zapier.com/app/zaps', external: true },
    },
    {
        step: 3,
        title: 'Monitor Results',
        description: 'View task progress and AI responses in your CodeTether dashboard.',
        action: { label: 'View Tasks', href: '/dashboard/tasks', external: false },
    },
]

const zapierUseCases = [
    {
        trigger: 'New email in Gmail',
        action: 'Create task to analyze and draft response',
        icon: '📧',
    },
    {
        trigger: 'New Slack message',
        action: 'Send to AI agent for code review',
        icon: '💬',
    },
    {
        trigger: 'New GitHub issue',
        action: 'Auto-create task to investigate bug',
        icon: '🐛',
    },
    {
        trigger: 'New Typeform submission',
        action: 'Process form data with AI',
        icon: '📝',
    },
    {
        trigger: 'Scheduled (daily/weekly)',
        action: 'Run automated code analysis',
        icon: '🕐',
    },
    {
        trigger: 'New Trello card',
        action: 'Create implementation task',
        icon: '📋',
    },
]

export default function GettingStartedPage() {
    return (
        <div className="space-y-8 pb-12">
            {/* Hero Section */}
            <div className="rounded-2xl bg-gradient-to-r from-orange-500 to-orange-600 p-8 text-white">
                <div className="flex items-center gap-3 mb-4">
                    <ZapierIcon className="h-10 w-10" />
                    <span className="text-sm font-medium bg-white/20 px-3 py-1 rounded-full">Recommended</span>
                </div>
                <h1 className="text-3xl font-bold mb-2">Get Started with Zapier</h1>
                <p className="text-lg text-orange-100 mb-6 max-w-2xl">
                    The fastest way to automate CodeTether. Connect to 6,000+ apps and start 
                    triggering AI tasks from emails, Slack, forms, and more — no code required.
                </p>
                <a
                    href={ZAPIER_INVITE_LINK}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 bg-white text-orange-600 px-6 py-3 rounded-lg font-semibold hover:bg-orange-50 transition-colors"
                >
                    <ZapierIcon className="h-5 w-5" />
                    Connect CodeTether to Zapier
                    <ArrowRightIcon className="h-4 w-4" />
                </a>
            </div>

            {/* Quick Start Steps */}
            <div className="rounded-xl bg-white dark:bg-gray-800 shadow-sm ring-1 ring-gray-200 dark:ring-gray-700 p-6">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">Quick Start (3 minutes)</h2>
                <div className="grid gap-6 md:grid-cols-3">
                    {quickStartSteps.map((step) => (
                        <div key={step.step} className="relative">
                            <div className="flex items-start gap-4">
                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-orange-100 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400 font-bold">
                                    {step.step}
                                </div>
                                <div className="flex-1">
                                    <h3 className="font-semibold text-gray-900 dark:text-white">{step.title}</h3>
                                    <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{step.description}</p>
                                    {step.action.external ? (
                                        <a
                                            href={step.action.href}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-orange-600 dark:text-orange-400 hover:underline"
                                        >
                                            {step.action.label}
                                            <ArrowRightIcon className="h-3 w-3" />
                                        </a>
                                    ) : (
                                        <Link
                                            href={step.action.href}
                                            className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-orange-600 dark:text-orange-400 hover:underline"
                                        >
                                            {step.action.label}
                                            <ArrowRightIcon className="h-3 w-3" />
                                        </Link>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Zapier Use Cases */}
            <div className="rounded-xl bg-white dark:bg-gray-800 shadow-sm ring-1 ring-gray-200 dark:ring-gray-700 p-6">
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">Popular Zapier Automations</h2>
                <p className="text-gray-600 dark:text-gray-400 mb-6">Examples of what you can build with CodeTether + Zapier</p>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {zapierUseCases.map((useCase, idx) => (
                        <div key={idx} className="flex items-start gap-3 p-4 rounded-lg bg-gray-50 dark:bg-gray-700/50">
                            <span className="text-2xl">{useCase.icon}</span>
                            <div>
                                <p className="text-sm font-medium text-gray-900 dark:text-white">{useCase.trigger}</p>
                                <p className="text-sm text-gray-500 dark:text-gray-400">→ {useCase.action}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* All Integration Methods */}
            <div>
                <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6">All Integration Methods</h2>
                <div className="grid gap-6 lg:grid-cols-3">
                    {integrationMethods.map((method) => (
                        <div
                            key={method.name}
                            className={`rounded-xl bg-white dark:bg-gray-800 shadow-sm ring-1 p-6 ${
                                method.featured 
                                    ? 'ring-orange-500 ring-2' 
                                    : 'ring-gray-200 dark:ring-gray-700'
                            }`}
                        >
                            {method.featured && (
                                <span className="inline-block mb-3 text-xs font-semibold text-orange-600 dark:text-orange-400 bg-orange-100 dark:bg-orange-900/30 px-2 py-1 rounded-full">
                                    Recommended
                                </span>
                            )}
                            <div className="flex items-center gap-3 mb-3">
                                <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${method.color} text-white`}>
                                    <method.icon className="h-5 w-5" />
                                </div>
                                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{method.name}</h3>
                            </div>
                            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">{method.description}</p>
                            <ul className="space-y-2 mb-6">
                                {method.features.map((feature, idx) => (
                                    <li key={idx} className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-400">
                                        <CheckIcon className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                                        {feature}
                                    </li>
                                ))}
                            </ul>
                            {method.external ? (
                                <a
                                    href={method.href}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                                        method.featured
                                            ? 'bg-orange-500 text-white hover:bg-orange-600'
                                            : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-600'
                                    }`}
                                >
                                    {method.cta}
                                    <ArrowRightIcon className="h-4 w-4" />
                                </a>
                            ) : (
                                <Link
                                    href={method.href}
                                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg font-medium bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                                >
                                    {method.cta}
                                    <ArrowRightIcon className="h-4 w-4" />
                                </Link>
                            )}
                        </div>
                    ))}
                </div>
            </div>

            {/* Help Section */}
            <div className="rounded-xl bg-gray-50 dark:bg-gray-800/50 p-6 text-center">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">Need Help?</h3>
                <p className="text-gray-600 dark:text-gray-400 mb-4">
                    Our team is here to help you get set up.
                </p>
                <div className="flex flex-wrap justify-center gap-4">
                    <a
                        href="https://docs.codetether.run"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:underline"
                    >
                        Documentation
                    </a>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                    <a
                        href="mailto:support@codetether.io"
                        className="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:underline"
                    >
                        Email Support
                    </a>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                    <a
                        href="https://discord.gg/codetether"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:underline"
                    >
                        Discord Community
                    </a>
                </div>
            </div>
        </div>
    )
}
