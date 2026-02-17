'use client'

import { Container } from '@/components/Container'

function InfinityIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#06b6d4" fillOpacity={0.2} />
            <path
                d="M8 16c0-2.2 1.8-4 4-4s4 1.8 4 4-1.8 4-4 4-4-1.8-4-4zm8 0c0-2.2 1.8-4 4-4s4 1.8 4 4-1.8 4-4 4-4-1.8-4-4z"
                stroke="#06b6d4"
                strokeWidth={2}
                fill="none"
            />
        </svg>
    )
}

function RecursiveIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#06b6d4" fillOpacity={0.2} />
            <path
                d="M16 8v4m0 8v4M8 16h4m8 0h4"
                stroke="#06b6d4"
                strokeWidth={2}
                strokeLinecap="round"
            />
            <circle cx={16} cy={16} r={4} fill="#06b6d4" />
            <path
                d="M12 12l-2-2m10 0l2-2m-10 12l-2 2m10 0l2 2"
                stroke="#06b6d4"
                strokeWidth={1.5}
                strokeLinecap="round"
            />
        </svg>
    )
}

function WebhookIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#06b6d4" fillOpacity={0.2} />
            <path
                d="M10 12l6 4-6 4V12zM16 12l6 4-6 4V12z"
                fill="#06b6d4"
            />
        </svg>
    )
}

const features = [
    {
        name: 'No More Token Limits',
        description:
            'ChatGPT maxes out at 128K tokens. RLM processes your full workspace context, all your content, and every spreadsheet row with no hard limit.',
        icon: InfinityIcon,
    },
    {
        name: 'AI Calls AI (Recursively)',
        description:
            'The agent writes Python that calls sub-LLMs. It chunks, analyzes, and synthesizes—like having a team of AI assistants.',
        icon: RecursiveIcon,
    },
    {
        name: 'Trigger from Anywhere',
        description:
            'Webhook in from Zapier, n8n, Make, or direct API. Results stream back in real-time or callback to your workflow.',
        icon: WebhookIcon,
    },
]

export function RLMFeature() {
    return (
        <section
            id="rlm"
            aria-label="RLM - Recursive Language Models"
            className="relative overflow-hidden bg-white dark:bg-gray-950 py-20 sm:py-32"
        >
            <Container className="relative">
                {/* Header */}
                <div className="mx-auto max-w-2xl lg:mx-0 lg:max-w-3xl">
                    <p className="text-base font-semibold text-cyan-600 dark:text-cyan-400">
                        The breakthrough you&apos;ve been waiting for
                    </p>
                    <h2 className="mt-2 text-3xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-4xl">
                        RLM: Finally, AI that reads <span className="text-cyan-600 dark:text-cyan-400">everything</span>
                    </h2>
                    <p className="mt-6 text-lg text-gray-600 dark:text-gray-300">
                        Based on <a href="https://arxiv.org/html/2512.24601v1" target="_blank" rel="noopener noreferrer" className="text-cyan-600 dark:text-cyan-400 underline hover:no-underline">MIT/Harvard research</a>, 
                        Recursive Language Models treat your content as an external variable. The AI writes code to analyze it 
                        piece by piece, calling sub-LLMs recursively until it has the full picture.
                    </p>
                </div>

                {/* Comparison */}
                <div className="mt-16 grid gap-8 lg:grid-cols-2">
                    {/* Before */}
                    <div className="rounded-2xl bg-gray-100 dark:bg-gray-900 p-8">
                        <h3 className="text-lg font-semibold text-gray-500 dark:text-gray-400 mb-4">
                            ❌ Before RLM (Regular ChatGPT)
                        </h3>
                        <div className="space-y-3 font-mono text-sm">
                            <p className="text-gray-500">You: Analyze my workspace for security issues</p>
                            <p className="text-red-500">ChatGPT: Please paste the code you&apos;d like me to review.</p>
                            <p className="text-gray-500">You: *pastes 3 files*</p>
                            <p className="text-red-500">ChatGPT: I can only see these 3 files. Do you have more?</p>
                            <p className="text-gray-500">You: I have 847 files...</p>
                            <p className="text-red-500">ChatGPT: That exceeds my context window. 😔</p>
                        </div>
                    </div>

                    {/* After */}
                    <div className="rounded-2xl bg-cyan-50 dark:bg-cyan-900/20 p-8 ring-2 ring-cyan-500">
                        <h3 className="text-lg font-semibold text-cyan-700 dark:text-cyan-300 mb-4">
                            ✅ With RLM (CodeTether)
                        </h3>
                        <div className="space-y-3 font-mono text-sm">
                            <p className="text-gray-600 dark:text-gray-300">You: Analyze my workspace for security issues</p>
                            <p className="text-cyan-600 dark:text-cyan-400">RLM: Loading 847 files into context...</p>
                            <p className="text-cyan-600 dark:text-cyan-400">RLM: Analyzing in batches of 50...</p>
                            <p className="text-cyan-600 dark:text-cyan-400">RLM: Running 17 sub-LLM security checks...</p>
                            <p className="text-green-600 dark:text-green-400">RLM: Found 12 critical issues. Here&apos;s the report:</p>
                            <p className="text-green-600 dark:text-green-400">[Detailed security audit with file references]</p>
                        </div>
                    </div>
                </div>

                {/* Feature Grid */}
                <ul
                    role="list"
                    className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-8 sm:grid-cols-3 lg:max-w-none"
                >
                    {features.map((feature) => (
                        <li
                            key={feature.name}
                            className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-8 transition-all hover:border-cyan-500 dark:hover:border-cyan-500 hover:shadow-lg hover:shadow-cyan-500/10"
                        >
                            <feature.icon className="h-10 w-10" />
                            <h3 className="mt-6 text-lg font-semibold text-gray-900 dark:text-white">
                                {feature.name}
                            </h3>
                            <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">{feature.description}</p>
                        </li>
                    ))}
                </ul>

                {/* Workflow Example */}
                <div className="mt-16 rounded-2xl bg-gray-900 p-8">
                    <h3 className="text-lg font-semibold text-white mb-6">
                        Example: Zapier → RLM → Google Sheets
                    </h3>
                    <div className="grid gap-4 sm:grid-cols-4">
                        <div className="rounded-lg bg-orange-500/20 p-4 text-center">
                            <p className="text-2xl mb-2">⚡</p>
                            <p className="text-sm font-medium text-orange-300">Zapier Trigger</p>
                            <p className="text-xs text-gray-400 mt-1">New row in sheet</p>
                        </div>
                        <div className="rounded-lg bg-cyan-500/20 p-4 text-center">
                            <p className="text-2xl mb-2">🤖</p>
                            <p className="text-sm font-medium text-cyan-300">RLM Agent</p>
                            <p className="text-xs text-gray-400 mt-1">Analyzes full context</p>
                        </div>
                        <div className="rounded-lg bg-cyan-500/20 p-4 text-center">
                            <p className="text-2xl mb-2">📝</p>
                            <p className="text-sm font-medium text-cyan-300">Generates Output</p>
                            <p className="text-xs text-gray-400 mt-1">Report, code, content</p>
                        </div>
                        <div className="rounded-lg bg-green-500/20 p-4 text-center">
                            <p className="text-2xl mb-2">📊</p>
                            <p className="text-sm font-medium text-green-300">Callback</p>
                            <p className="text-xs text-gray-400 mt-1">Results to your app</p>
                        </div>
                    </div>
                </div>
            </Container>
        </section>
    )
}
