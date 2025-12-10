import { Container } from '@/components/Container'

const useCases = [
    {
        title: 'AI Coding Assistants',
        description:
            'Deploy AI coding agents across your development team. Workers run on developer machines with full codebase access, streaming results back through the central server.',
        icon: '💻',
        features: ['OpenCode integration', 'Session resumption', 'Multi-repo support'],
    },
    {
        title: 'Customer Support Automation',
        description:
            'Orchestrate multiple specialized agents to handle support tickets. Route queries to the right agent, escalate to humans when needed.',
        icon: '🎧',
        features: ['Human-in-the-loop', 'Agent handoffs', 'Real-time monitoring'],
    },
    {
        title: 'Data Pipeline Orchestration',
        description:
            'Coordinate AI agents for ETL workflows. One agent extracts, another transforms, another loads—all communicating through A2A.',
        icon: '🔄',
        features: ['Task chaining', 'Error handling', 'Progress tracking'],
    },
    {
        title: 'Research & Analysis',
        description:
            'Deploy research agents that gather information, analysis agents that synthesize findings, and report agents that present results.',
        icon: '🔬',
        features: ['Multi-agent workflows', 'Knowledge sharing', 'Collaborative reasoning'],
    },
    {
        title: 'DevOps Automation',
        description:
            'AI agents that monitor systems, diagnose issues, and coordinate remediation. From alerting to resolution, fully automated.',
        icon: '⚙️',
        features: ['Kubernetes native', 'Incident response', 'Auto-remediation'],
    },
    {
        title: 'Content Generation',
        description:
            'Coordinate specialized agents for different content types. One writes, another edits, another optimizes for SEO.',
        icon: '✍️',
        features: ['Quality control', 'Style consistency', 'Multi-format output'],
    },
]

export function UseCases() {
    return (
        <section
            id="use-cases"
            aria-labelledby="use-cases-title"
            className="bg-white py-20 sm:py-32"
        >
            <Container>
                <div className="mx-auto max-w-2xl lg:mx-0">
                    <h2
                        id="use-cases-title"
                        className="text-3xl font-medium tracking-tight text-gray-900"
                    >
                        Built for real-world AI workflows
                    </h2>
                    <p className="mt-2 text-lg text-gray-600">
                        See how teams use CodeTether to orchestrate AI agents across industries.
                    </p>
                </div>
                <div className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-6 sm:mt-20 lg:max-w-none lg:grid-cols-3">
                    {useCases.map((useCase) => (
                        <div
                            key={useCase.title}
                            className="flex flex-col rounded-2xl border border-gray-200 p-8 hover:border-gray-300 hover:shadow-lg transition-all"
                        >
                            <div className="text-4xl">{useCase.icon}</div>
                            <h3 className="mt-4 text-lg font-semibold text-gray-900">
                                {useCase.title}
                            </h3>
                            <p className="mt-2 flex-grow text-sm text-gray-600">
                                {useCase.description}
                            </p>
                            <ul className="mt-4 flex flex-wrap gap-2">
                                {useCase.features.map((feature) => (
                                    <li
                                        key={feature}
                                        className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700"
                                    >
                                        {feature}
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
