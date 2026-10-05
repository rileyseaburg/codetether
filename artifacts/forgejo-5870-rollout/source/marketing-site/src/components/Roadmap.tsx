'use client'

import { Container } from '@/components/Container'

const phases = [
    {
        phase: 'Shipped',
        title: 'Core Platform',
        status: 'current',
        goal: '60+ registered tools, autonomous coding loops, multi-agent orchestration, and multi-modal output — live in the agent runtime.',
        items: [
            { name: 'OKR tracking and execution runs', done: true },
            { name: 'OKR → PRD → Ralph autonomous pipeline', done: true },
            { name: 'Structured PRD generation and validation', done: true },
            { name: 'Ralph iterative implementation loop', done: true },
            { name: 'RLM infinite context processing', done: true },
            { name: 'RLM answer verification', done: true },
            { name: 'Session recall and context browsing', done: true },
            { name: 'Persistent memory across sessions', done: true },
            { name: 'Real file output (CSV, PDF, code)', done: true },
            { name: 'Plan mode, safe edit previews, and undo', done: true },
            { name: 'Browser control with network replay', done: true },
            { name: 'Web search, web fetch, and code search', done: true },
            { name: 'Voice TTS and transcription', done: true },
            { name: 'Podcast generation & RSS', done: true },
            { name: 'YouTube upload', done: true },
            { name: 'AI avatar video generation', done: true },
            { name: 'Image input for vision-capable models', done: true },
            { name: 'MCP bridge (Model Context Protocol)', done: true },
            { name: 'Kubernetes pod management', done: true },
            { name: 'Sub-agent relay autochat', done: true },
            { name: 'Swarm parallel execution', done: true },
            { name: 'Multi-model orchestration', done: true },
            { name: 'OPA Rego RBAC and tenant isolation', done: true },
            { name: 'Self-hosted (Docker / K8s / bare metal)', done: true },
        ],
    },
    {
        phase: 'Next',
        title: 'Control Plane API',
        status: 'upcoming',
        goal: 'Expose the full agent runtime as a durable, observable, multi-tenant control plane.',
        items: [
            { name: 'Unified control plane API for OKRs, PRDs, runs, tools, and sessions', done: false },
            { name: 'Run lifecycle events and streaming progress', done: false },
            { name: 'Dashboard for OKR/run monitoring and replayable audit trails', done: false },
            { name: 'Team workspaces with role-scoped agent permissions', done: false },
            { name: 'Scheduled and webhook-triggered autonomous runs', done: false },
            { name: 'Worker pools for local, cloud, and Kubernetes executors', done: false },
            { name: 'Tool catalog, policy gates, and per-tenant capability controls', done: false },
            { name: 'Pre-built workflow templates for engineering, ops, and media', done: false },
            { name: 'Bulk task API and batched background execution', done: false },
            { name: 'Zapier, n8n, Make, and GitHub app integrations', done: false },
            { name: 'Usage metering, quotas, and cost controls', done: false },
        ],
    },
    {
        phase: 'Future',
        title: 'Autonomous Organization Layer',
        status: 'future',
        goal: 'Turn goals, policies, tools, and workers into a self-improving execution fabric.',
        items: [
            { name: 'Policy-aware autonomous delegation across teams and tenants', done: false },
            { name: 'Learning workflow library from successful runs', done: false },
            { name: 'Organization-level OKR decomposition into agent run plans', done: false },
            { name: 'Cross-repository dependency reasoning and migration planning', done: false },
            { name: 'RLM deeper recursion and domain-trained retrieval models', done: false },
            { name: 'Custom fine-tuned coding and operations models', done: false },
            { name: 'Real-time collaborative voice agent', done: false },
            { name: 'Video understanding, generation, and review loops', done: false },
            { name: 'Marketplace for signed agent skills and MCP tool packs', done: false },
            { name: 'White-label and private-cloud deployments for agencies and enterprises', done: false },
        ],
    },
]

function CheckIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 20 20" fill="currentColor" {...props}>
            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
        </svg>
    )
}

function CircleIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 20 20" fill="currentColor" {...props}>
            <circle cx="10" cy="10" r="4" />
        </svg>
    )
}

export function Roadmap() {
    return (
        <section
            id="roadmap"
            aria-label="Product roadmap"
            className="bg-gray-900 py-20 sm:py-32"
        >
            <Container>
                <div className="mx-auto max-w-2xl text-center">
                    <h2 className="text-3xl font-medium tracking-tight text-white">
                        The Road to the Agent Control Plane
                    </h2>
                    <p className="mt-4 text-lg text-gray-400">
                        The agent runtime is already deep. Next is making it governable, observable, and programmable for teams.
                    </p>
                </div>

                <div className="mt-16 grid gap-8 lg:grid-cols-3">
                    {phases.map((phase) => (
                        <div
                            key={phase.phase}
                            className={`rounded-2xl p-6 ${phase.status === 'current'
                                    ? 'bg-cyan-950 ring-2 ring-cyan-500'
                                    : 'bg-gray-800'
                                }`}
                        >
                            <div className="flex items-center justify-between">
                                <span className={`text-sm font-medium ${phase.status === 'current' ? 'text-cyan-400' : 'text-gray-400'
                                    }`}>
                                    {phase.phase}
                                </span>
                                {phase.status === 'current' && (
                                    <span className="rounded-full bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-400 ring-1 ring-inset ring-cyan-500/20">
                                        Live
                                    </span>
                                )}
                            </div>
                            <h3 className="mt-4 text-xl font-semibold text-white">
                                {phase.title}
                            </h3>
                            <p className="mt-2 text-sm text-gray-400">
                                {phase.goal}
                            </p>
                            <ul className="mt-6 space-y-3">
                                {phase.items.map((item) => (
                                    <li key={item.name} className="flex items-start gap-3">
                                        {item.done ? (
                                            <CheckIcon className="h-5 w-5 flex-none text-cyan-400" />
                                        ) : (
                                            <CircleIcon className="h-5 w-5 flex-none text-gray-600" />
                                        )}
                                        <span className={`text-sm ${item.done ? 'text-gray-300' : 'text-gray-500'
                                            }`}>
                                            {item.name}
                                        </span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </div>

                {/* Feature Request CTA */}
                <div className="mt-16 text-center">
                    <p className="text-gray-400">
                        Want a feature? We listen to our users.
                    </p>
                    <a
                        href="mailto:features@codetether.run?subject=Feature Request"
                        className="mt-4 inline-flex items-center gap-2 text-cyan-400 hover:text-cyan-300 font-medium"
                    >
                        Request a feature
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                        </svg>
                    </a>
                </div>
            </Container>
        </section>
    )
}
