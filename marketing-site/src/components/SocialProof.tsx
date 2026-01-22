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
            title: 'Webhook Integration',
            description: 'Trigger tasks from Zapier, n8n, Make, or any HTTP request.',
        },
        {
            title: 'RLM Processing',
            description: 'Recursive Language Models handle 10M+ tokens—100x beyond normal LLM context. AI works 5-60 minutes with recursive decomposition.',
            highlight: true,
        },
        {
            title: 'Email Delivery',
            description: 'Results delivered to your inbox with file attachments.',
        },
        {
            title: 'RLM Technology',
            description: 'MIT research enabling unlimited context windows. Background processing with variable stitching produces real file outputs.',
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
                        className="text-3xl font-medium tracking-tight text-gray-900 dark:text-white"
                    >
                        How It Works
                    </h2>
                </div>
                <div className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-8 lg:max-w-none lg:grid-cols-4">
                    {features.map((feature) => (
                        <div
                            key={feature.title}
                            className={`rounded-2xl p-8 ${
                                feature.highlight
                                    ? 'bg-gray-900 dark:bg-gray-800 border border-cyan-500/30'
                                    : 'bg-gray-50 dark:bg-gray-900'
                            }`}
                        >
                            <h3 className={`font-semibold text-lg ${
                                feature.highlight
                                    ? 'text-cyan-400'
                                    : 'text-gray-900 dark:text-white'
                            }`}>
                                {feature.title}
                            </h3>
                            <p className={`mt-2 text-sm ${
                                feature.highlight
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
