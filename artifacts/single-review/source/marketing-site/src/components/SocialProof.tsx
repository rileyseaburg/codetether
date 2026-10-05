'use client'

import { Container } from '@/components/Container'

export function SocialProof() {
    return (
        <section className="border-y border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 py-8">
            <Container>
                <div className="flex flex-wrap items-center justify-center gap-8 text-sm text-gray-500 dark:text-gray-400">
                    <span className="text-cyan-600 dark:text-cyan-400 font-medium">60+ Registered Tools</span>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                    <span>OKR → PRD → Ralph</span>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                    <span>Swarm & Relay</span>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                    <span>MCP Bridge</span>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                    <span>OPA Rego RBAC</span>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                    <span className="text-cyan-600 dark:text-cyan-400 font-medium">Browser Replay + Media AI</span>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                    <span>K8s Native</span>
                </div>
            </Container>
        </section>
    )
}

export function Testimonials() {
    const features = [
        {
            title: 'Autonomous Coding',
            description: 'Start with an objective. CodeTether generates the PRD, maps work to stories, runs Ralph, tests, and returns a ready-to-merge branch.',
            highlight: true,
        },
        {
            title: 'Swarm Orchestration',
            description: 'Spawn focused sub-agents or run best-effort swarms in parallel — security, performance, docs, QA — with shared results aggregated automatically.',
        },
        {
            title: 'Multi-Modal Control',
            description: "Voice synthesis, podcasts, avatar video, YouTube upload, browser automation with network replay, and MCP bridge to any external tool server.",
        },
        {
            title: 'Enterprise Security',
            description: 'OPA Rego policy engine, RBAC across 5 roles, tenant isolation, Ed25519 plugin signing, and K8s-native deployment.',
            highlight: true,
        },
    ]

    return (
        <section
            id="features"
            aria-labelledby="features-title"
            className="py-20 sm:py-32 bg-white dark:bg-gray-950"
        >
            <Container>
                <div className="mx-auto max-w-2xl text-center">
                    <h2
                        id="features-title"
                        className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white"
                    >
                        The Four Pillars
                    </h2>
                    <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                        Autonomous AI that codes, orchestrates, and deploys — end to end.
                    </p>
                </div>
                <div className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-8 lg:max-w-none lg:grid-cols-4">
                    {features.map((feature) => (
                        <div
                            key={feature.title}
                            className={`rounded-2xl p-8 ${feature.highlight
                                ? 'bg-gradient-to-b from-cyan-950/40 to-gray-900 dark:bg-gray-800 border border-cyan-500/40'
                                : 'bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-800'
                                }`}
                        >
                            <h3 className={`font-bold text-lg ${feature.highlight
                                ? 'text-cyan-400'
                                : 'text-gray-900 dark:text-white'
                                }`}>
                                {feature.title}
                            </h3>
                            <p className={`mt-2 text-sm ${feature.highlight
                                ? 'text-gray-300'
                                : 'text-gray-600 dark:text-gray-400'
                                }`}>
                                {feature.description}
                            </p>
                        </div>
                    ))}
                </div>
            </Container>
        </section>
    )
}
