import { Container } from '@/components/Container'

const phases = [
    {
        phase: 'Now → 3 months',
        title: 'Solidify the Core',
        status: 'current',
        goal: 'Make CodeTether a rock-solid, self-hostable A2A implementation.',
        items: [
            { name: 'A2A protocol implementation', done: true },
            { name: 'Redis message broker & task queues', done: true },
            { name: 'SSE streaming for real-time output', done: true },
            { name: 'Session history & resumption API', done: true },
            { name: 'MCP client integration', done: true },
            { name: 'Keycloak OIDC integration', done: true },
            { name: 'Helm chart for Kubernetes', done: true },
            { name: 'CLI: codetether init & codetether dev', done: false },
            { name: 'Python SDK v1', done: false },
            { name: 'TypeScript client for web UI', done: false },
            { name: 'Hosted Pro MVP (single-region)', done: false },
        ],
    },
    {
        phase: '3–6 months',
        title: 'Teams Love It',
        status: 'upcoming',
        goal: 'Move from cool open source project to standard runtime for agent systems.',
        items: [
            { name: 'Multi-tenant architecture', done: false },
            { name: 'Horizontal autoscaling policies', done: false },
            { name: 'OpenTelemetry traces & metrics', done: false },
            { name: 'Fine-grained RBAC & API tokens', done: false },
            { name: 'Secret management (Vault/SSM/AKV)', done: false },
            { name: 'Audit logs for compliance', done: false },
            { name: 'Rust worker SDK', done: false },
            { name: 'Node/TypeScript SDK', done: false },
            { name: 'Live workflow graph in dashboard', done: false },
            { name: 'Multi-region Pro (EU + US)', done: false },
        ],
    },
    {
        phase: '6–12+ months',
        title: 'Enterprise & Ecosystem',
        status: 'future',
        goal: 'Become the go-to A2A control plane for enterprises.',
        items: [
            { name: 'Enterprise Edition (on-prem/VPC)', done: false },
            { name: 'SOC 2 Type II compliance', done: false },
            { name: 'Built-in orchestrator agent', done: false },
            { name: 'Policy engine for tool calls', done: false },
            { name: 'Content filters (PII, toxicity)', done: false },
            { name: 'Agent & Tool Registry marketplace', done: false },
            { name: 'Enterprise SLAs (99.99%)', done: false },
            { name: 'Dedicated TAM & 24/7 support', done: false },
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
                        Roadmap to the standard A2A runtime
                    </h2>
                    <p className="mt-4 text-lg text-gray-400">
                        We&apos;re building CodeTether to be the production-grade foundation
                        for teams serious about multi-agent systems.
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
                                        In Progress
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
            </Container>
        </section>
    )
}
