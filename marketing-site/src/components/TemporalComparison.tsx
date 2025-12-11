'use client'

import { Container } from '@/components/Container'
import { Button } from '@/components/Button'

function TemporalIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" fill="currentColor" {...props}>
            <circle cx="16" cy="16" r="14" fill="none" stroke="currentColor" strokeWidth="2" />
            <path d="M16 8v8l6 4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
    )
}

const temporalGaps = [
    {
        problem: '"How do I stream LLM token output back to the user through a Temporal activity?"',
        temporal: 'Really hard. No native support.',
        codetether: 'Built-in SSE streaming from workers to clients.',
    },
    {
        problem: '"How do I manage chat history state inside a Temporal workflow?"',
        temporal: 'Complex state management. Build from scratch.',
        codetether: 'Persistent session history with context preservation.',
    },
    {
        problem: '"How do I connect this to VS Code / Copilot?"',
        temporal: 'No integration exists. Build the plumbing.',
        codetether: 'Native MCP server—Copilot calls your agents as tools.',
    },
    {
        problem: '"How do I handle the agent loop (think → plan → act → retry)?"',
        temporal: 'Implement activities yourself. Months of work.',
        codetether: 'A2A protocol handles agent orchestration natively.',
    },
    {
        problem: '"How do I integrate with our VDI without crashing sessions?"',
        temporal: 'Architecture redesign required.',
        codetether: 'Lightweight client streams from robust backend workers.',
    },
]

export function TemporalComparison() {
    return (
        <section
            id="temporal-comparison"
            aria-label="Temporal comparison"
            className="py-20 sm:py-32 bg-white dark:bg-gray-950"
        >
            <Container>
                {/* Header */}
                <div className="mx-auto max-w-3xl text-center">
                    <div className="flex items-center justify-center gap-2 mb-4">
                        <TemporalIcon className="h-8 w-8 text-cyan-600 dark:text-cyan-400" />
                        <span className="inline-flex items-center rounded-full bg-purple-100 dark:bg-purple-900/30 px-4 py-1 text-sm font-medium text-purple-700 dark:text-purple-400">
                            For Platform Architects
                        </span>
                    </div>
                    <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-4xl">
                        Temporal for AI Agents
                    </h2>
                    <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                        You know how Temporal solved reliable workflows for your transaction systems?
                        <span className="font-semibold text-gray-900 dark:text-white"> CodeTether is Temporal for your AI Agents.</span>
                    </p>
                </div>

                {/* The Problem Statement */}
                <div className="mt-12 rounded-2xl bg-gradient-to-r from-purple-900 to-indigo-900 p-8 sm:p-12">
                    <div className="max-w-3xl">
                        <h3 className="text-xl font-bold text-white">The &quot;Temporal Gap&quot;</h3>
                        <p className="mt-4 text-purple-100">
                            Temporal is a brilliant general-purpose workflow engine. But it knows nothing about
                            LLMs, tokens, MCP, or chat context. To build an AI Agent on Temporal, you have to
                            write <span className="font-semibold text-white">everything</span> from scratch:
                        </p>
                        <ul className="mt-4 grid sm:grid-cols-2 gap-3">
                            {['The agent loop', 'The memory system', 'The tool calling', 'The streaming response', 'The VDI integration', 'The session management'].map((item) => (
                                <li key={item} className="flex items-center gap-2 text-purple-200">
                                    <span className="text-purple-400">→</span>
                                    {item}
                                </li>
                            ))}
                        </ul>
                        <p className="mt-6 text-purple-100">
                            We spent <span className="font-semibold text-white">thousands of hours</span> building the
                            Agent Protocol so you don&apos;t have to. You get the security of Temporal&apos;s polling architecture,
                            but designed specifically for long-running AI tasks.
                        </p>
                    </div>
                </div>

                {/* Comparison Table */}
                <div className="mt-16">
                    <h3 className="text-center text-xl font-semibold text-gray-900 dark:text-white mb-8">
                        Questions Your Engineers Are Stuck On Right Now
                    </h3>
                    <div className="overflow-hidden rounded-2xl border border-gray-200 dark:border-gray-800">
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead>
                                    <tr className="bg-gray-50 dark:bg-gray-900">
                                        <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">The Question</th>
                                        <th className="px-6 py-4 text-left text-sm font-semibold text-red-500 dark:text-red-400">With Raw Temporal</th>
                                        <th className="px-6 py-4 text-left text-sm font-semibold text-cyan-600 dark:text-cyan-400">With CodeTether</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200 dark:divide-gray-800 bg-white dark:bg-gray-950">
                                    {temporalGaps.map((row) => (
                                        <tr key={row.problem}>
                                            <td className="px-6 py-4 text-sm text-gray-700 dark:text-gray-300 italic">{row.problem}</td>
                                            <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-500">{row.temporal}</td>
                                            <td className="px-6 py-4 text-sm text-gray-900 dark:text-gray-200 font-medium">{row.codetether}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                    <p className="mt-4 text-center text-lg font-semibold text-cyan-600 dark:text-cyan-400">
                        CodeTether answers: &quot;It&apos;s already done. Just deploy the worker.&quot;
                    </p>
                </div>

                {/* Architecture Similarity */}
                <div className="mt-16 grid lg:grid-cols-2 gap-8">
                    <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 p-8">
                        <h4 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                            <span className="text-2xl">⚡</span>
                            Same Security Model as Temporal
                        </h4>
                        <ul className="mt-4 space-y-3">
                            <li className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300">
                                <span className="text-cyan-500 mt-1">✓</span>
                                <span><strong>Workers PULL tasks</strong> from inside your network—no inbound ports</span>
                            </li>
                            <li className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300">
                                <span className="text-cyan-500 mt-1">✓</span>
                                <span><strong>Data stays in your VPC</strong>—only task metadata flows through the server</span>
                            </li>
                            <li className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300">
                                <span className="text-cyan-500 mt-1">✓</span>
                                <span><strong>Durable execution</strong>—if a worker dies, another picks up the task</span>
                            </li>
                            <li className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300">
                                <span className="text-cyan-500 mt-1">✓</span>
                                <span><strong>Audit trail built-in</strong>—every task, every result, logged for compliance</span>
                            </li>
                        </ul>
                    </div>
                    <div className="rounded-2xl border border-cyan-500 bg-cyan-50 dark:bg-cyan-950/30 p-8">
                        <h4 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                            <span className="text-2xl">🧠</span>
                            Plus Everything AI Agents Need
                        </h4>
                        <ul className="mt-4 space-y-3">
                            <li className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300">
                                <span className="text-cyan-500 mt-1">✓</span>
                                <span><strong>Native MCP support</strong>—Copilot can dispatch work via standard protocol</span>
                            </li>
                            <li className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300">
                                <span className="text-cyan-500 mt-1">✓</span>
                                <span><strong>Real-time token streaming</strong>—see agent output as it generates</span>
                            </li>
                            <li className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300">
                                <span className="text-cyan-500 mt-1">✓</span>
                                <span><strong>Session persistence</strong>—resume any conversation with full context</span>
                            </li>
                            <li className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-300">
                                <span className="text-cyan-500 mt-1">✓</span>
                                <span><strong>VDI-optimized</strong>—heavy compute on backend, lightweight output to desktop</span>
                            </li>
                        </ul>
                    </div>
                </div>

                {/* The Moat */}
                <div className="mt-16 text-center max-w-2xl mx-auto">
                    <p className="text-gray-600 dark:text-gray-400 italic">
                        &quot;If building AI agents on Temporal was easy, a junior dev would have done it in a weekend.
                        The thousands of hours we spent solving token streaming, context management, and VDI integration
                        is the product. We&apos;re selling you the time you won&apos;t have to spend.&quot;
                    </p>
                </div>

                {/* CTA */}
                <div className="mt-12 text-center">
                    <div className="flex flex-wrap justify-center gap-4">
                        <Button href="#features" color="cyan">
                            See the Architecture
                        </Button>
                        <Button href="#contact" variant="outline">
                            Talk to an Architect
                        </Button>
                    </div>
                </div>
            </Container>
        </section>
    )
}
