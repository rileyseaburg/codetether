'use client'

import { Container } from '@/components/Container'

export function SocialProof() {
    return (
        <section className="border-y border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 py-8">
            <Container>
                <div className="flex flex-wrap items-center justify-center gap-8 text-sm text-gray-500 dark:text-gray-400">
                    <span>Webhook trigger</span>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                    <span className="text-cyan-600 dark:text-cyan-400 font-medium">RLM processing</span>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                    <span>10M+ token context</span>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                    <span>Email delivery</span>
                    <span className="text-gray-300 dark:text-gray-600">|</span>
                    <span>Real file output</span>
                </div>
            </Container>
        </section>
    )
}

export function Testimonials() {
    const features = [
        {
            title: 'Trigger Once',
            description: 'Use dashboard, iOS app, webhook API, Zapier, n8n, or Make.',
        },
        {
            title: 'Process',
            description: 'The AI decomposes the job, runs recursive work, verifies outputs, and stitches results—5-60 minutes unattended.',
            highlight: true,
        },
        {
            title: 'Deliver',
            description: 'Get results via email (with attachments), webhook callback (JSON), or dashboard download.',
        },
        {
            title: 'Scale Complex Tasks',
            description: 'RLM (MIT research) processes 10M+ tokens without degradation. Handles datasets and workflows normal AI can\'t.',
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
                        The Three Steps
                    </h2>
                    <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                        From trigger to delivery—it's that simple.
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
