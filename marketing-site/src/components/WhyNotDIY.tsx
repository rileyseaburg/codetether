'use client'

import { Container } from '@/components/Container'

const maintenanceTimeline = [
    { day: 'Day 1', status: 'success', event: 'It works! The agent polls and runs.' },
    { day: 'Day 30', status: 'warning', event: 'The Redis queue fills up and crashes production.' },
    { day: 'Day 60', status: 'danger', event: 'Security audit finds no encryption on the wire.' },
    { day: 'Day 90', status: 'critical', event: 'The engineer who built it quits. Now nobody knows how it works.' },
]

const runtimeConcerns = [
    {
        question: 'Retry Logic',
        diy: 'What happens when the worker crashes halfway through a 20-minute job?',
        codetether: 'Automatic task recovery with checkpoint state preservation.',
    },
    {
        question: 'Queueing',
        diy: 'What happens when 50 developers submit 500 jobs at once?',
        codetether: 'Redis-backed queue with worker pool scaling and backpressure.',
    },
    {
        question: 'Security Handshake',
        diy: 'How do you prove the worker is allowed to touch the database?',
        codetether: 'Keycloak-integrated auth with service accounts and scopes.',
    },
    {
        question: 'Logging',
        diy: 'Where does stdout go when the worker is ephemeral?',
        codetether: 'Structured logs and SSE streaming to persistent storage.',
    },
]

export function WhyNotDIY() {
    return (
        <section
            id="why-not-diy"
            aria-label="Why not build it yourself"
            className="py-20 sm:py-32 bg-gray-50 dark:bg-gray-900"
        >
            <Container>
                {/* Header */}
                <div className="mx-auto max-w-3xl text-center">
                    <span className="inline-flex items-center rounded-full bg-orange-100 dark:bg-orange-900/30 px-4 py-1 text-sm font-medium text-orange-700 dark:text-orange-400 mb-4">
                        The Hard Truth
                    </span>
                    <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-4xl">
                        &quot;Can&apos;t Our Senior Engineer Just Build This?&quot;
                    </h2>
                    <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                        Yes. And here&apos;s exactly what will happen.
                    </p>
                </div>

                {/* The Weekend Project Timeline */}
                <div className="mt-12 rounded-2xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 p-8">
                    <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-6">
                        The &quot;Weekend Project&quot; → Production Trap
                    </h3>
                    <div className="space-y-4">
                        {maintenanceTimeline.map((item, index) => (
                            <div
                                key={item.day}
                                className={`flex items-start gap-4 p-4 rounded-lg ${item.status === 'success'
                                        ? 'bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800'
                                        : item.status === 'warning'
                                            ? 'bg-yellow-50 dark:bg-yellow-950/30 border border-yellow-200 dark:border-yellow-800'
                                            : item.status === 'danger'
                                                ? 'bg-orange-50 dark:bg-orange-950/30 border border-orange-200 dark:border-orange-800'
                                                : 'bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800'
                                    }`}
                            >
                                <div className={`flex-shrink-0 w-20 font-bold ${item.status === 'success'
                                        ? 'text-green-700 dark:text-green-400'
                                        : item.status === 'warning'
                                            ? 'text-yellow-700 dark:text-yellow-400'
                                            : item.status === 'danger'
                                                ? 'text-orange-700 dark:text-orange-400'
                                                : 'text-red-700 dark:text-red-400'
                                    }`}>
                                    {item.day}
                                </div>
                                <div className="flex-1">
                                    <span className={`${item.status === 'success'
                                            ? 'text-green-800 dark:text-green-300'
                                            : item.status === 'warning'
                                                ? 'text-yellow-800 dark:text-yellow-300'
                                                : item.status === 'danger'
                                                    ? 'text-orange-800 dark:text-orange-300'
                                                    : 'text-red-800 dark:text-red-300'
                                        }`}>
                                        {item.event}
                                    </span>
                                </div>
                                <div className={`flex-shrink-0 text-2xl ${item.status === 'success' ? '' : 'opacity-70'
                                    }`}>
                                    {item.status === 'success' ? '✅' : item.status === 'warning' ? '⚠️' : item.status === 'danger' ? '🚨' : '💀'}
                                </div>
                            </div>
                        ))}
                    </div>
                    <p className="mt-6 text-gray-600 dark:text-gray-400 text-sm">
                        Companies buy platforms to avoid <span className="font-semibold text-gray-900 dark:text-white">&quot;Maintenance Debt.&quot;</span> They don&apos;t want to own the plumbing—they want to own the business logic.
                    </p>
                </div>

                {/* Runtime vs Script */}
                <div className="mt-12 grid lg:grid-cols-2 gap-8">
                    <div className="rounded-2xl bg-gradient-to-br from-gray-800 to-gray-900 p-8">
                        <div className="flex items-center gap-3 mb-4">
                            <span className="text-3xl">🤖</span>
                            <h3 className="text-xl font-bold text-white">LLMs Write Code</h3>
                        </div>
                        <p className="text-gray-300 mb-4">
                            An LLM can generate a Python script to &quot;poll a server&quot; in 10 seconds.
                        </p>
                        <p className="text-gray-400 text-sm">
                            That&apos;s the <span className="text-white font-semibold">logic</span>. A script. The easy part.
                        </p>
                    </div>
                    <div className="rounded-2xl bg-gradient-to-br from-cyan-600 to-cyan-700 p-8">
                        <div className="flex items-center gap-3 mb-4">
                            <span className="text-3xl">🏗️</span>
                            <h3 className="text-xl font-bold text-white">CodeTether Runs Systems</h3>
                        </div>
                        <p className="text-gray-100 mb-4">
                            The server, the queue, the state machine, the retry logic, the security handshake.
                        </p>
                        <p className="text-cyan-200 text-sm">
                            That&apos;s the <span className="text-white font-semibold">runtime</span>. The infrastructure. The hard part.
                        </p>
                    </div>
                </div>

                {/* The Questions They'll Ask */}
                <div className="mt-12">
                    <h3 className="text-center text-xl font-semibold text-gray-900 dark:text-white mb-8">
                        Questions Your DIY System Won&apos;t Answer
                    </h3>
                    <div className="overflow-hidden rounded-2xl border border-gray-200 dark:border-gray-800">
                        <table className="w-full">
                            <thead>
                                <tr className="bg-gray-50 dark:bg-gray-900">
                                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">The Runtime Problem</th>
                                    <th className="px-6 py-4 text-left text-sm font-semibold text-red-500 dark:text-red-400">Your DIY System</th>
                                    <th className="px-6 py-4 text-left text-sm font-semibold text-cyan-600 dark:text-cyan-400">CodeTether</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200 dark:divide-gray-800 bg-white dark:bg-gray-950">
                                {runtimeConcerns.map((row) => (
                                    <tr key={row.question}>
                                        <td className="px-6 py-4 text-sm font-medium text-gray-900 dark:text-white">{row.question}</td>
                                        <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-500 italic">{row.diy}</td>
                                        <td className="px-6 py-4 text-sm text-gray-900 dark:text-gray-200">{row.codetether}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* The Gold Rush Analogy */}
                <div className="mt-16 rounded-2xl bg-gradient-to-r from-amber-500 to-yellow-500 p-8 sm:p-12">
                    <div className="max-w-3xl mx-auto text-center">
                        <h3 className="text-2xl font-bold text-gray-900 mb-6">⛏️ The Gold Rush Analogy</h3>
                        <div className="grid sm:grid-cols-3 gap-6 mb-8">
                            <div className="bg-white/20 backdrop-blur rounded-xl p-4">
                                <div className="text-3xl mb-2">💎</div>
                                <div className="font-bold text-gray-900">The Gold Mine</div>
                                <div className="text-sm text-gray-800">OpenAI / Anthropic</div>
                                <div className="text-xs text-gray-700 mt-1">Everyone wants the gold</div>
                            </div>
                            <div className="bg-white/20 backdrop-blur rounded-xl p-4">
                                <div className="text-3xl mb-2">⛏️</div>
                                <div className="font-bold text-gray-900">The Miner</div>
                                <div className="text-sm text-gray-800">The AI Agent</div>
                                <div className="text-xs text-gray-700 mt-1">Smart and capable</div>
                            </div>
                            <div className="bg-white/20 backdrop-blur rounded-xl p-4">
                                <div className="text-3xl mb-2">🌬️</div>
                                <div className="font-bold text-gray-900">The Ventilation</div>
                                <div className="text-sm text-gray-800">CodeTether</div>
                                <div className="text-xs text-gray-700 mt-1">Keeps the operation safe</div>
                            </div>
                        </div>
                        <p className="text-gray-900 text-lg">
                            Sure, the miner is smart. But without the ventilation system,
                            <span className="font-bold"> the miner dies, the tunnel collapses, and the operation shuts down.</span>
                        </p>
                        <p className="mt-4 text-gray-800 font-semibold">
                            The smarter miners get, the better your ventilation needs to be.
                        </p>
                    </div>
                </div>

                {/* CISO Quote */}
                <div className="mt-12 max-w-3xl mx-auto">
                    <div className="rounded-2xl bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 p-8">
                        <div className="flex items-start gap-4">
                            <span className="text-4xl">🛡️</span>
                            <div>
                                <h4 className="font-bold text-red-700 dark:text-red-400 mb-2">The CISO Doesn&apos;t Trust DIY</h4>
                                <div className="space-y-4 text-gray-700 dark:text-gray-300">
                                    <p>
                                        <span className="text-red-600 dark:text-red-400">❌ What gets you fired:</span><br />
                                        <span className="italic">&quot;I asked ChatGPT to write a custom reverse-shell script to run agents inside our payment network.&quot;</span>
                                    </p>
                                    <p>
                                        <span className="text-green-600 dark:text-green-400">✅ What gets the check signed:</span><br />
                                        <span className="italic">&quot;We&apos;re deploying CodeTether—an industry-standard, SOC2-compliant orchestration platform that runs in our VPC.&quot;</span>
                                    </p>
                                </div>
                                <p className="mt-4 text-sm text-gray-600 dark:text-gray-400">
                                    You&apos;re not just buying code. You&apos;re buying <span className="font-semibold text-gray-900 dark:text-white">standardization</span> and <span className="font-semibold text-gray-900 dark:text-white">trust</span>.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* The Verdict */}
                <div className="mt-16 text-center max-w-2xl mx-auto">
                    <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                        The Smarter LLMs Get, The More They Need Us
                    </h3>
                    <div className="grid sm:grid-cols-2 gap-6 text-left">
                        <div className="bg-gray-100 dark:bg-gray-800 rounded-xl p-6">
                            <div className="text-sm text-gray-500 dark:text-gray-400 mb-2">Dumb Bots (Chatbots)</div>
                            <div className="text-gray-900 dark:text-white">Just need an API call</div>
                        </div>
                        <div className="bg-cyan-100 dark:bg-cyan-900/30 rounded-xl p-6 border-2 border-cyan-500">
                            <div className="text-sm text-cyan-600 dark:text-cyan-400 mb-2">Genius Agents (Coding/Infra Bots)</div>
                            <div className="text-gray-900 dark:text-white font-semibold">Need access, long-term memory, and safety rails</div>
                        </div>
                    </div>
                    <p className="mt-8 text-xl font-semibold text-cyan-600 dark:text-cyan-400">
                        CodeTether is the safety rail for genius AI.
                    </p>
                </div>
            </Container>
        </section>
    )
}
