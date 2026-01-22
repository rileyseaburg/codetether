'use client'

import { Container } from '@/components/Container'

const phases = [
    {
        phase: 'Now',
        title: 'Core Platform',
        status: 'current',
        goal: 'The AI worker your automations deserve.',
        items: [
            { name: 'Webhook trigger API', done: true },
            { name: 'RLM infinite context processing', done: true },
            { name: 'RLM answer verification', done: true },
            { name: 'Email delivery with attachments', done: true },
            { name: 'Callback webhooks for automation', done: true },
            { name: 'Session persistence (reply to continue)', done: true },
            { name: 'Real file output (CSV, PDF, code)', done: true },
            { name: 'Background processing (up to 60 min)', done: true },
            { name: 'Zapier/n8n/Make compatibility', done: true },
            { name: 'Dashboard for task monitoring', done: false },
            { name: 'Pre-built workflow templates', done: false },
        ],
    },
    {
        phase: 'Next',
        title: 'Power Features',
        status: 'upcoming',
        goal: 'More automation, more integrations, more output formats.',
        items: [
            { name: 'Scheduled tasks (cron triggers)', done: false },
            { name: 'Google Sheets native integration', done: false },
            { name: 'Airtable native integration', done: false },
            { name: 'Direct Google Drive output', done: false },
            { name: 'Bulk task API (batch processing)', done: false },
            { name: 'Custom output templates', done: false },
            { name: 'Task chaining (multi-step workflows)', done: false },
            { name: 'Team workspaces', done: false },
            { name: 'Zapier app in marketplace', done: false },
            { name: 'Make module in marketplace', done: false },
        ],
    },
    {
        phase: 'Future',
        title: 'AI Superpowers',
        status: 'future',
        goal: 'Advanced AI capabilities for complex automation.',
        items: [
            { name: 'Web browsing/scraping agent', done: false },
            { name: 'Image generation output', done: false },
            { name: 'Voice transcription input', done: false },
            { name: 'RLM deeper recursion layers', done: false },
            { name: 'RLM-trained models', done: false },
            { name: 'RLM async parallel sub-calls', done: false },
            { name: 'Custom trained models (fine-tuning)', done: false },
            { name: 'Multi-model orchestration', done: false },
            { name: 'API for third-party integrations', done: false },
            { name: 'White-label for agencies', done: false },
            { name: 'Self-hosted enterprise edition', done: false },
        ],
    },
]

function CheckIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 20 20" fill="currentColor" {...props}>
            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
        </svg>
    )
}

function CircleIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 20 20" fill="currentColor" {...props}>
            <circle cx="10" cy="10" r="4" />
        </svg>
    )
}

export function Roadmap() {
    return (
        <section
            id="roadmap"
            aria-label="Product roadmap"
            className="bg-gray-900 py-20 sm:py-32"
        >
            <Container>
                <div className="mx-auto max-w-2xl text-center">
                    <h2 className="text-3xl font-medium tracking-tight text-white">
                        Building the Future of AI Automation
                    </h2>
                    <p className="mt-4 text-lg text-gray-400">
                        We ship fast. Here&apos;s what&apos;s done and what&apos;s coming next.
                    </p>
                </div>

                <div className="mt-16 grid gap-8 lg:grid-cols-3">
                    {phases.map((phase) => (
                        <div
                            key={phase.phase}
                            className={`rounded-2xl p-6 ${phase.status === 'current'
                                    ? 'bg-cyan-950 ring-2 ring-cyan-500'
                                    : 'bg-gray-800'
                                }`}
                        >
                            <div className="flex items-center justify-between">
                                <span className={`text-sm font-medium ${phase.status === 'current' ? 'text-cyan-400' : 'text-gray-400'
                                    }`}>
                                    {phase.phase}
                                </span>
                                {phase.status === 'current' && (
                                    <span className="rounded-full bg-cyan-500/10 px-3 py-1 text-xs font-medium text-cyan-400 ring-1 ring-inset ring-cyan-500/20">
                                        Live
                                    </span>
                                )}
                            </div>
                            <h3 className="mt-4 text-xl font-semibold text-white">
                                {phase.title}
                            </h3>
                            <p className="mt-2 text-sm text-gray-400">
                                {phase.goal}
                            </p>
                            <ul className="mt-6 space-y-3">
                                {phase.items.map((item) => (
                                    <li key={item.name} className="flex items-start gap-3">
                                        {item.done ? (
                                            <CheckIcon className="h-5 w-5 flex-none text-cyan-400" />
                                        ) : (
                                            <CircleIcon className="h-5 w-5 flex-none text-gray-600" />
                                        )}
                                        <span className={`text-sm ${item.done ? 'text-gray-300' : 'text-gray-500'
                                            }`}>
                                            {item.name}
                                        </span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </div>

                {/* Feature Request CTA */}
                <div className="mt-16 text-center">
                    <p className="text-gray-400">
                        Want a feature? We listen to our users.
                    </p>
                    <a
                        href="mailto:features@codetether.run?subject=Feature Request"
                        className="mt-4 inline-flex items-center gap-2 text-cyan-400 hover:text-cyan-300 font-medium"
                    >
                        Request a feature
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                        </svg>
                    </a>
                </div>
            </Container>
        </section>
    )
}
