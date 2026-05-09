import { Container } from '@/components/Container'

const features = [
    {
        name: 'RLM: Infinite Context',
        description:
            'Recursive Language Model processing lets the agent analyze whole repositories, large histories, and sprawling docs with recursive chunking, synthesis, and verification.',
        icon: RLMIcon,
    },
    {
        name: 'Persistent Memory & Recall',
        description:
            'Session recall, context browsing, curated memory, and task state keep long-running work coherent across resets, handoffs, and fresh agent iterations.',
        icon: MCPIcon,
    },
    {
        name: 'Swarm Orchestration',
        description:
            'Spawn parallel sub-agents with specialized roles. Security review, performance analysis, documentation, QA, and implementation can run concurrently.',
        icon: SwarmIcon,
    },
    {
        name: 'Relay Task Routing',
        description:
            'Autonomous delegation between agents. Hand off context, chain multi-step workflows, and orchestrate complex pipelines across specialized AI instances.',
        icon: RelayIcon,
    },
    {
        name: 'MCP + Browser Replay',
        description:
            'Bridge external MCP servers and control real browsers. Inspect DOM, upload files, capture app traffic, and replay authenticated XHR/fetch requests safely.',
        icon: FileIcon,
    },
    {
        name: 'Voice & Media Pipeline',
        description:
            'Built-in text-to-speech, transcription, podcast generation, YouTube upload, image input, and AI avatar video. Go from a script to a published asset.',
        icon: VoiceIcon,
    },
]

function RLMIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#8B5CF6" fillOpacity={0.2} />
            <path
                d="M8 16c0-2.2 1.8-4 4-4s4 1.8 4 4-1.8 4-4 4-4-1.8-4-4zm8 0c0-2.2 1.8-4 4-4s4 1.8 4 4-1.8 4-4 4-4-1.8-4-4z"
                stroke="#8B5CF6"
                strokeWidth={2}
                fill="none"
            />
        </svg>
    )
}

function MCPIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#06B6D4" fillOpacity={0.2} />
            <path
                d="M12 8h8l4 8-4 8h-8l-4-8 4-8z"
                stroke="#06B6D4"
                strokeWidth={2}
                fill="none"
            />
            <circle cx={16} cy={16} r={3} fill="#06B6D4" />
        </svg>
    )
}

function SwarmIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#F59E0B" fillOpacity={0.2} />
            <circle cx={16} cy={10} r={3} fill="#F59E0B" />
            <circle cx={10} cy={20} r={3} fill="#F59E0B" />
            <circle cx={22} cy={20} r={3} fill="#F59E0B" />
            <path
                d="M16 13v4M16 17l-6 3M16 17l6 3"
                stroke="#F59E0B"
                strokeWidth={2}
            />
        </svg>
    )
}

function RelayIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#10B981" fillOpacity={0.2} />
            <path
                d="M8 10h6v6H8zM18 16h6v6h-6z"
                stroke="#10B981"
                strokeWidth={2}
                fill="none"
            />
            <path
                d="M14 13h4M14 19h4"
                stroke="#10B981"
                strokeWidth={2}
                strokeDasharray="2 2"
            />
        </svg>
    )
}

function FileIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#3B82F6" fillOpacity={0.2} />
            <path
                d="M10 8h8l4 4v12a2 2 0 01-2 2H10a2 2 0 01-2-2V10a2 2 0 012-2z"
                stroke="#3B82F6"
                strokeWidth={2}
                fill="none"
            />
            <path
                d="M18 8v4h4"
                stroke="#3B82F6"
                strokeWidth={2}
                fill="none"
            />
        </svg>
    )
}

function VoiceIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#EC4899" fillOpacity={0.2} />
            <path
                d="M12 10v12a2 2 0 004 0V10a2 2 0 00-4 0z"
                stroke="#EC4899"
                strokeWidth={2}
                fill="none"
            />
            <path
                d="M8 16a8 8 0 0016 0"
                stroke="#EC4899"
                strokeWidth={2}
                fill="none"
            />
            <path
                d="M16 24v3"
                stroke="#EC4899"
                strokeWidth={2}
                strokeLinecap="round"
            />
        </svg>
    )
}

export function SecondaryFeatures() {
    return (
        <section
            id="secondary-features"
            aria-label="Platform capabilities"
            className="py-20 sm:py-32 bg-gray-50 dark:bg-gray-900"
        >
            <Container>
                <div className="mx-auto max-w-2xl sm:text-center">
                    <h2 className="text-3xl font-medium tracking-tight text-gray-900 dark:text-white">
                        The AI Development Platform
                    </h2>
                    <p className="mt-2 text-lg text-gray-600 dark:text-gray-300">
                        60+ registered tools, multi-modal AI, persistent context, and enterprise-grade orchestration — all from a single binary.
                    </p>
                </div>
                <ul
                    role="list"
                    className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-6 text-sm sm:mt-20 sm:grid-cols-2 md:gap-y-10 lg:max-w-none lg:grid-cols-3"
                >
                    {features.map((feature) => (
                        <li
                            key={feature.name}
                            className="rounded-2xl border border-gray-200 dark:border-gray-800 p-8 hover:border-cyan-500 dark:hover:border-cyan-500 hover:shadow-lg hover:shadow-cyan-500/10 transition-all bg-white dark:bg-gray-950"
                        >
                            <feature.icon className="h-8 w-8" />
                            <h3 className="mt-6 font-semibold text-gray-900 dark:text-white">
                                {feature.name}
                            </h3>
                            <p className="mt-2 text-gray-600 dark:text-gray-300">{feature.description}</p>
                        </li>
                    ))}
                </ul>
            </Container>
        </section>
    )
}
