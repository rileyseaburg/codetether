'use client'

import { Container } from '@/components/Container'

export function RLMExplainer() {
    return (
        <section
            id="rlm"
            aria-label="What is RLM"
            className="py-20 sm:py-28 bg-gray-950"
        >
            <Container>
                {/* Header */}
                <div className="mx-auto max-w-3xl text-center">
                    <span className="inline-flex items-center rounded-full bg-cyan-950 px-4 py-1.5 text-sm font-medium text-cyan-400 ring-1 ring-inset ring-cyan-500/20 mb-6">
                        Powered by MIT Research
                    </span>
                    <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
                        Unlimited Context. Real Outputs. Reliable Automation.
                    </h2>
                    <p className="mt-4 text-lg text-gray-400">
                        Most AI degrades as context grows. RLM processes large inputs recursively—breaking work into chunks, verifying results, and producing deliverables.
                    </p>
                </div>

                {/* The Problem & Solution */}
                <div className="mt-16 grid md:grid-cols-2 gap-8">
                    {/* Problem */}
                    <div className="rounded-2xl bg-gray-900 border border-gray-800 p-8">
                        <h3 className="text-xl font-semibold text-white mb-4">The Problem: Context Limits</h3>
                        <div className="bg-gray-800 rounded-lg p-4">
                            <div className="text-sm text-gray-400 mb-3">Base models hit context limits on 6–11M token tasks.</div>
                            <div className="text-sm text-gray-400">RLM completes them with 91.33% accuracy (MIT CSAIL).</div>
                        </div>
                    </div>

                    {/* Solution */}
                    <div className="rounded-2xl bg-cyan-950/30 border border-cyan-900 p-8">
                        <h3 className="text-xl font-semibold text-white mb-4">The Solution: RLM</h3>
                        <p className="text-gray-300 mb-4">
                            RLM treats input as an <span className="text-cyan-400 font-medium">environment variable</span>, not
                            direct context. The AI writes code to peek, decompose, and recursively call itself on chunks.
                        </p>
                        <div className="bg-gray-900 rounded-lg p-4">
                            <div className="text-sm text-gray-500 mb-2">RLM(GPT-5) on same tasks:</div>
                            <div className="text-3xl font-bold text-cyan-400">91.33% accuracy</div>
                            <div className="text-sm text-gray-500 mt-1">From failing to solved</div>
                        </div>
                    </div>
                </div>

                {/* How It Works */}
                <div className="mt-16">
                    <h3 className="text-xl font-semibold text-white text-center mb-8">How RLM Works</h3>
                    <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
                        <div className="text-center">
                            <div className="mx-auto h-12 w-12 rounded-full bg-cyan-500/20 flex items-center justify-center mb-4">
                                <span className="text-cyan-400 font-bold">1</span>
                            </div>
                            <h4 className="font-medium text-white mb-2">Load as Variable</h4>
                            <p className="text-sm text-gray-400">
                                Your data becomes a variable in a Python REPL, not direct LLM input
                            </p>
                        </div>
                        <div className="text-center">
                            <div className="mx-auto h-12 w-12 rounded-full bg-cyan-500/20 flex items-center justify-center mb-4">
                                <span className="text-cyan-400 font-bold">2</span>
                            </div>
                            <h4 className="font-medium text-white mb-2">Decompose</h4>
                            <p className="text-sm text-gray-400">
                                AI writes code to chunk, filter, and navigate your data programmatically
                            </p>
                        </div>
                        <div className="text-center">
                            <div className="mx-auto h-12 w-12 rounded-full bg-cyan-500/20 flex items-center justify-center mb-4">
                                <span className="text-cyan-400 font-bold">3</span>
                            </div>
                            <h4 className="font-medium text-white mb-2">Recursive Calls</h4>
                            <p className="text-sm text-gray-400">
                                Sub-LLMs process chunks, verify results, and report back
                            </p>
                        </div>
                        <div className="text-center">
                            <div className="mx-auto h-12 w-12 rounded-full bg-cyan-500/20 flex items-center justify-center mb-4">
                                <span className="text-cyan-400 font-bold">4</span>
                            </div>
                            <h4 className="font-medium text-white mb-2">Stitch Output</h4>
                            <p className="text-sm text-gray-400">
                                Results combined into real files: CSV, PDF, code, reports
                            </p>
                        </div>
                    </div>
                </div>

                {/* Key Stats */}
                <div className="mt-16 rounded-2xl bg-gray-900 border border-gray-800 p-8">
                    <div className="grid sm:grid-cols-3 gap-8 text-center">
                        <div>
                            <div className="text-4xl font-bold text-cyan-400">10M+</div>
                            <div className="text-sm text-gray-400 mt-1">tokens processed</div>
                            <div className="text-xs text-gray-500 mt-1">100x beyond normal LLMs</div>
                        </div>
                        <div>
                            <div className="text-4xl font-bold text-cyan-400">91%</div>
                            <div className="text-sm text-gray-400 mt-1">accuracy on huge tasks</div>
                            <div className="text-xs text-gray-500 mt-1">vs context-limited base models</div>
                        </div>
                        <div>
                            <div className="text-4xl font-bold text-cyan-400">3x</div>
                            <div className="text-sm text-gray-400 mt-1">cheaper than alternatives</div>
                            <div className="text-xs text-gray-500 mt-1">median cost lower than base model</div>
                        </div>
                    </div>
                </div>

                {/* Paper Link */}
                <div className="mt-12 text-center">
                    <p className="text-gray-400 mb-4">
                        RLM is based on peer-reviewed research from MIT CSAIL.
                    </p>
                    <a
                        href="https://arxiv.org/html/2512.24601v1"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 rounded-full bg-gray-800 px-6 py-3 text-sm font-medium text-white hover:bg-gray-700 transition-colors"
                    >
                        <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6zm-1 2l5 5h-5V4zm-3 9h4v2h-4v-2zm0 4h4v2h-4v-2zM8 9h2v2H8V9zm0 4h2v2H8v-2zm0 4h2v2H8v-2z" />
                        </svg>
                        Read the Paper: Recursive Language Models
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                        </svg>
                    </a>
                    <p className="mt-4 text-xs text-gray-500">
                        Zhang, Kraska, Khattab. &quot;Recursive Language Models.&quot; MIT CSAIL, 2025.
                    </p>
                </div>
            </Container>
        </section>
    )
}
