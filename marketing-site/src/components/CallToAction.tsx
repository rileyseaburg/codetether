'use client'

import { CircleBackground } from '@/components/CircleBackground'
import { Container } from '@/components/Container'
import { Button } from '@/components/Button'

export function CallToAction() {
    return (
        <section
            id="get-started"
            className="relative overflow-hidden bg-gray-900 py-20 sm:py-28"
        >
            <div className="absolute top-1/2 left-20 -translate-y-1/2 sm:left-1/2 sm:-translate-x-1/2">
                <CircleBackground color="#06B6D4" className="animate-spin-slower" />
            </div>
            <Container className="relative">
                <div className="mx-auto max-w-2xl sm:text-center">
                    {/* Security Badge */}
                    <div className="mb-6 inline-flex items-center gap-2 rounded-full bg-gray-800/60 px-4 py-2 text-sm text-gray-300 ring-1 ring-gray-700">
                        <svg className="h-4 w-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
                        </svg>
                        <span><span className="text-cyan-400 font-medium">Rust</span> · <span className="text-cyan-400 font-medium">K8s</span> · <span className="text-cyan-400 font-medium">Mandatory Auth</span></span>
                    </div>

                    <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
                        Your Infrastructure Deserves Better<br />
                        <span className="text-cyan-400">Than an Agent That Shipped with No Auth.</span>
                    </h2>
                    <p className="mt-4 text-lg text-gray-300">
                        Deploy CodeTether on your own terms. Read the code. Audit the architecture. Own your data.
                    </p>

                    {/* CTA Buttons */}
                    <div className="mt-10 flex flex-col sm:flex-row justify-center gap-4">
                        <Button href="/register" color="cyan" className="text-base px-8 py-3">
                            Deploy CodeTether Free
                        </Button>
                        <Button
                            href="https://github.com/rileyseaburg/codetether"
                            variant="outline"
                            className="text-gray-300 text-base px-8 py-3"
                        >
                            Star on GitHub
                        </Button>
                    </div>

                    {/* Trust Badges */}
                    <div className="mt-8 flex flex-wrap justify-center gap-4 text-xs text-gray-400">
                        <span className="flex items-center gap-1">
                            <svg className="h-4 w-4 text-cyan-400" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                            Open source — MIT License
                        </span>
                        <span className="flex items-center gap-1">
                            <svg className="h-4 w-4 text-cyan-400" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                            Self-host on your infrastructure
                        </span>
                        <span className="flex items-center gap-1">
                            <svg className="h-4 w-4 text-cyan-400" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                            Every action audit-logged
                        </span>
                    </div>
                </div>
            </Container>
        </section>
    )
}
