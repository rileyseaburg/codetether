'use client'

import { Container } from '@/components/Container'
import { Button } from '@/components/Button'

const outcomes = [
    'Generate PRDs from rough objectives',
    'Run Ralph loops against real repos',
    'Spawn focused reviewer/tester/doc swarms',
    'Govern tools with OPA and audit trails',
]

export function CallToAction() {
    return (
        <section id="get-started" className="relative overflow-hidden bg-gray-950 py-20 sm:py-28">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(34,211,238,0.18),transparent_34rem)]" />
            <Container className="relative">
                <div className="mx-auto max-w-4xl overflow-hidden rounded-[2rem] border border-white/10 bg-white/[0.04] p-8 shadow-2xl shadow-cyan-950/30 backdrop-blur sm:p-12 lg:p-14">
                    <div className="grid gap-10 lg:grid-cols-[1.2fr_0.8fr] lg:items-center">
                        <div>
                            <div className="inline-flex rounded-full bg-cyan-300/10 px-4 py-2 text-sm font-medium text-cyan-200 ring-1 ring-cyan-300/20">
                                Build with the agent runtime now
                            </div>
                            <h2 className="mt-6 text-3xl font-bold tracking-tight text-white sm:text-5xl">
                                Start with one objective. End with reviewed, tested work.
                            </h2>
                            <p className="mt-5 text-lg leading-8 text-gray-300">
                                Use CodeTether locally, self-host it, or connect it to the cloud control plane as it rolls out.
                                The runtime is already capable; the API surface is becoming the system of record.
                            </p>
                            <div className="mt-8 flex flex-col gap-4 sm:flex-row">
                                <Button href="/register" color="cyan" className="px-8 py-3 text-base">
                                    Start building free
                                </Button>
                                <Button
                                    href="https://github.com/rileyseaburg/codetether"
                                    variant="outline"
                                    className="px-8 py-3 text-base text-gray-200"
                                >
                                    View on GitHub
                                </Button>
                            </div>
                        </div>
                        <div className="rounded-3xl border border-white/10 bg-gray-950/70 p-5">
                            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-cyan-200/80">What you get</p>
                            <ul className="mt-5 space-y-4">
                                {outcomes.map((outcome) => (
                                    <li key={outcome} className="flex gap-3 text-sm text-gray-300">
                                        <span className="mt-1 h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_16px_rgba(103,232,249,0.8)]" />
                                        <span>{outcome}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </div>
                </div>
            </Container>
        </section>
    )
}
