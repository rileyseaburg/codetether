'use client'

import { Container } from '@/components/Container'
import { Button } from '@/components/Button'

function CheckIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
    )
}

function XIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
    )
}

const comparisonData = [
    {
        feature: 'Execution Location',
        copilot: 'Runs inside IDE process',
        codetether: 'Runs on backend servers',
        salesAngle: 'Stop lagging your VDIs',
    },
    {
        feature: 'Task Duration',
        copilot: 'Seconds (autocomplete/chat)',
        codetether: 'Hours (background jobs)',
        salesAngle: 'Work while you sleep',
    },
    {
        feature: 'Data Flow',
        copilot: 'Egress to Azure/OpenAI',
        codetether: 'Local execution in your VPC',
        salesAngle: 'Keep the code local',
    },
    {
        feature: 'Customization',
        copilot: 'Zero (it\'s a product)',
        codetether: 'Infinite (it\'s a platform)',
        salesAngle: 'Build YOUR bank\'s agent',
    },
    {
        feature: 'Session Persistence',
        copilot: 'Forgets after 10 minutes',
        codetether: 'Persistent session history',
        salesAngle: 'Context that lasts',
    },
    {
        feature: 'Background Tasks',
        copilot: 'Stops when IDE closes',
        codetether: 'Fire and forget',
        salesAngle: 'Deploy at 5pm, done by 9am',
    },
]

const wedges = [
    {
        title: 'The VDI Resource Problem',
        icon: '💻',
        problem: 'VDI instances are under-provisioned (2 vCPUs, 8GB RAM). Autonomous agents burn massive CPU and memory—your VDI will lag, freeze, or crash.',
        solution: 'Run the heavy lift on robust backend servers via CodeTether workers. Stream only the text output to the VDI. Power without killing the desktop.',
    },
    {
        title: 'The Background vs Foreground Problem',
        icon: '🌙',
        problem: 'Copilot requires the IDE to be open and the user present. Close the VDI at 5:00 PM, Copilot stops working.',
        solution: '"Fire and Forget." Developer says "Refactor this auth module," closes laptop, goes home. CodeTether keeps working all night. Job done by morning.',
    },
    {
        title: 'The Black Box Problem',
        icon: '🔐',
        problem: 'Copilot is a black box. You can\'t customize prompts, inject compliance rules, or chain it with other tools (Jira → Code → Test).',
        solution: 'You own the orchestration layer. Build a Compliance Agent, a COBOL Migration Agent, or any custom workflow. You own the brain.',
    },
]

export function CopilotComparison() {
    return (
        <section
            id="copilot-comparison"
            aria-label="Copilot comparison"
            className="py-20 sm:py-32 bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-950"
        >
            <Container>
                {/* Header */}
                <div className="mx-auto max-w-3xl text-center">
                    <span className="inline-flex items-center rounded-full bg-cyan-100 dark:bg-cyan-900/30 px-4 py-1 text-sm font-medium text-cyan-700 dark:text-cyan-400 mb-4">
                        Already have GitHub Copilot?
                    </span>
                    <h2 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-4xl">
                        Copilot is a Plugin.<br />
                        <span className="text-cyan-600 dark:text-cyan-400">CodeTether is a Workforce.</span>
                    </h2>
                    <p className="mt-4 text-lg text-gray-600 dark:text-gray-300">
                        Copilot helps you type faster. CodeTether runs 20-minute background jobs while your developers sleep.
                        <span className="font-semibold text-gray-900 dark:text-white"> We make your Copilot license 10x more valuable.</span>
                    </p>
                </div>

                {/* The Better Together Architecture */}
                <div className="mt-16 rounded-3xl bg-gray-900 dark:bg-gray-800 p-4 sm:p-8 lg:p-12 overflow-hidden">
                    <div className="grid lg:grid-cols-2 gap-8 lg:gap-12 items-center">
                        <div>
                            <h3 className="text-2xl font-bold text-white">
                                The &quot;Better Together&quot; Architecture
                            </h3>
                            <p className="mt-4 text-gray-300">
                                Because CodeTether is an <span className="text-cyan-400 font-semibold">MCP Server</span>,
                                Copilot can call your agents like API tools. Developers stay in VS Code while
                                heavy work runs on your secure backend.
                            </p>
                            <div className="mt-6 space-y-4">
                                <div className="flex items-start gap-3">
                                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-cyan-500 text-white text-xs font-bold">1</div>
                                    <p className="text-gray-300"><span className="text-white font-medium">Developer in Copilot:</span> &quot;Refactor this auth module to use the new standard.&quot;</p>
                                </div>
                                <div className="flex items-start gap-3">
                                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-cyan-500 text-white text-xs font-bold">2</div>
                                    <p className="text-gray-300"><span className="text-white font-medium">Copilot calls MCP:</span> <code className="bg-gray-800 px-2 py-0.5 rounded text-cyan-400">codetether.spawn_agent(task=&quot;refactor&quot;)</code></p>
                                </div>
                                <div className="flex items-start gap-3">
                                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-cyan-500 text-white text-xs font-bold">3</div>
                                    <p className="text-gray-300"><span className="text-white font-medium">CodeTether Worker:</span> Runs refactor, runs tests, fixes bugs (20 mins)</p>
                                </div>
                                <div className="flex items-start gap-3">
                                    <div className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-white text-xs font-bold">✓</div>
                                    <p className="text-gray-300"><span className="text-white font-medium">Copilot receives:</span> &quot;Job done. Here is the PR link.&quot;</p>
                                </div>
                            </div>
                        </div>
                        <div className="relative overflow-hidden">
                            {/* Architecture Diagram */}
                            <div className="rounded-2xl bg-gray-950 p-4 sm:p-6 ring-1 ring-white/10">
                                <div className="space-y-4">
                                    {/* VS Code / Copilot Box */}
                                    <div className="rounded-xl bg-blue-900/30 border border-blue-500/30 p-3 sm:p-4">
                                        <div className="flex flex-wrap items-center gap-2 mb-3">
                                            <span className="text-xl sm:text-2xl">💻</span>
                                            <span className="font-semibold text-blue-400 text-sm sm:text-base">VS Code + Copilot</span>
                                            <span className="text-xs text-blue-400/60 sm:ml-auto">Developer VDI</span>
                                        </div>
                                        <p className="text-xs sm:text-sm text-gray-400">Lightweight interface. Quick autocomplete. Chat.</p>
                                    </div>

                                    {/* Arrow */}
                                    <div className="flex justify-center">
                                        <div className="flex flex-col items-center">
                                            <span className="text-xs text-cyan-400 font-medium">MCP Protocol</span>
                                            <svg className="h-8 w-8 text-cyan-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                                            </svg>
                                        </div>
                                    </div>

                                    {/* CodeTether Box */}
                                    <div className="rounded-xl bg-cyan-900/30 border border-cyan-500/30 p-3 sm:p-4">
                                        <div className="flex flex-wrap items-center gap-2 mb-3">
                                            <span className="text-xl sm:text-2xl">⚡</span>
                                            <span className="font-semibold text-cyan-400 text-sm sm:text-base">CodeTether Workers</span>
                                            <span className="text-xs text-cyan-400/60 sm:ml-auto">Your Secure VPC</span>
                                        </div>
                                        <div className="grid grid-cols-3 gap-1 sm:gap-2 mt-2">
                                            <div className="rounded bg-gray-800 p-1.5 sm:p-2 text-center">
                                                <div className="text-base sm:text-lg">🔧</div>
                                                <div className="text-[10px] sm:text-xs text-gray-400">Refactor</div>
                                            </div>
                                            <div className="rounded bg-gray-800 p-1.5 sm:p-2 text-center">
                                                <div className="text-base sm:text-lg">🧪</div>
                                                <div className="text-[10px] sm:text-xs text-gray-400">Test</div>
                                            </div>
                                            <div className="rounded bg-gray-800 p-1.5 sm:p-2 text-center">
                                                <div className="text-base sm:text-lg">📊</div>
                                                <div className="text-[10px] sm:text-xs text-gray-400">Analyze</div>
                                            </div>
                                        </div>
                                        <p className="text-xs sm:text-sm text-gray-400 mt-3">Heavy compute. Long-running. Data stays local.</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* The 3 Wedges */}
                <div className="mt-16">
                    <h3 className="text-center text-xl font-semibold text-gray-900 dark:text-white mb-8">
                        Why Copilot Alone Fails at Agent Workflows
                    </h3>
                    <div className="grid md:grid-cols-3 gap-6">
                        {wedges.map((wedge) => (
                            <div
                                key={wedge.title}
                                className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 hover:border-cyan-500 dark:hover:border-cyan-500 transition-colors"
                            >
                                <div className="text-3xl mb-4">{wedge.icon}</div>
                                <h4 className="font-semibold text-gray-900 dark:text-white">{wedge.title}</h4>
                                <div className="mt-4 space-y-3">
                                    <div className="flex items-start gap-2">
                                        <XIcon className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                                        <p className="text-sm text-gray-600 dark:text-gray-400">{wedge.problem}</p>
                                    </div>
                                    <div className="flex items-start gap-2">
                                        <CheckIcon className="h-5 w-5 text-emerald-500 flex-shrink-0 mt-0.5" />
                                        <p className="text-sm text-gray-700 dark:text-gray-300">{wedge.solution}</p>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Comparison Table */}
                <div className="mt-16 overflow-hidden rounded-2xl border border-gray-200 dark:border-gray-800">
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="bg-gray-50 dark:bg-gray-900">
                                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">Feature</th>
                                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">GitHub Copilot</th>
                                    <th className="px-6 py-4 text-left text-sm font-semibold text-cyan-600 dark:text-cyan-400">CodeTether</th>
                                    <th className="px-6 py-4 text-left text-sm font-semibold text-gray-900 dark:text-white">The Win</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200 dark:divide-gray-800 bg-white dark:bg-gray-950">
                                {comparisonData.map((row) => (
                                    <tr key={row.feature}>
                                        <td className="px-6 py-4 text-sm font-medium text-gray-900 dark:text-white">{row.feature}</td>
                                        <td className="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">{row.copilot}</td>
                                        <td className="px-6 py-4 text-sm text-gray-900 dark:text-gray-200 font-medium">{row.codetether}</td>
                                        <td className="px-6 py-4 text-sm text-cyan-600 dark:text-cyan-400 font-medium">{row.salesAngle}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>

                {/* Bottom CTA */}
                <div className="mt-12 text-center">
                    <p className="text-lg text-gray-600 dark:text-gray-300 max-w-2xl mx-auto mb-6">
                        <span className="font-semibold text-gray-900 dark:text-white">Keep Copilot!</span> It&apos;s great for autocomplete.
                        Use CodeTether for the heavy lifting—migration tasks, test generation, and complex refactors that take hours to run.
                        <span className="text-cyan-600 dark:text-cyan-400 font-medium"> Copilot helps you write. CodeTether helps you build.</span>
                    </p>
                    <div className="flex flex-wrap justify-center gap-4">
                        <Button href="#features" color="cyan">
                            See the Architecture
                        </Button>
                        <Button href="#contact" variant="outline">
                            Request Demo
                        </Button>
                    </div>
                </div>
            </Container>
        </section>
    )
}
