import { Container } from '@/components/Container'

const maintenanceTimeline = [
    { day: 'Day 1', status: 'success', event: 'The demo works. Everyone ships it.' },
    { day: 'Day 30', status: 'warning', event: 'Load hits. The queue backs up. On-call begins.' },
    { day: 'Day 60', status: 'danger', event: 'Security review: missing encryption, auth, and an audit trail.' },
    { day: 'Day 90', status: 'critical', event: 'The original builder leaves. Now it\'s yours.' },
]

const runtimeConcerns = [
    {
        question: 'Retry & Recovery',
        diy: 'Worker dies mid-job. Do you resume, replay, or lose work?',
        codetether: 'Checkpointed recovery: resume safely after crashes.',
    },
    {
        question: 'Queue & Backpressure',
        diy: '500 jobs land at once. What slows down, drops, or deadlocks?',
        codetether: 'Queue + backpressure + worker autoscaling.',
    },
    {
        question: 'Identity & Permissions',
        diy: 'How does a worker prove it can touch prod data?',
        codetether: 'Keycloak auth with scoped service accounts.',
    },
    {
        question: 'Logs & Audit',
        diy: 'Where do logs go, and who can see them later?',
        codetether: 'Structured logs + streamed output + retention.',
    },
]

const controlMappings = [
    {
        area: 'Access Control',
        gap: 'Agents execute with shared credentials or over-broad service accounts.',
        control: 'Per-agent identity with scoped RBAC (Keycloak).',
    },
    {
        area: 'Change Management',
        gap: 'Autonomous changes ship with no approvals or policy gates.',
        control: 'Human-in-the-loop approvals for sensitive actions.',
    },
    {
        area: 'Audit Logging',
        gap: 'No reliable record of what ran, who approved it, or what changed.',
        control: 'Central audit trail for sessions, tools, and outputs.',
    },
    {
        area: 'Network Security',
        gap: 'Requires inbound access, VPNs, or new firewall exceptions.',
        control: 'Outbound-only workers (reverse polling).',
    },
    {
        area: 'Incident Response',
        gap: 'Runaway agents are hard to stop and even harder to explain.',
        control: 'Centralized oversight and intervention controls.',
    },
    {
        area: 'Vendor & Data Risk',
        gap: 'Prompts or source code get routed through third-party systems.',
        control: 'Payloads stay on the worker; CodeTether stays on orchestration metadata (you control retention).',
    },
]

export function WhyNotDIY() {
    return (
        <section
            id="why-not-diy"
            aria-label="Why not build it yourself"
            className="py-16 sm:py-24 bg-gray-50 dark:bg-gray-900"
        >
            <Container>
                {/* Header */}
                <div className="mx-auto max-w-3xl text-center">
                    <span className="inline-flex items-center rounded-full bg-orange-100 dark:bg-orange-900/30 px-4 py-1 text-sm font-medium text-orange-700 dark:text-orange-400 mb-4">
                        Reality Check
                    </span>
                    <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-4xl">
                        &quot;Can&apos;t Our Senior Engineer Just Build This?&quot;
                    </h2>
                    <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                        Yes. The demo is easy. Production is where you pay.
                    </p>
                </div>

                {/* The Weekend Project Timeline */}
                <div className="mt-12 rounded-2xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 p-6 sm:p-8">
                    <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                        The &quot;Weekend Project&quot; → On-Call Trap
                    </h3>
                    <p className="mb-6 text-sm text-gray-600 dark:text-gray-400">
                        A predictable timeline when a demo becomes &quot;production.&quot;
                    </p>
                    <div className="space-y-4">
                        {maintenanceTimeline.map((item) => (
                            <div
                                key={item.day}
                                className={`flex flex-col sm:flex-row items-start gap-4 p-4 rounded-lg ${item.status === 'success'
                                    ? 'bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800'
                                    : item.status === 'warning'
                                        ? 'bg-yellow-50 dark:bg-yellow-950/30 border border-yellow-200 dark:border-yellow-800'
                                        : item.status === 'danger'
                                            ? 'bg-orange-50 dark:bg-orange-950/30 border border-orange-200 dark:border-orange-800'
                                            : 'bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800'
                                    }`}
                            >
                                <div className={`text-sm font-bold w-20 sm:w-20 ${item.status === 'success'
                                    ? 'text-green-700 dark:text-green-400'
                                    : item.status === 'warning'
                                        ? 'text-yellow-700 dark:text-yellow-400'
                                        : item.status === 'danger'
                                            ? 'text-orange-700 dark:text-orange-400'
                                            : 'text-red-700 dark:text-red-400'
                                    }`}>
                                    {item.day}
                                </div>
                                <div className="flex-1 min-w-0 text-sm break-words">
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
                                <div className={`text-2xl flex-shrink-0 ${item.status === 'success' ? '' : 'opacity-70'
                                    }`}>
                                    {item.status === 'success' ? '✅' : item.status === 'warning' ? '⚠️' : item.status === 'danger' ? '🚨' : '💀'}
                                </div>
                            </div>
                        ))}
                    </div>
                    <p className="mt-6 text-gray-600 dark:text-gray-400 text-sm">
                        Platforms get bought to avoid <span className="font-semibold text-gray-900 dark:text-white">&quot;maintenance debt.&quot;</span> You don&apos;t want to own the plumbing—you want uptime, security, and sleep.
                    </p>
                </div>

                {/* Runtime vs Script */}
                <div className="mt-12 grid lg:grid-cols-2 gap-8">
                    <div className="rounded-2xl bg-gradient-to-br from-gray-800 to-gray-900 p-8">
                        <div className="flex items-center gap-3 mb-4">
                            <span className="text-3xl">🤖</span>
                            <h3 className="text-xl font-bold text-white">LLMs Write the Demo</h3>
                        </div>
                        <p className="text-gray-300 mb-4">
                            An LLM can generate the polling script in seconds.
                        </p>
                        <p className="text-gray-400 text-sm">
                            That&apos;s the <span className="text-white font-semibold">demo</span>. Not the runtime.
                        </p>
                    </div>
                    <div className="rounded-2xl bg-gradient-to-br from-cyan-600 to-cyan-700 p-8">
                        <div className="flex items-center gap-3 mb-4">
                            <span className="text-3xl">🏗️</span>
                            <h3 className="text-xl font-bold text-white">CodeTether Runs the Runtime</h3>
                        </div>
                        <ul className="text-gray-100 mb-4 space-y-1 text-sm">
                            <li>Queue + worker orchestration</li>
                            <li>Retries + recovery + checkpoints</li>
                            <li>Scoped identities + auth</li>
                            <li>Logs + streaming + auditability</li>
                        </ul>
                        <p className="text-cyan-200 text-sm">
                            That&apos;s the <span className="text-white font-semibold">runtime</span>. That&apos;s what keeps agent work reliable.
                        </p>
                    </div>
                </div>

                {/* The Questions They'll Ask */}
                <div className="mt-12">
                    <h3 className="text-center text-xl font-semibold text-gray-900 dark:text-white mb-8">
                        Questions a DIY Runtime Must Answer
                    </h3>
                    <div className="overflow-hidden rounded-2xl border border-gray-200 dark:border-gray-800">
                        {/* Mobile: stacked cards */}
                        <div className="md:hidden divide-y divide-gray-200 dark:divide-gray-800 bg-white dark:bg-gray-950">
                            {runtimeConcerns.map((row) => (
                                <div key={row.question} className="p-4">
                                    <div className="text-sm font-semibold text-gray-900 dark:text-white">
                                        {row.question}
                                    </div>
                                    <dl className="mt-3 space-y-3">
                                        <div>
                                            <dt className="text-xs font-semibold uppercase tracking-wide text-red-600 dark:text-red-400">Your DIY System</dt>
                                            <dd className="mt-1 text-sm text-gray-700 dark:text-gray-300 italic break-words">{row.diy}</dd>
                                        </div>
                                        <div>
                                            <dt className="text-xs font-semibold uppercase tracking-wide text-cyan-700 dark:text-cyan-400">CodeTether</dt>
                                            <dd className="mt-1 text-sm font-medium text-gray-900 dark:text-gray-200 break-words">{row.codetether}</dd>
                                        </div>
                                    </dl>
                                </div>
                            ))}
                        </div>

                        {/* Desktop/tablet: table */}
                        <div className="hidden md:block overflow-x-auto">
                            <table className="w-full min-w-[600px]">
                                <thead>
                                    <tr className="bg-gray-50 dark:bg-gray-900">
                                        <th className="px-4 sm:px-6 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">The Runtime Problem</th>
                                        <th className="px-4 sm:px-6 py-4 text-left text-sm font-semibold text-red-500 dark:text-red-400">Your DIY System</th>
                                        <th className="px-4 sm:px-6 py-4 text-left text-sm font-semibold text-cyan-600 dark:text-cyan-400">CodeTether</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200 dark:divide-gray-800 bg-white dark:bg-gray-950">
                                    {runtimeConcerns.map((row) => (
                                        <tr key={row.question}>
                                            <td className="px-4 sm:px-6 py-4 text-sm font-medium text-gray-900 dark:text-white break-words">{row.question}</td>
                                            <td className="px-4 sm:px-6 py-4 text-sm text-gray-500 dark:text-gray-500 italic break-words">{row.diy}</td>
                                            <td className="px-4 sm:px-6 py-4 text-sm text-gray-900 dark:text-gray-200 break-words">{row.codetether}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                {/* Control Mapping */}
                <div className="mt-12 rounded-2xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 p-6 sm:p-8">
                    <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                        <div>
                            <h3 className="text-xl font-bold text-gray-900 dark:text-white">
                                Uncontrolled Autonomous Execution Risk
                            </h3>
                            <p className="mt-2 text-sm text-gray-600 dark:text-gray-400 max-w-2xl">
                                Agents aren&apos;t human users and aren&apos;t CI/CD. If they can execute work, they need a governance layer.
                                Here&apos;s how CodeTether maps to controls CISOs already report on.
                            </p>
                        </div>
                        <span className="inline-flex items-center rounded-full bg-gray-100 dark:bg-gray-900 px-3 py-1 text-xs font-semibold text-gray-700 dark:text-gray-300">
                            SOC 2 / ISO 27001 / NIST CSF
                        </span>
                    </div>

                    <div className="mt-6 overflow-hidden rounded-2xl border border-gray-200 dark:border-gray-800">
                        {/* Mobile: stacked cards */}
                        <div className="md:hidden divide-y divide-gray-200 dark:divide-gray-800 bg-white dark:bg-gray-950">
                            {controlMappings.map((row) => (
                                <div key={row.area} className="p-4">
                                    <div className="text-sm font-semibold text-gray-900 dark:text-white">
                                        {row.area}
                                    </div>
                                    <dl className="mt-3 space-y-3">
                                        <div>
                                            <dt className="text-xs font-semibold uppercase tracking-wide text-red-600 dark:text-red-400">
                                                Gap without CodeTether
                                            </dt>
                                            <dd className="mt-1 text-sm text-gray-700 dark:text-gray-300 break-words">
                                                {row.gap}
                                            </dd>
                                        </div>
                                        <div>
                                            <dt className="text-xs font-semibold uppercase tracking-wide text-cyan-700 dark:text-cyan-400">
                                                CodeTether Control
                                            </dt>
                                            <dd className="mt-1 text-sm font-medium text-gray-900 dark:text-gray-200 break-words">
                                                {row.control}
                                            </dd>
                                        </div>
                                    </dl>
                                </div>
                            ))}
                        </div>

                        {/* Desktop/tablet: table */}
                        <div className="hidden md:block overflow-x-auto">
                            <table className="w-full min-w-[700px]">
                                <thead>
                                    <tr className="bg-gray-50 dark:bg-gray-900">
                                        <th className="px-4 sm:px-6 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">
                                            Control Area
                                        </th>
                                        <th className="px-4 sm:px-6 py-4 text-left text-sm font-semibold text-red-500 dark:text-red-400">
                                            Gap Without CodeTether
                                        </th>
                                        <th className="px-4 sm:px-6 py-4 text-left text-sm font-semibold text-cyan-600 dark:text-cyan-400">
                                            CodeTether Control
                                        </th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-200 dark:divide-gray-800 bg-white dark:bg-gray-950">
                                    {controlMappings.map((row) => (
                                        <tr key={row.area}>
                                            <td className="px-4 sm:px-6 py-4 text-sm font-medium text-gray-900 dark:text-white break-words">
                                                {row.area}
                                            </td>
                                            <td className="px-4 sm:px-6 py-4 text-sm text-gray-600 dark:text-gray-400 break-words">
                                                {row.gap}
                                            </td>
                                            <td className="px-4 sm:px-6 py-4 text-sm text-gray-900 dark:text-gray-200 font-medium break-words">
                                                {row.control}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                {/* The Gold Rush Analogy */}
                <div className="mt-16 rounded-2xl bg-gradient-to-r from-amber-500 to-yellow-500 p-6 sm:p-12">
                    <div className="max-w-3xl mx-auto text-center">
                        <h3 className="text-2xl font-bold text-gray-900 mb-6">⛏️ One Simple Analogy</h3>
                        <div className="grid sm:grid-cols-3 gap-4 sm:gap-6 mb-8">
                            <div className="bg-white/20 backdrop-blur rounded-xl p-4">
                                <div className="text-3xl mb-2">💎</div>
                                <div className="font-bold text-gray-900">The Gold Mine</div>
                                <div className="text-sm text-gray-800">Model providers</div>
                                <div className="text-xs text-gray-700 mt-1">Everyone wants the output</div>
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
                        <p className="text-gray-900 text-lg break-words">
                            The miner can be brilliant. Without ventilation, <span className="font-bold">the operation shuts down.</span>
                        </p>
                        <p className="mt-4 text-gray-800 font-semibold break-words">
                            CodeTether is that ventilation.
                        </p>
                    </div>
                </div>

                {/* CISO Quote */}
                <div className="mt-12 max-w-3xl mx-auto">
                    <div className="rounded-2xl bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 p-6 sm:p-8">
                        <div className="flex flex-col sm:flex-row items-start gap-4">
                            <span className="text-4xl">🛡️</span>
                            <div>
                                <h4 className="font-bold text-red-700 dark:text-red-400 mb-2">Your CISO Won&apos;t Approve DIY</h4>
                                <div className="space-y-4 text-gray-700 dark:text-gray-300 break-words">
                                    <p>
                                        <span className="text-red-600 dark:text-red-400">❌ What gets you blamed:</span><br />
                                        <span className="italic">&quot;We built a homegrown agent runner with prod credentials and no audit trail.&quot;</span>
                                    </p>
                                    <p>
                                        <span className="text-green-600 dark:text-green-400">✅ What gets you credit:</span><br />
                                        <span className="italic">&quot;We deployed a scoped, auditable orchestration runtime inside our VPC.&quot;</span>
                                    </p>
                                </div>
                                <p className="mt-4 text-sm text-gray-600 dark:text-gray-400">
                                    You&apos;re buying <span className="font-semibold text-gray-900 dark:text-white">standardization</span>, <span className="font-semibold text-gray-900 dark:text-white">auditability</span>, and <span className="font-semibold text-gray-900 dark:text-white">trust</span>.
                                </p>
                                <div className="mt-6 rounded-xl bg-white/60 dark:bg-gray-900/40 border border-red-200/60 dark:border-red-900/30 p-4">
                                    <p className="text-xs font-semibold uppercase tracking-wide text-red-700 dark:text-red-300">
                                        Board Sentence
                                    </p>
                                    <p className="mt-2 text-sm text-gray-900 dark:text-white break-words">
                                        &ldquo;We implemented a control plane for autonomous systems so no AI can execute work inside our environment without identity, authorization, audit logging, and human approval.&rdquo;
                                    </p>
                                </div>
                                <div className="mt-4 text-sm text-gray-700 dark:text-gray-300 break-words">
                                    In the next 12&ndash;24 months, an autonomous agent will run unattended and make a material change. The question won&apos;t be
                                    &ldquo;why did the agent do this?&rdquo; It will be &ldquo;why was there no control plane?&rdquo;
                                </div>
                                <ul className="mt-4 space-y-1 text-sm text-gray-700 dark:text-gray-300">
                                    <li className="break-words">
                                        <span className="font-semibold text-gray-900 dark:text-white">Deploy and nothing happens:</span> proactive risk management.
                                    </li>
                                    <li className="break-words">
                                        <span className="font-semibold text-gray-900 dark:text-white">Don&apos;t deploy and something happens:</span> it looks like a documented omission.
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>

                {/* The Verdict */}
                <div className="mt-16 text-center max-w-2xl mx-auto">
                    <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                        Chatbots Need APIs. Agents Need a Runtime.
                    </h3>
                    <div className="grid sm:grid-cols-2 gap-6 text-left">
                        <div className="bg-gray-100 dark:bg-gray-800 rounded-xl p-6">
                            <div className="text-sm text-gray-500 dark:text-gray-400 mb-2">Chatbots</div>
                            <div className="text-gray-900 dark:text-white">Prompt → response</div>
                        </div>
                        <div className="bg-cyan-100 dark:bg-cyan-900/30 rounded-xl p-6 border-2 border-cyan-500">
                            <div className="text-sm text-cyan-600 dark:text-cyan-400 mb-2">Agent teams</div>
                            <div className="text-gray-900 dark:text-white font-semibold">Tools, auth, memory, guardrails</div>
                        </div>
                    </div>
                    <p className="mt-8 text-xl font-semibold text-cyan-600 dark:text-cyan-400">
                        CodeTether is the production runtime for agent teams.
                    </p>
                </div>
            </Container>
        </section>
    )
}
