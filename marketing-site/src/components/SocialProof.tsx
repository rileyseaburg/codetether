import { Container } from '@/components/Container'

export function SocialProof() {
    const stats = [
        {
            label: 'Open Source',
            value: 'Apache 2.0',
            detail: 'Commercial-friendly license',
        },
        {
            label: 'A2A Protocol',
            value: 'v0.3 Compliant',
            detail: 'Industry standard',
        },
        {
            label: 'Self-Hostable',
            value: '100%',
            detail: 'You control your data',
        },
    ]
    return (
        <section className="border-y border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 py-12">
            <Container>
                <div className="mx-auto max-w-4xl text-center">
                <p className="text-sm font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-400">
                    Production-Ready Foundation
                </p>
                <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-3">
                    {stats.map((stat) => (
                        <div key={stat.label} className="rounded-lg bg-white dark:bg-gray-800 p-4 shadow">
                            <div className="text-xs font-medium text-gray-500 dark:text-gray-400">{stat.label}</div>
                            <div className="mt-1 text-xl font-bold text-gray-900 dark:text-white">{stat.value}</div>
                            <div className="mt-0.5 text-xs text-gray-600 dark:text-gray-400">{stat.detail}</div>
                        </div>
                    ))}
                </div>
                </div>
            </Container>
        </section>
    )
}

export function Testimonials() {
    const features = [
        {
            title: 'Pull Architecture',
            description: 'Workers poll for tasks instead of receiving inbound connections. Zero firewall rules to approve. Security teams love it.',
            icon: '⬇️',
        },
        {
            title: 'Zero Third-Party Storage',
            description: 'CodeTether does not proxy or store your prompts and source code. The Control Plane only needs orchestration metadata.',
            icon: '🛡️',
        },
        {
            title: 'A2A Protocol Native',
            description: 'Built on Google and Microsoft\'s A2A protocol specification for agent-to-agent communication and orchestration.',
            icon: '🔗',
        },
    ]

    return (
        <section
            id="testimonials"
            aria-labelledby="testimonials-title"
            className="py-20 sm:py-32 bg-white dark:bg-gray-950"
        >
            <Container>
                <div className="mx-auto max-w-2xl text-center">
                    <h2
                        id="testimonials-title"
                        className="text-3xl font-medium tracking-tight text-gray-900 dark:text-white"
                    >
                        v1.2.0 Highlights
                    </h2>
                    <p className="mt-2 text-lg text-gray-600 dark:text-gray-300">
                        What makes CodeTether production-ready.
                    </p>
                </div>
                <div className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-8 lg:max-w-none lg:grid-cols-3">
                    {features.map((feature) => (
                        <figure
                            key={feature.title}
                            className="rounded-2xl bg-white dark:bg-gray-900 p-8 shadow-lg ring-1 ring-gray-900/5 dark:ring-gray-800"
                        >
                            <div className="text-4xl mb-4">{feature.icon}</div>
                            <figcaption>
                                <h3 className="font-semibold text-gray-900 dark:text-white text-lg">
                                    {feature.title}
                                </h3>
                                <p className="mt-2 text-sm text-gray-700 dark:text-gray-300">
                                    {feature.description}
                                </p>
                            </figcaption>
                        </figure>
                    ))}
                </div>
            </Container>
        </section>
    )
}
