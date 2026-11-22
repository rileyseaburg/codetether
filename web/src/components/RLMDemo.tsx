'use client'

import { useState, useEffect, useRef } from 'react'
import { Container } from '@/components/Container'

interface RLMStep {
    id: string
    type: 'load' | 'code' | 'output' | 'subcall' | 'result' | 'stitch'
    content: string
    status: 'pending' | 'running' | 'completed'
    duration?: number
}

const demoScenario = {
    title: "Analyze 12,847 customer records and find top revenue drivers",
    inputTokens: 847293,
    steps: [
        {
            id: '1',
            type: 'load' as const,
            content: 'Loading input as environment variable: input_var (847,293 tokens)',
            duration: 1.2,
        },
        {
            id: '2',
            type: 'code' as const,
            content: `# Peek at input structure
lines = input_var.split('\\n')
print(f"Total rows: {len(lines)}")
print(f"Headers: {lines[0]}")
print(f"Sample: {lines[1:3]}")`,
            duration: 0.3,
        },
        {
            id: '3',
            type: 'output' as const,
            content: `Total rows: 12847
Headers: Customer_ID,Revenue,Region,Product,Date
Sample: ['1001,45000,NA,Enterprise,2024-01', '1002,12000,EU,SMB,2024-01']`,
            duration: 0.1,
        },
        {
            id: '4',
            type: 'code' as const,
            content: `# Chunk for parallel processing
chunk_size = 1000
chunks = [lines[i:i+chunk_size] for i in range(1, len(lines), chunk_size)]
print(f"Created {len(chunks)} chunks for analysis")`,
            duration: 0.4,
        },
        {
            id: '5',
            type: 'output' as const,
            content: `Created 13 chunks for analysis`,
            duration: 0.1,
        },
        {
            id: '6',
            type: 'subcall' as const,
            content: `Sub-LM call 1/13: "Analyze chunk and extract top 10 by revenue"`,
            duration: 2.1,
        },
        {
            id: '7',
            type: 'subcall' as const,
            content: `Sub-LM call 2/13: "Analyze chunk and extract top 10 by revenue"`,
            duration: 1.8,
        },
        {
            id: '8',
            type: 'subcall' as const,
            content: `Sub-LM call 3/13: "Analyze chunk and extract top 10 by revenue"`,
            duration: 2.3,
        },
        {
            id: '9',
            type: 'code' as const,
            content: `# Aggregate results from sub-calls
all_top = chunk_1_results + chunk_2_results + chunk_3_results + ...
sorted_top = sorted(all_top, key=lambda x: x['revenue'], reverse=True)[:50]
print(f"Found {len(sorted_top)} high-value customers")`,
            duration: 0.5,
        },
        {
            id: '10',
            type: 'output' as const,
            content: `Found 50 high-value customers across all regions`,
            duration: 0.1,
        },
        {
            id: '11',
            type: 'subcall' as const,
            content: `Sub-LM verification: "Verify top 10 calculations are correct"`,
            duration: 1.5,
        },
        {
            id: '12',
            type: 'stitch' as const,
            content: `# Generate final CSV output
output_csv = "Rank,Customer_ID,Revenue,Region,Product\\n"
for i, customer in enumerate(sorted_top[:10], 1):
    output_csv += f"{i},{customer['id']},{customer['revenue']},{customer['region']},{customer['product']}\\n"
result_file = output_csv  # 10 rows, verified`,
            duration: 0.8,
        },
        {
            id: '13',
            type: 'result' as const,
            content: `top_customers.csv ready (10 rows)
Emailing to user with summary report...`,
            duration: 0.3,
        },
    ],
}

export function RLMDemo() {
    const [isRunning, setIsRunning] = useState(false)
    const [currentStep, setCurrentStep] = useState(0)
    const [completedSteps, setCompletedSteps] = useState<RLMStep[]>([])
    const [stats, setStats] = useState({ chunks: 0, subcalls: 0, tokens: 0 })
    const scrollRef = useRef<HTMLDivElement>(null)

    const runDemo = () => {
        setIsRunning(true)
        setCurrentStep(0)
        setCompletedSteps([])
        setStats({ chunks: 0, subcalls: 0, tokens: 0 })
    }

    const resetDemo = () => {
        setIsRunning(false)
        setCurrentStep(0)
        setCompletedSteps([])
        setStats({ chunks: 0, subcalls: 0, tokens: 0 })
    }

    useEffect(() => {
        if (!isRunning) return
        if (currentStep >= demoScenario.steps.length) {
            setIsRunning(false)
            return
        }

        const step = demoScenario.steps[currentStep]
        const delay = (step.duration || 0.5) * 1000

        const timer = setTimeout(() => {
            setCompletedSteps(prev => [...prev, { ...step, status: 'completed' }])
            
            // Update stats
            if (step.type === 'load') {
                setStats(s => ({ ...s, tokens: demoScenario.inputTokens }))
            }
            if (step.type === 'subcall') {
                setStats(s => ({ ...s, subcalls: s.subcalls + 1 }))
            }
            if (step.content.includes('chunks')) {
                setStats(s => ({ ...s, chunks: 13 }))
            }
            
            setCurrentStep(prev => prev + 1)
        }, delay)

        return () => clearTimeout(timer)
    }, [isRunning, currentStep])

    // Auto-scroll
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
    }, [completedSteps])

    const typeConfig: Record<string, { icon: string; label: string; color: string }> = {
        load: { icon: '📥', label: 'Load', color: 'border-blue-500/50 bg-blue-950/50' },
        code: { icon: '💻', label: 'Code', color: 'border-green-500/50 bg-green-950/50' },
        output: { icon: '📤', label: 'Output', color: 'border-gray-500/50 bg-gray-800/50' },
        subcall: { icon: '🔄', label: 'Sub-call', color: 'border-cyan-500/50 bg-cyan-950/50' },
        stitch: { icon: '🧵', label: 'Stitch', color: 'border-cyan-500/50 bg-cyan-950/50' },
        result: { icon: '✅', label: 'Result', color: 'border-emerald-500/50 bg-emerald-950/50' },
    }

    return (
        <section id="demo" className="py-20 sm:py-28 bg-gray-900">
            <Container>
                <div className="mx-auto max-w-4xl">
                    {/* Header */}
                    <div className="text-center mb-12">
                        <span className="inline-flex items-center rounded-full bg-cyan-950 px-4 py-1.5 text-sm font-medium text-cyan-400 ring-1 ring-inset ring-cyan-500/20 mb-4">
                            Live Demo
                        </span>
                        <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
                            Watch RLM in Action
                        </h2>
                        <p className="mt-4 text-lg text-gray-400">
                            See how CodeTether processes 847K tokens using recursive decomposition
                        </p>
                    </div>

                    {/* Demo Terminal */}
                    <div className="rounded-2xl bg-gray-950 border border-gray-800 overflow-hidden shadow-2xl">
                        {/* Terminal Header */}
                        <div className="flex items-center justify-between px-4 py-3 bg-gray-900 border-b border-gray-800">
                            <div className="flex items-center gap-2">
                                <div className="flex gap-1.5">
                                    <div className="h-3 w-3 rounded-full bg-red-500" />
                                    <div className="h-3 w-3 rounded-full bg-yellow-500" />
                                    <div className="h-3 w-3 rounded-full bg-green-500" />
                                </div>
                                <span className="ml-3 text-sm text-gray-400 font-mono">RLM Execution</span>
                            </div>
                            <div className="flex items-center gap-3">
                                {isRunning && (
                                    <div className="flex items-center gap-2 text-xs text-cyan-400">
                                        <div className="h-2 w-2 rounded-full bg-cyan-500 animate-pulse" />
                                        Processing...
                                    </div>
                                )}
                                {!isRunning && completedSteps.length === 0 && (
                                    <button
                                        onClick={runDemo}
                                        className="px-4 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-medium rounded-lg transition-colors"
                                    >
                                        Run Demo
                                    </button>
                                )}
                                {!isRunning && completedSteps.length > 0 && (
                                    <button
                                        onClick={resetDemo}
                                        className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg transition-colors"
                                    >
                                        Reset
                                    </button>
                                )}
                            </div>
                        </div>

                        {/* Task Description */}
                        <div className="px-4 py-3 bg-gray-900/50 border-b border-gray-800">
                            <p className="text-sm text-gray-300">
                                <span className="text-gray-500">Task:</span> {demoScenario.title}
                            </p>
                        </div>

                        {/* Stats Bar */}
                        <div className="flex items-center gap-6 px-4 py-2 bg-gray-900/30 border-b border-gray-800 text-xs font-mono">
                            <div>
                                <span className="text-gray-500">Tokens: </span>
                                <span className="text-cyan-400">{stats.tokens.toLocaleString()}</span>
                            </div>
                            <div>
                                <span className="text-gray-500">Chunks: </span>
                                <span className="text-cyan-400">{stats.chunks}</span>
                            </div>
                            <div>
                                <span className="text-gray-500">Sub-calls: </span>
                                <span className="text-cyan-400">{stats.subcalls}/13</span>
                            </div>
                        </div>

                        {/* Execution Steps */}
                        <div ref={scrollRef} className="h-80 overflow-y-auto p-4 space-y-3">
                            {completedSteps.length === 0 && !isRunning && (
                                <div className="flex items-center justify-center h-full text-gray-500 text-sm">
                                    Click "Run Demo" to see RLM process 847K tokens
                                </div>
                            )}

                            {completedSteps.map((step) => {
                                const config = typeConfig[step.type]
                                return (
                                    <div
                                        key={step.id}
                                        className={`rounded-lg border ${config.color} p-3 animate-fadeIn`}
                                    >
                                        <div className="flex items-center justify-between mb-2">
                                            <div className="flex items-center gap-2 text-xs">
                                                <span>{config.icon}</span>
                                                <span className="font-medium text-gray-300">{config.label}</span>
                                            </div>
                                            {step.duration && (
                                                <span className="text-[10px] text-gray-500">{step.duration}s</span>
                                            )}
                                        </div>
                                        <pre className="text-xs font-mono text-gray-300 whitespace-pre-wrap break-words">
                                            {step.content}
                                        </pre>
                                    </div>
                                )
                            })}

                            {isRunning && currentStep < demoScenario.steps.length && (
                                <div className="flex items-center gap-2 text-xs text-gray-500 py-2">
                                    <div className="flex gap-1">
                                        <span className="h-1.5 w-1.5 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                                        <span className="h-1.5 w-1.5 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                                        <span className="h-1.5 w-1.5 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                                    </div>
                                    <span>Executing...</span>
                                </div>
                            )}

                            {!isRunning && completedSteps.length === demoScenario.steps.length && (
                                <div className="rounded-lg border border-emerald-500/50 bg-emerald-950/50 p-4 text-center">
                                    <p className="text-emerald-400 font-medium">Task Complete!</p>
                                    <p className="text-sm text-gray-400 mt-1">
                                        Processed 847,293 tokens in 13 chunks with 4 sub-LM calls
                                    </p>
                                    <p className="text-xs text-gray-500 mt-2">
                                        Output: top_customers.csv sent via email
                                    </p>
                                </div>
                            )}
                        </div>

                        {/* Footer */}
                        <div className="px-4 py-3 bg-gray-900 border-t border-gray-800 flex items-center justify-between">
                            <a
                                href="https://arxiv.org/html/2512.24601v1"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                            >
                                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                    <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z" />
                                    <path fillRule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clipRule="evenodd" />
                                </svg>
                                Read the RLM Paper
                            </a>
                            <span className="text-xs text-gray-500">
                                Powered by MIT Research
                            </span>
                        </div>
                    </div>

                    {/* CTA */}
                    <div className="mt-8 text-center">
                        <a
                            href="/register"
                            className="inline-flex items-center gap-2 rounded-lg bg-cyan-600 px-6 py-3 text-sm font-semibold text-white hover:bg-cyan-500 transition-colors"
                        >
                            Try It Yourself - Free
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                            </svg>
                        </a>
                    </div>
                </div>
            </Container>
        </section>
    )
}
