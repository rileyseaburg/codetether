import { Container } from '@/components/Container'

const faqs = [
    [
        {
            question: 'What is A2A Server MCP?',
            answer:
                'A2A Server MCP is an open-source Agent-to-Agent communication server that implements the A2A protocol with Model Context Protocol (MCP) integration. It enables AI agents to communicate, share tasks, and orchestrate complex workflows.',
        },
        {
            question: 'How does distributed worker architecture work?',
            answer:
                'Workers run on remote machines with access to codebases. They poll the central A2A server for tasks, execute them using OpenCode or other agents, and stream results back in real-time. This allows you to run AI coding agents on machines where the code lives.',
        },
        {
            question: 'Can I resume past AI conversations?',
            answer:
                'Yes! Session history is automatically synced from workers to the server. You can browse past sessions from any device and resume them with full context preservation. The AI continues exactly where you left off.',
        },
    ],
    [
        {
            question: 'What authentication methods are supported?',
            answer:
                'A2A Server supports enterprise authentication via Keycloak with OAuth2/OIDC. This includes username/password authentication, token refresh, and role-based access control for agents and codebases.',
        },
        {
            question: 'How do I deploy to production?',
            answer:
                'We provide Helm charts for Kubernetes deployment with horizontal autoscaling, network policies, and TLS termination. A single command deploys the entire stack including Redis message broker and monitoring.',
        },
        {
            question: 'Is there a Swift/iOS client?',
            answer:
                'Yes! We have a native Swift Liquid Glass UI for iOS and macOS with Apple-style glassmorphism design. It supports real-time output streaming, session management, and Keycloak authentication.',
        },
    ],
    [
        {
            question: 'What is MCP integration?',
            answer:
                'Model Context Protocol (MCP) allows agents to access external tools and resources. A2A Server acts as an MCP client, enabling your agents to use file systems, databases, APIs, and other tools through a standardized interface.',
        },
        {
            question: 'How does real-time streaming work?',
            answer:
                'We use Server-Sent Events (SSE) for real-time output streaming. When an agent runs a task, output is streamed line-by-line to the server, which broadcasts it to connected clients. You see responses as they happen.',
        },
        {
            question: 'Is A2A Server free to use?',
            answer:
                'A2A Server MCP is completely open source under the Apache 2.0 license. You can use it for free, modify it, and deploy it anywhere. We also offer enterprise support and hosted solutions.',
        },
    ],
]

export function Faqs() {
    return (
        <section
            id="faqs"
            aria-labelledby="faqs-title"
            className="border-t border-gray-200 py-20 sm:py-32"
        >
            <Container>
                <div className="mx-auto max-w-2xl lg:mx-0">
                    <h2
                        id="faqs-title"
                        className="text-3xl font-medium tracking-tight text-gray-900"
                    >
                        Frequently asked questions
                    </h2>
                    <p className="mt-2 text-lg text-gray-600">
                        Have a different question?{' '}
                        <a
                            href="https://github.com/rileyseaburg/A2A-Server-MCP/discussions"
                            className="text-cyan-600 underline"
                        >
                            Join the discussion on GitHub
                        </a>
                        .
                    </p>
                </div>
                <ul
                    role="list"
                    className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-8 sm:mt-20 lg:max-w-none lg:grid-cols-3"
                >
                    {faqs.map((column, columnIndex) => (
                        <li key={columnIndex}>
                            <ul role="list" className="space-y-10">
                                {column.map((faq, faqIndex) => (
                                    <li key={faqIndex}>
                                        <h3 className="text-lg/6 font-semibold text-gray-900">
                                            {faq.question}
                                        </h3>
                                        <p className="mt-4 text-sm text-gray-700">{faq.answer}</p>
                                    </li>
                                ))}
                            </ul>
                        </li>
                    ))}
                </ul>
            </Container>
        </section>
    )
}
