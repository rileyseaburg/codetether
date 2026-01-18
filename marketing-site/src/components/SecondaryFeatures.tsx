import { useId } from 'react'

import { Container } from '@/components/Container'

const features = [
    {
        name: 'RLM: Infinite Context',
        description:
            'Revolutionary Recursive Language Models process arbitrarily long contexts through recursive sub-LLM calls. Analyze entire monorepos without context limits.',
        icon: RLMIcon,
    },
    {
        name: 'Zero Inbound Firewall Rules',
        description:
            'Workers PULL tasks from your server—never the other way around. Security teams approve because there\'s nothing to approve. No ports, no VPNs, no attack surface.',
        icon: SystemsIcon,
    },
    {
        name: 'Data Gravity Respected',
        description:
            'Your source code, patient records, and financial data have "gravity"—they can\'t move. We move the AI to them. Workers run inside your VPC and only send back results.',
        icon: DataIcon,
    },
    {
        name: 'HIPAA / SOC2 / PCI Ready',
        description:
            'Built for regulated industries from day one. Keycloak SSO, RBAC, audit logs, network policies, and Kubernetes isolation. The compliance checkbox is already checked.',
        icon: EnterpriseIcon,
    },
    {
        name: 'Open Standards (A2A + MCP)',
        description:
            'Built on Google/Microsoft\'s A2A protocol and Anthropic\'s MCP. No vendor lock-in—your agents speak the same language as Claude, Gemini, and the rest of the ecosystem.',
        icon: OpenSourceIcon,
    },
    {
        name: 'Human-in-the-Loop Built In',
        description:
            'Real-time dashboard for oversight. Approve sensitive actions, intervene when agents need guidance, and audit everything. AI augments humans, never replaces judgment.',
        icon: MonitorIcon,
    },
]

function SystemsIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#06b6d4" fillOpacity={0.2} />
            <circle cx={10} cy={12} r={3} fill="#06b6d4" />
            <circle cx={22} cy={12} r={3} fill="#06b6d4" />
            <circle cx={16} cy={22} r={3} fill="#06b6d4" />
            <path d="M10 15v4l6 3M22 15v4l-6 3" stroke="#06b6d4" strokeWidth={2} fill="none" />
        </svg>
    )
}

function DataIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#06b6d4" fillOpacity={0.2} />
            <path
                d="M8 10h6v12H8zM18 10h6v12h-6z"
                fill="#06b6d4"
            />
            <path d="M14 16h4" stroke="#06b6d4" strokeWidth={2} strokeDasharray="2 2" />
        </svg>
    )
}

function EnterpriseIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#06b6d4" fillOpacity={0.2} />
            <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M16 6a4 4 0 00-4 4v2H8v14h16V12h-4v-2a4 4 0 00-4-4zm-2 4a2 2 0 114 0v2h-4v-2zm2 8a2 2 0 100 4 2 2 0 000-4z"
                fill="#06b6d4"
            />
        </svg>
    )
}

function OpenSourceIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#06b6d4" fillOpacity={0.2} />
            <path
                d="M16 6c-5.523 0-10 4.477-10 10 0 4.42 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.603-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.27.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0116 9.5c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.026 2.747-1.026.546 1.38.202 2.397.1 2.65.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C23.138 24.163 26 20.418 26 16c0-5.523-4.477-10-10-10z"
                fill="#06b6d4"
            />
        </svg>
    )
}

function MCPIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#06b6d4" fillOpacity={0.2} />
            <path
                d="M10 10h4v4h-4zM18 10h4v4h-4zM10 18h4v4h-4zM18 18h4v4h-4z"
                fill="#06b6d4"
            />
            <path
                d="M14 12h4M12 14v4M20 14v4M14 20h4"
                stroke="#06b6d4"
                strokeWidth={2}
            />
        </svg>
    )
}

function MonitorIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#06b6d4" fillOpacity={0.2} />
            <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M6 8a2 2 0 012-2h16a2 2 0 012 2v12a2 2 0 01-2 2h-6v2h4v2H10v-2h4v-2H8a2 2 0 01-2-2V8zm2 0v12h16V8H8zm4 3h8v2h-8v-2zm0 4h5v2h-5v-2z"
                fill="#06b6d4"
            />
        </svg>
    )
}

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

export function SecondaryFeatures() {
    return (
        <section
            id="secondary-features"
            aria-label="Core value propositions"
            className="py-20 sm:py-32 bg-white dark:bg-gray-950"
        >
            <Container>
                <div className="mx-auto max-w-2xl sm:text-center">
                    <h2 className="text-3xl font-medium tracking-tight text-gray-900 dark:text-white">
                        Why Security Teams Say &quot;Yes&quot;
                    </h2>
                    <p className="mt-2 text-lg text-gray-600 dark:text-gray-300">
                        The difference between &quot;AI as a toy&quot; and &quot;AI as a workforce&quot; is access.
                        CodeTether solves the secure access problem that kills enterprise AI projects.
                    </p>
                </div>
                <ul
                    role="list"
                    className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-6 text-sm sm:mt-20 sm:grid-cols-2 md:gap-y-10 lg:max-w-none lg:grid-cols-3"
                >
                    {features.map((feature) => (
                        <li
                            key={feature.name}
                            className="rounded-2xl border border-gray-200 dark:border-gray-800 p-8 hover:border-cyan-500 dark:hover:border-cyan-500 hover:shadow-lg dark:hover:shadow-cyan-500/10 transition-all bg-white dark:bg-gray-900"
                        >
                            <feature.icon className="h-8 w-8" />
                            <h3 className="mt-6 font-semibold text-gray-900 dark:text-white">
                                {feature.name}
                            </h3>
                            <p className="mt-2 text-gray-700 dark:text-gray-300">{feature.description}</p>
                        </li>
                    ))}
                </ul>
            </Container>
        </section>
    )
}
