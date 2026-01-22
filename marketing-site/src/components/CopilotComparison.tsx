'use client'

import { Container } from '@/components/Container'
import { Button } from '@/components/Button'

function CheckIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
    )
}

function XIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
    )
}

const comparisonData = [
    {
        feature: 'Task Duration',
        chatgpt: 'Seconds (single response)',
        codetether: 'Up to 60 min (background)',
    },
    {
        feature: 'Output Format',
        chatgpt: 'Text in chat window',
        codetether: 'Real files (CSV, PDF, code)',
    },
    {
        feature: 'Automation',
        chatgpt: 'Manual copy/paste',
        codetether: 'Webhook trigger + callback',
    },
    {
        feature: 'Batch Processing',
        chatgpt: 'One request at a time',
        codetether: '100+ concurrent tasks',
    },
    {
        feature: 'Context Handling',
        chatgpt: 'Degrades on long inputs',
        codetether: 'RLM - unlimited context',
    },
]

const painPoints = [
    {
        title: 'The Copy/Paste Problem',
        problem: 'ChatGPT gives you text. You copy it, paste it, format it… again and again.',
        solution: 'CodeTether delivers real files ready to use.',
    },
    {
        title: 'The Babysitting Problem',
        problem: 'Complex tasks take multiple prompts and constant steering.',
        solution: 'CodeTether runs in the background and finishes the job.',
    },
    {
        title: 'The Timeout Problem',
        problem: 'Zapier "AI steps" fail when tasks take longer than 30 seconds.',
        solution: 'CodeTether runs for up to 60 minutes with checkpointed progress.',
    },
    {
        title: 'The Context Limit Problem',
        problem: 'Normal LLMs break down on big datasets and long context.',
        solution: 'CodeTether uses RLM (MIT research) to process 10M+ tokens without degradation.',
    },
]

export function CopilotComparison() {
    return (
        <section
            id="chatgpt-comparison"
            aria-label="ChatGPT comparison"
            className="py-16 sm:py-24 bg-white dark:bg-gray-950"
        >
            <Container>
                {/* Header */}
                <div className="mx-auto max-w-2xl text-center">
                    <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-4xl">
                        ChatGPT is a Chat.<br />
                        <span className="text-cyan-600 dark:text-cyan-400">CodeTether is a Worker.</span>
                    </h2>
                    <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                        ChatGPT is great for quick answers. CodeTether is for tasks you'd normally spend <span className="font-semibold">30–60 minutes</span> doing yourself—or pay someone else to do.
                    </p>
                    <p className="mt-2 text-gray-600 dark:text-gray-300">
                        <span className="font-semibold">Trigger once → walk away → get deliverables.</span>
                    </p>
                </div>

                {/* Pain Points */}
                <div className="mt-16 grid md:grid-cols-2 lg:grid-cols-4 gap-6">
                    {painPoints.map((point) => (
                        <div
                            key={point.title}
                            className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-6"
                        >
                            <h4 className="font-semibold text-gray-900 dark:text-white">{point.title}</h4>
                            <div className="mt-4 space-y-3">
                                <div className="flex items-start gap-2">
                                    <XIcon className="h-5 w-5 text-gray-400 flex-shrink-0 mt-0.5" />
                                    <p className="text-sm text-gray-600 dark:text-gray-400">{point.problem}</p>
                                </div>
                                <div className="flex items-start gap-2">
                                    <CheckIcon className="h-5 w-5 text-cyan-500 flex-shrink-0 mt-0.5" />
                                    <p className="text-sm text-gray-700 dark:text-gray-300">{point.solution}</p>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>

                {/* Comparison Table */}
                <div className="mt-16 overflow-hidden rounded-2xl border border-gray-200 dark:border-gray-800">
                    <table className="w-full">
                        <thead>
                            <tr className="bg-gray-50 dark:bg-gray-900">
                                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">Capability</th>
                                <th className="px-6 py-4 text-left text-sm font-semibold text-gray-500 dark:text-gray-400">ChatGPT</th>
                                <th className="px-6 py-4 text-left text-sm font-semibold text-cyan-600 dark:text-cyan-400">CodeTether</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200 dark:divide-gray-800 bg-white dark:bg-gray-950">
                            {comparisonData.map((row) => (
                                <tr key={row.feature}>
                                    <td className="px-6 py-4 text-sm font-medium text-gray-900 dark:text-white">{row.feature}</td>
                                    <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">{row.chatgpt}</td>
                                    <td className="px-6 py-4 text-sm text-gray-900 dark:text-gray-200 font-medium">{row.codetether}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* CTA */}
                <div className="mt-12 text-center">
                    <Button href="/register" color="cyan">
                        Try CodeTether Free
                    </Button>
                </div>
            </Container>
        </section>
    )
}
