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
                    {/* RLM Trust Badge */}
                    <div className="mb-6 inline-flex items-center gap-2 rounded-full bg-gray-800/60 px-4 py-2 text-sm text-gray-300 ring-1 ring-gray-700">
                        <svg className="h-4 w-4 text-cyan-400" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M6.267 3.455a3.066 3.066 0 001.745-.723 3.066 3.066 0 013.976 0 3.066 3.066 0 001.745.723 3.066 3.066 0 012.812 2.812c.051.643.304 1.254.723 1.745a3.066 3.066 0 010 3.976 3.066 3.066 0 00-.723 1.745 3.066 3.066 0 01-2.812 2.812 3.066 3.066 0 00-1.745.723 3.066 3.066 0 01-3.976 0 3.066 3.066 0 00-1.745-.723 3.066 3.066 0 01-2.812-2.812 3.066 3.066 0 00-.723-1.745 3.066 3.066 0 010-3.976 3.066 3.066 0 00.723-1.745 3.066 3.066 0 012.812-2.812zm7.44 5.252a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                        <span>Powered by <span className="text-cyan-400 font-medium">RLM</span> (MIT Research)</span>
                    </div>

                    <h2 className="text-3xl font-medium tracking-tight text-white sm:text-4xl">
                        Stop Babysitting AI.<br />
                        <span className="text-cyan-400">Start Getting Results.</span>
                    </h2>
                    <p className="mt-4 text-lg text-gray-300">
                        Unlimited context. No data limits. Recursive task decomposition
                        that handles complexity you couldn&apos;t before.
                    </p>
                    <p className="mt-2 text-base text-gray-400">
                        Trigger a task. Go do other things. Get files in your inbox.
                    </p>

                    {/* CTA Buttons */}
                    <div className="mt-10 flex flex-col sm:flex-row justify-center gap-4">
                        <Button href="/register" color="cyan" className="text-base px-8 py-3">
                            Start Free - 10 Tasks/Month
                        </Button>
                        <Button 
                            href="#pricing" 
                            variant="outline" 
                            className="text-gray-300 text-base px-8 py-3"
                        >
                            View Pricing
                        </Button>
                    </div>

                    {/* Trust Badges */}
                    <div className="mt-8 flex flex-wrap justify-center gap-4 text-xs text-gray-400">
                        <span className="flex items-center gap-1">
                            <svg className="h-4 w-4 text-cyan-400" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                            No credit card required
                        </span>
                        <span className="flex items-center gap-1">
                            <svg className="h-4 w-4 text-cyan-400" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                            Works with Zapier, n8n, Make
                        </span>
                        <span className="flex items-center gap-1">
                            <svg className="h-4 w-4 text-cyan-400" fill="currentColor" viewBox="0 0 20 20">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                            Cancel anytime
                        </span>
                    </div>
                </div>
            </Container>
        </section>
    )
}
