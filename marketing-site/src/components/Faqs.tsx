import { Container } from '@/components/Container'

const faqs = [
    [
        {
            question: 'We already have GitHub Copilot. Why do we need CodeTether?',
            answer:
                'Copilot is fantastic for helping a human type faster—it\'s a plugin. CodeTether is a workforce. Copilot cannot run a 20-minute background job to refactor a legacy module while your developer sleeps. If you run a long-running autonomous agent inside a VDI slice, you\'ll crash the VDI. Our agents run on backend servers where compute is cheap and access is secure, streaming results back to the VDI. Keep Copilot for autocomplete; use CodeTether for the heavy lifting.',
        },
        {
            question: 'How does CodeTether work with Copilot via MCP?',
            answer:
                'Because CodeTether is an MCP Server, Copilot can call your agents like API tools. A developer in VS Code says "refactor this auth module," Copilot calls codetether.spawn_agent(), our worker runs the job in your VPC for 20 minutes, and Copilot gets a ping back: "Job done. Here\'s the PR link." Your devs stay in VS Code; heavy work runs on secure backend servers.',
        },
        {
            question: 'Can I resume past AI conversations?',
            answer:
                'Yes! Session history is automatically synced from workers to the server. You can browse past sessions from any device and resume them with full context preservation. The AI continues exactly where you left off—unlike Copilot which forgets after 10 minutes.',
        },
    ],
    [
        {
            question: 'What about data security and compliance?',
            answer:
                'Workers PULL tasks from inside your network—no inbound firewall rules needed. Your source code, patient records, and financial data never leave your VPC. We process locally and return only results. Built for HIPAA, SOC2, PCI from day one with Keycloak SSO, RBAC, and audit logs.',
        },
        {
            question: 'How do I deploy to production?',
            answer:
                'We provide Helm charts for Kubernetes deployment with horizontal autoscaling, network policies, and TLS termination. A single command deploys the entire stack including Redis message broker and monitoring. Workers can run anywhere—on-prem, in your VPC, or on developer machines.',
        },
        {
            question: 'What happens when the developer closes their laptop?',
            answer:
                'Unlike Copilot which stops when the IDE closes, CodeTether agents are "fire and forget." Developer says "refactor this authentication module," closes their laptop at 5 PM, goes home. The CodeTether worker keeps running all night. When they log in the next morning, the job is done with a PR ready for review.',
        },
    ],
    [
        {
            question: 'Can we customize agents for our specific workflows?',
            answer:
                'Absolutely. Unlike Copilot (a black box product), CodeTether is a platform you control. Build a Compliance Agent that checks code before committing. Build a COBOL Migration Agent. Chain agents: "Check Jira first, then code, then test." You own the orchestration layer and the prompts.',
        },
        {
            question: 'Can\'t our senior engineer just build this?',
            answer:
                'Yes—and here\'s what will happen. Day 1: "It works!" Day 30: Redis queue crashes production. Day 60: Security audit finds no encryption. Day 90: That engineer quits and now nobody knows how the "internal agent runner" works. LLMs write scripts in 10 seconds; CodeTether is the runtime that keeps those scripts safe in production. You\'re not buying code—you\'re avoiding maintenance debt.',
        },
        {
            question: 'What is MCP integration?',
            answer:
                'Model Context Protocol (MCP) is Anthropic\'s open standard for AI tools. CodeTether implements MCP, so any MCP-compatible client (including GitHub Copilot) can dispatch work to your secure backend workers. Your agents can access file systems, databases, APIs, and custom tools through this standardized interface.',
        },
        {
            question: 'Is CodeTether free to use?',
            answer:
                'CodeTether is completely open source under the Apache 2.0 license. You can use it for free, modify it, and deploy it anywhere. We also offer enterprise support, managed hosting, and custom deployments for organizations that want production SLAs and dedicated support.',
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
                        Frequently asked questions
                    </h2>
                    <p className="mt-2 text-lg text-gray-600 dark:text-gray-300">
                        Have a different question?{' '}
                        <a
                            href="https://github.com/rileyseaburg/A2A-Server-MCP/discussions"
                            className="text-cyan-600 dark:text-cyan-400 underline"
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
                                        <h3 className="text-lg/6 font-semibold text-gray-900 dark:text-white">
                                            {faq.question}
                                        </h3>
                                        <p className="mt-4 text-sm text-gray-700 dark:text-gray-300">{faq.answer}</p>
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
