import { Container } from '@/components/Container'

export function SocialProof() {
    return (
        <section className="border-y border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 py-12">
            <Container>
                <div className="mx-auto max-w-4xl text-center">
                    <p className="text-sm font-semibold uppercase tracking-wide text-gray-600 dark:text-gray-400">
                        Trusted by developers at
                    </p>
                    <div className="mt-8 flex flex-wrap items-center justify-center gap-x-12 gap-y-6 grayscale opacity-70">
                        {/* Placeholder company logos - replace with real ones */}
                        <div className="flex items-center gap-2">
                            <span className="text-3xl">🚀</span>
                            <span className="text-lg font-semibold text-gray-700 dark:text-gray-300">StartupCo</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-3xl">🏢</span>
                            <span className="text-lg font-semibold text-gray-700 dark:text-gray-300">Enterprise Inc</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-3xl">⚡</span>
                            <span className="text-lg font-semibold text-gray-700 dark:text-gray-300">TechForward</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-3xl">🔮</span>
                            <span className="text-lg font-semibold text-gray-700 dark:text-gray-300">AI Labs</span>
                        </div>
                    </div>
                    <div className="mt-10 grid grid-cols-1 gap-8 sm:grid-cols-3">
                        <div>
                            <div className="text-3xl font-bold text-gray-900 dark:text-white">500+</div>
                            <div className="mt-1 text-sm text-gray-600 dark:text-gray-400">GitHub Stars</div>
                        </div>
                        <div>
                            <div className="text-3xl font-bold text-gray-900 dark:text-white">10k+</div>
                            <div className="mt-1 text-sm text-gray-600 dark:text-gray-400">Agent Messages/Day</div>
                        </div>
                        <div>
                            <div className="text-3xl font-bold text-gray-900 dark:text-white">99.9%</div>
                            <div className="mt-1 text-sm text-gray-600 dark:text-gray-400">Uptime SLA</div>
                        </div>
                    </div>
                </div>
            </Container>
        </section>
    )
}

export function Testimonials() {
    const testimonials = [
        {
            quote:
                "A2A Server completely transformed how we build AI features. Our agents now collaborate seamlessly, and the session resumption is a game-changer.",
            author: 'Alex Chen',
            title: 'CTO',
            company: 'AI Startup',
            avatar: '👨‍💻',
        },
        {
            quote:
                "We evaluated several multi-agent frameworks. A2A's Kubernetes-native approach and enterprise security made it the clear choice for production.",
            author: 'Sarah Johnson',
            title: 'VP Engineering',
            company: 'Enterprise Co',
            avatar: '👩‍💼',
        },
        {
            quote:
                "The distributed worker architecture let us run coding agents on our secure infrastructure while managing everything centrally. Brilliant design.",
            author: 'Mike Rivera',
            title: 'Platform Lead',
            company: 'FinTech Corp',
            avatar: '👨‍🔬',
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
                        Loved by AI teams
                    </h2>
                    <p className="mt-2 text-lg text-gray-600 dark:text-gray-300">
                        See what developers are saying about A2A Server MCP.
                    </p>
                </div>
                <div className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-8 lg:max-w-none lg:grid-cols-3">
                    {testimonials.map((testimonial) => (
                        <figure
                            key={testimonial.author}
                            className="rounded-2xl bg-white dark:bg-gray-900 p-8 shadow-lg ring-1 ring-gray-900/5 dark:ring-gray-800"
                        >
                            <blockquote className="text-gray-700 dark:text-gray-300">
                                <p>"{testimonial.quote}"</p>
                            </blockquote>
                            <figcaption className="mt-6 flex items-center gap-4">
                                <div className="h-12 w-12 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center text-2xl">
                                    {testimonial.avatar}
                                </div>
                                <div>
                                    <div className="font-semibold text-gray-900 dark:text-white">
                                        {testimonial.author}
                                    </div>
                                    <div className="text-sm text-gray-600 dark:text-gray-400">
                                        {testimonial.title}, {testimonial.company}
                                    </div>
                                </div>
                            </figcaption>
                        </figure>
                    ))}
                </div>
            </Container>
        </section>
    )
}
