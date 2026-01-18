'use client'

import { Container } from '@/components/Container'

function InfinityIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#8B5CF6" fillOpacity={0.2} />
            <path
                d="M8 16c0-2.2 1.8-4 4-4s4 1.8 4 4-1.8 4-4 4-4-1.8-4-4zm8 0c0-2.2 1.8-4 4-4s4 1.8 4 4-1.8 4-4 4-4-1.8-4-4z"
                stroke="#8B5CF6"
                strokeWidth={2}
                fill="none"
            />
        </svg>
    )
}

function RecursiveIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#8B5CF6" fillOpacity={0.2} />
            <path
                d="M16 8v4m0 8v4M8 16h4m8 0h4"
                stroke="#8B5CF6"
                strokeWidth={2}
                strokeLinecap="round"
            />
            <circle cx={16} cy={16} r={4} fill="#8B5CF6" />
            <path
                d="M12 12l-2-2m10 0l2-2m-10 12l-2 2m10 0l2 2"
                stroke="#8B5CF6"
                strokeWidth={1.5}
                strokeLinecap="round"
            />
        </svg>
    )
}

function CodeIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 32 32" aria-hidden="true" {...props}>
            <circle cx={16} cy={16} r={16} fill="#8B5CF6" fillOpacity={0.2} />
            <path
                d="M12 10l-4 6 4 6M20 10l4 6-4 6M14 22l4-12"
                stroke="#8B5CF6"
                strokeWidth={2}
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    )
}

const features = [
    {
        name: 'Infinite Context Window',
        description:
            'Break free from context limits. RLM treats your entire codebase as an external variable, processing millions of tokens through intelligent chunking and recursive analysis.',
        icon: InfinityIcon,
    },
    {
        name: 'Recursive Sub-LLM Calls',
        description:
            'The AI writes Python code that calls llm_query() recursively. Each subcall gets a fresh context window, enabling deep analysis without context bloat.',
        icon: RecursiveIcon,
    },
    {
        name: 'Python REPL Power',
        description:
            'Full Python environment with regex, comprehensions, and standard library. The AI thinks in code, manipulates data programmatically, and synthesizes insights.',
        icon: CodeIcon,
    },
]

export function RLMFeature() {
    return (
        <section
            id="rlm"
            aria-label="RLM - Recursive Language Models"
            className="relative overflow-hidden bg-gradient-to-b from-purple-950 via-gray-900 to-gray-900 py-20 sm:py-32"
        >
            {/* Background decoration */}
            <div className="absolute inset-0 overflow-hidden">
                <div className="absolute -top-40 -right-40 h-80 w-80 rounded-full bg-purple-500/20 blur-3xl" />
                <div className="absolute -bottom-40 -left-40 h-80 w-80 rounded-full bg-cyan-500/20 blur-3xl" />
            </div>

            <Container className="relative">
                {/* Badge */}
                <div className="flex justify-center">
                    <span className="inline-flex items-center gap-2 rounded-full bg-purple-500/10 px-4 py-2 text-sm font-medium text-purple-400 ring-1 ring-purple-500/20">
                        <span className="relative flex h-2 w-2">
                            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-purple-400 opacity-75" />
                            <span className="relative inline-flex h-2 w-2 rounded-full bg-purple-500" />
                        </span>
                        Revolutionary New Feature
                    </span>
                </div>

                {/* Header */}
                <div className="mx-auto mt-8 max-w-3xl text-center">
                    <h2 className="text-4xl font-bold tracking-tight text-white sm:text-5xl">
                        RLM: <span className="text-purple-400">Recursive Language Models</span>
                    </h2>
                    <p className="mt-6 text-xl text-gray-300">
                        Process <span className="font-semibold text-white">arbitrarily long contexts</span> through recursive LLM calls.
                        Analyze entire monorepos, audit massive codebases, generate documentation at scale—
                        <span className="text-purple-400"> without context window limits</span>.
                    </p>
                </div>

                {/* Code Demo */}
                <div className="mx-auto mt-16 max-w-4xl">
                    <div className="overflow-hidden rounded-2xl bg-gray-900 shadow-2xl ring-1 ring-white/10">
                        <div className="flex items-center gap-2 border-b border-gray-700 px-4 py-3">
                            <div className="h-3 w-3 rounded-full bg-red-500" />
                            <div className="h-3 w-3 rounded-full bg-yellow-500" />
                            <div className="h-3 w-3 rounded-full bg-green-500" />
                            <span className="ml-2 text-sm text-gray-400">RLM Python REPL</span>
                        </div>
                        <pre className="overflow-x-auto p-6 text-sm leading-relaxed">
                            <code className="text-gray-300">
                                <span className="text-gray-500"># Context is pre-loaded from your codebase</span>{'\n'}
                                <span className="text-purple-400">print</span>(<span className="text-green-400">f&quot;Analyzing </span><span className="text-cyan-400">{'{len(context):,}'}</span><span className="text-green-400"> characters...&quot;</span>){'\n\n'}

                                <span className="text-gray-500"># Use Python to chunk and process</span>{'\n'}
                                <span className="text-cyan-400">files</span> = context.<span className="text-purple-400">split</span>(<span className="text-green-400">&quot;--- FILE: &quot;</span>){'\n'}
                                <span className="text-cyan-400">issues</span> = []{'\n\n'}

                                <span className="text-purple-400">for</span> file <span className="text-purple-400">in</span> files[:<span className="text-yellow-400">50</span>]:  <span className="text-gray-500"># Process in batches</span>{'\n'}
                                {'    '}<span className="text-gray-500"># Recursive LLM call with fresh context</span>{'\n'}
                                {'    '}<span className="text-cyan-400">analysis</span> = <span className="text-purple-400">llm_query</span>(<span className="text-green-400">f&quot;&quot;&quot;</span>{'\n'}
                                {'        '}<span className="text-green-400">Find security vulnerabilities in:</span>{'\n'}
                                {'        '}<span className="text-cyan-400">{'{file[:8000]}'}</span>{'\n'}
                                {'    '}<span className="text-green-400">&quot;&quot;&quot;</span>){'\n'}
                                {'    '}<span className="text-purple-400">if</span> <span className="text-green-400">&quot;vulnerability&quot;</span> <span className="text-purple-400">in</span> analysis.<span className="text-purple-400">lower</span>():{'\n'}
                                {'        '}issues.<span className="text-purple-400">append</span>(analysis){'\n\n'}

                                <span className="text-gray-500"># Return final synthesized result</span>{'\n'}
                                <span className="text-cyan-400">summary</span> = <span className="text-purple-400">llm_query</span>(<span className="text-green-400">f&quot;Summarize these </span><span className="text-cyan-400">{'{len(issues)}'}</span><span className="text-green-400"> issues: </span><span className="text-cyan-400">{'{issues}'}</span><span className="text-green-400">&quot;</span>){'\n'}
                                <span className="text-purple-400">FINAL</span>(summary)
                            </code>
                        </pre>
                    </div>
                </div>

                {/* Feature Grid */}
                <ul
                    role="list"
                    className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-8 sm:grid-cols-3 lg:max-w-none"
                >
                    {features.map((feature) => (
                        <li
                            key={feature.name}
                            className="rounded-2xl border border-purple-500/20 bg-gray-900/50 p-8 backdrop-blur transition-all hover:border-purple-500/40 hover:bg-gray-900/80"
                        >
                            <feature.icon className="h-10 w-10" />
                            <h3 className="mt-6 text-lg font-semibold text-white">
                                {feature.name}
                            </h3>
                            <p className="mt-2 text-sm text-gray-400">{feature.description}</p>
                        </li>
                    ))}
                </ul>

                {/* Use Cases */}
                <div className="mx-auto mt-16 max-w-4xl">
                    <h3 className="text-center text-xl font-semibold text-white">
                        Use Cases That Were Impossible Before
                    </h3>
                    <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                        {[
                            { emoji: '🔍', title: 'Monorepo Audits', desc: 'Security scan 500+ files' },
                            { emoji: '📚', title: 'Doc Generation', desc: 'API docs from 100k lines' },
                            { emoji: '🔄', title: 'Mass Refactoring', desc: 'Coordinate cross-file changes' },
                            { emoji: '🏗️', title: 'Architecture Review', desc: 'Map entire system dependencies' },
                        ].map((item) => (
                            <div
                                key={item.title}
                                className="rounded-xl bg-gray-800/50 p-4 text-center"
                            >
                                <span className="text-3xl">{item.emoji}</span>
                                <h4 className="mt-2 font-medium text-white">{item.title}</h4>
                                <p className="mt-1 text-xs text-gray-400">{item.desc}</p>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Stats */}
                <div className="mx-auto mt-16 grid max-w-4xl grid-cols-2 gap-8 sm:grid-cols-4">
                    {[
                        { value: '∞', label: 'Context Size' },
                        { value: '100+', label: 'Subcalls/Session' },
                        { value: '<30s', label: 'Avg Analysis Time' },
                        { value: '0', label: 'Data Leaves VPC' },
                    ].map((stat) => (
                        <div key={stat.label} className="text-center">
                            <p className="text-4xl font-bold text-purple-400">{stat.value}</p>
                            <p className="mt-2 text-sm text-gray-400">{stat.label}</p>
                        </div>
                    ))}
                </div>
            </Container>
        </section>
    )
}
