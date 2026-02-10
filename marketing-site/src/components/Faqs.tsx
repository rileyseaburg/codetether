'use client'

import { Container } from '@/components/Container'

const faqs = [
    [
        {
            question: 'How is CodeTether different from OpenClaw?',
            answer: 'OpenClaw is a Node.js gateway that shipped with auth: none by default. CodeTether is a Rust-based perpetual cognition runtime with mandatory HMAC-SHA256 authentication, Ed25519 code-signed sandboxed plugins, persona swarms with scoped permissions, and append-only audit logging. It self-deploys on Kubernetes. These are shipped features in v1.1.0, not a roadmap.',
        },
        {
            question: 'Why is CodeTether written in Rust?',
            answer: 'An autonomous agent with system-level access IS infrastructure. Memory safety isn\'t optional when your agent can read files, execute commands, and take actions on its own. You wouldn\'t write a database in JavaScript — you shouldn\'t write an autonomous agent in it either.',
        },
        {
            question: 'What are Persona Swarms?',
            answer: 'Instead of one bot, you get a coordinated team of agents — monitoring, deployment, code review — each with its own scoped permissions and security boundary. A compromised monitor can\'t escalate to deploy access. That\'s not paranoia, that\'s basic engineering.',
        },
    ],
    [
        {
            question: 'What is perpetual cognition?',
            answer: 'Most AI agents are request-response: you ask, they answer. CodeTether runs continuous thought loops that persist across restarts, survive node failures, and scale horizontally. Your agents reason, plan, and act autonomously — not just when you type something.',
        },
        {
            question: 'Can agents modify their own code?',
            answer: 'Yes. CodeTether agents can write code, open PRs, and evolve their capabilities. But every modification goes through an auditable gate you define. Every decision is logged, every action is traceable. The agents get smarter while you stay in control.',
        },
        {
            question: 'What is RLM?',
            answer: 'RLM (Recursive Language Models) is MIT research that treats input as an environment variable, not direct LLM context. Instead of stuffing everything into one prompt, RLM recursively decomposes tasks, processes chunks independently, verifies results, and stitches them together. CodeTether uses RLM to handle 10M+ tokens.',
        },
    ],
    [
        {
            question: 'Can I self-host?',
            answer: 'Yes. CodeTether is open source under the MIT License. Run it on your own servers with full control. Docker images and Helm charts provided. Your infrastructure shouldn\'t depend on someone else\'s business model.',
        },
        {
            question: 'How does the security model work?',
            answer: 'Authentication uses HMAC-SHA256 bearer tokens and is mandatory — there is no flag to disable it. All plugins are sandboxed with Ed25519 code signing and SHA-256 integrity checks. Every action is logged to an append-only JSON Lines audit trail with timestamps, categories, and metadata. Persona swarms enforce least-privilege — each agent only has the permissions it needs. Agency plans can add custom OPA Rego policies.',
        },
        {
            question: 'Is there a managed/hosted option?',
            answer: 'Yes. Self-host for free, or use our managed platform with tiered pricing: Free (10 tasks/mo), Pro ($297/mo, 300 tasks), and Agency ($497/mo, 2000 tasks). All plans include the same security guarantees.',
        },
    ],
]

export function Faqs() {
    return (
        <section
            id="faqs"
            aria-labelledby="faqs-title"
            className="border-t border-gray-200 dark:border-gray-800 py-20 sm:py-32 bg-white dark:bg-gray-950"
        >
            <Container>
                <div className="mx-auto max-w-2xl lg:mx-0">
                    <h2
                        id="faqs-title"
                        className="text-3xl font-medium tracking-tight text-gray-900 dark:text-white"
                    >
                        Frequently Asked Questions
                    </h2>
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
                                        <h3 className="text-lg/6 font-semibold text-gray-900 dark:text-white">
                                            {faq.question}
                                        </h3>
                                        <p className="mt-4 text-sm text-gray-600 dark:text-gray-400">{faq.answer}</p>
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
