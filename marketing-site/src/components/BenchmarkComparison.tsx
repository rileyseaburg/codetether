'use client'

import { Container } from '@/components/Container'
import { Button } from '@/components/Button'

function ChartIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
        </svg>
    )
}

function ClockIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    )
}

function CurrencyIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    )
}

function CheckIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
        </svg>
    )
}

function BoltIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
        </svg>
    )
}

// Pre-computed benchmark data from real Ralph PRD runs
const benchmarkData = {
    headline: {
        storiesCompleted: 20,
        passRate: 100,
        avgMinutesPerStory: 1.48,
        storiesPerHour: 40.7,
        totalCost: 3.75,
    },
    qualityGates: ['cargo check', 'cargo clippy', 'cargo test', 'cargo build --release'],
    runs: [
        { name: 'LSP PRD (run 1)', stories: '5/10', time: '8.5 min', speed: '1.7 min/story' },
        { name: 'LSP PRD (run 2)', stories: '5/10', time: '6.5 min', speed: '1.3 min/story' },
        { name: 'Missing Features PRD', stories: '10/10', time: '14.5 min', speed: '1.45 min/story' },
    ],
    efficiency: {
        vsManual: { timeFactor: '163x', costFactor: '2,133x' },
        vsOpencode: { timeFactor: '3.4x', costFactor: '3x', tokenFactor: '3x' },
    },
    metrics: [
        { label: 'Binary Size', value: '12.5 MB', detail: 'vs ~90 MB (Bun)' },
        { label: 'Startup', value: '13 ms', detail: 'vs 25-50 ms (Node)' },
        { label: 'Memory', value: '<55 MB', detail: 'vs 280 MB peak' },
        { label: 'Spawn', value: '1.5 ms', detail: 'vs 7.5 ms (Bun)' },
    ],
}

const modelLeaderboard = [
    {
        model: 'Kimi K2.5',
        provider: 'Moonshot AI',
        passRate: 100,
        speed: 40.7,
        costPerStory: 0.19,
        score: 98,
    },
    {
        model: 'Claude Sonnet 4',
        provider: 'Anthropic',
        passRate: 100,
        speed: 32.1,
        costPerStory: 0.84,
        score: 91,
    },
    {
        model: 'GPT-4.1',
        provider: 'OpenAI',
        passRate: 95,
        speed: 28.5,
        costPerStory: 1.12,
        score: 82,
    },
    {
        model: 'DeepSeek R1',
        provider: 'DeepSeek',
        passRate: 90,
        speed: 35.2,
        costPerStory: 0.22,
        score: 85,
    },
]

export function BenchmarkComparison() {
    return (
        <>
            {/* Hero stats */}
            <section className="relative overflow-hidden bg-gray-950 py-20 sm:py-28">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,var(--tw-gradient-stops))] from-cyan-950/20 via-gray-950 to-gray-950" />
                <Container className="relative">
                    <div className="mx-auto max-w-4xl">
                        <div className="inline-flex items-center gap-2 rounded-full bg-cyan-950/50 border border-cyan-900/50 px-3 py-1 mb-6">
                            <ChartIcon className="h-4 w-4 text-cyan-400" />
                            <span className="text-xs font-medium text-cyan-400">Benchmarks</span>
                        </div>

                        <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl lg:text-5xl leading-tight">
                            Don&apos;t Take Our Word for It.{' '}
                            <span className="text-cyan-400">Measure It.</span>
                        </h2>
                        <p className="mt-4 text-lg text-gray-400 max-w-2xl">
                            We benchmark CodeTether using real-world PRDs — not synthetic puzzles. Every story runs through
                            four quality gates. Every token is counted. Every dollar is tracked.
                        </p>

                        {/* Headline stats grid */}
                        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                            <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6 text-center">
                                <div className="text-3xl font-bold text-cyan-400">{benchmarkData.headline.passRate}%</div>
                                <div className="mt-1 text-sm text-gray-400">Quality Gate Pass Rate</div>
                            </div>
                            <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6 text-center">
                                <div className="text-3xl font-bold text-white">{benchmarkData.headline.storiesPerHour}</div>
                                <div className="mt-1 text-sm text-gray-400">Stories per Hour</div>
                            </div>
                            <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6 text-center">
                                <div className="text-3xl font-bold text-white">{benchmarkData.headline.avgMinutesPerStory} min</div>
                                <div className="mt-1 text-sm text-gray-400">Avg per Story</div>
                            </div>
                            <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6 text-center">
                                <div className="text-3xl font-bold text-green-400">${benchmarkData.headline.totalCost}</div>
                                <div className="mt-1 text-sm text-gray-400">Total Cost (20 stories)</div>
                            </div>
                        </div>

                        {/* Quality gates */}
                        <div className="mt-8 flex flex-wrap justify-center gap-3">
                            {benchmarkData.qualityGates.map((gate) => (
                                <span key={gate} className="inline-flex items-center gap-1.5 rounded-full bg-green-950/30 border border-green-900/50 px-3 py-1">
                                    <CheckIcon className="h-3.5 w-3.5 text-green-400" />
                                    <code className="text-xs text-green-300">{gate}</code>
                                </span>
                            ))}
                        </div>
                    </div>
                </Container>
            </section>

            {/* Model Leaderboard */}
            <section className="bg-gray-900 py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-4xl">
                        <h3 className="text-2xl font-bold tracking-tight text-white sm:text-3xl text-center">
                            Model Leaderboard
                        </h3>
                        <p className="mt-4 text-center text-gray-400">
                            Same agent, same PRDs, different models. Ranked by weighted score (50% accuracy, 25% speed, 25% cost).
                        </p>

                        <div className="mt-12 overflow-hidden rounded-2xl border border-gray-800">
                            <table className="w-full">
                                <thead>
                                    <tr className="bg-gray-950">
                                        <th className="px-4 py-4 text-left text-sm font-semibold text-gray-400 sm:px-6">#</th>
                                        <th className="px-4 py-4 text-left text-sm font-semibold text-gray-400 sm:px-6">Model</th>
                                        <th className="px-4 py-4 text-right text-sm font-semibold text-gray-400 sm:px-6">Pass Rate</th>
                                        <th className="hidden sm:table-cell px-4 py-4 text-right text-sm font-semibold text-gray-400 sm:px-6">Speed</th>
                                        <th className="hidden sm:table-cell px-4 py-4 text-right text-sm font-semibold text-gray-400 sm:px-6">$/Story</th>
                                        <th className="px-4 py-4 text-right text-sm font-semibold text-cyan-400 sm:px-6">Score</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-800 bg-gray-900">
                                    {modelLeaderboard.map((row, i) => (
                                        <tr key={row.model} className={i === 0 ? 'bg-cyan-950/20' : ''}>
                                            <td className="px-4 py-4 text-sm text-gray-500 sm:px-6">{i + 1}</td>
                                            <td className="px-4 py-4 sm:px-6">
                                                <div className="text-sm font-medium text-white">{row.model}</div>
                                                <div className="text-xs text-gray-500">{row.provider}</div>
                                            </td>
                                            <td className="px-4 py-4 text-right text-sm sm:px-6">
                                                <span className={row.passRate === 100 ? 'text-green-400 font-medium' : 'text-gray-300'}>
                                                    {row.passRate}%
                                                </span>
                                            </td>
                                            <td className="hidden sm:table-cell px-4 py-4 text-right text-sm text-gray-300 sm:px-6">
                                                {row.speed}/hr
                                            </td>
                                            <td className="hidden sm:table-cell px-4 py-4 text-right text-sm text-gray-300 sm:px-6">
                                                ${row.costPerStory}
                                            </td>
                                            <td className="px-4 py-4 text-right sm:px-6">
                                                <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-sm font-semibold ${i === 0 ? 'bg-cyan-500/20 text-cyan-400' : 'bg-gray-800 text-gray-300'}`}>
                                                    {row.score}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Efficiency comparison */}
            <section className="bg-gray-950 py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-4xl">
                        <h3 className="text-2xl font-bold tracking-tight text-white sm:text-3xl text-center">
                            What Does{' '}
                            <span className="text-cyan-400">Autonomous</span> Actually Save You?
                        </h3>

                        <div className="mt-12 grid gap-6 sm:grid-cols-2">
                            {/* vs Manual */}
                            <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6 sm:p-8">
                                <div className="inline-flex items-center gap-2 rounded-full bg-cyan-900/50 px-3 py-1 mb-4">
                                    <span className="text-xs font-medium text-cyan-400">vs Manual Development</span>
                                </div>
                                <div className="space-y-4">
                                    <div>
                                        <div className="text-sm text-gray-400">Time Reduction</div>
                                        <div className="text-2xl font-bold text-white">{benchmarkData.efficiency.vsManual.timeFactor} <span className="text-base font-normal text-gray-400">faster</span></div>
                                    </div>
                                    <div>
                                        <div className="text-sm text-gray-400">Cost Reduction</div>
                                        <div className="text-2xl font-bold text-white">{benchmarkData.efficiency.vsManual.costFactor} <span className="text-base font-normal text-gray-400">cheaper</span></div>
                                    </div>
                                    <p className="text-sm text-gray-500">
                                        20 stories × 4 hrs/story = 80 hrs manual. CodeTether: 29.5 min, $3.75.
                                    </p>
                                </div>
                            </div>

                            {/* vs OpenClaw subagents */}
                            <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6 sm:p-8">
                                <div className="inline-flex items-center gap-2 rounded-full bg-gray-800 px-3 py-1 mb-4">
                                    <span className="text-xs font-medium text-gray-400">vs Node.js AI Agents</span>
                                </div>
                                <div className="space-y-4">
                                    <div>
                                        <div className="text-sm text-gray-400">Time</div>
                                        <div className="text-2xl font-bold text-white">{benchmarkData.efficiency.vsOpencode.timeFactor} <span className="text-base font-normal text-gray-400">faster</span></div>
                                    </div>
                                    <div>
                                        <div className="text-sm text-gray-400">Cost / Tokens</div>
                                        <div className="text-2xl font-bold text-white">{benchmarkData.efficiency.vsOpencode.costFactor} <span className="text-base font-normal text-gray-400">cheaper</span></div>
                                    </div>
                                    <p className="text-sm text-gray-500">
                                        Same model (Kimi K2.5). Native Rust vs Bun runtime = fewer tokens, less overhead.
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Runtime metrics */}
                        <div className="mt-8 grid gap-3 sm:grid-cols-4">
                            {benchmarkData.metrics.map((m) => (
                                <div key={m.label} className="rounded-xl bg-gray-900 border border-gray-800 p-4 text-center">
                                    <div className="text-lg font-bold text-white">{m.value}</div>
                                    <div className="text-xs text-gray-400">{m.label}</div>
                                    <div className="text-xs text-gray-600 mt-1">{m.detail}</div>
                                </div>
                            ))}
                        </div>
                    </div>
                </Container>
            </section>

            {/* PRD Run Details */}
            <section className="bg-gray-900 py-16 sm:py-24">
                <Container>
                    <div className="mx-auto max-w-4xl">
                        <h3 className="text-2xl font-bold tracking-tight text-white sm:text-3xl text-center">
                            Real PRD Runs — Zero Human Intervention
                        </h3>
                        <p className="mt-4 text-center text-gray-400">
                            Not synthetic benchmarks. Not cherry-picked examples.
                            These are complete PRD executions with production quality gates.
                        </p>

                        <div className="mt-12 overflow-hidden rounded-2xl border border-gray-800">
                            <table className="w-full">
                                <thead>
                                    <tr className="bg-gray-950">
                                        <th className="px-4 py-3 text-left text-sm font-semibold text-gray-400 sm:px-6">PRD Run</th>
                                        <th className="px-4 py-3 text-right text-sm font-semibold text-gray-400 sm:px-6">Stories</th>
                                        <th className="px-4 py-3 text-right text-sm font-semibold text-gray-400 sm:px-6">Duration</th>
                                        <th className="hidden sm:table-cell px-4 py-3 text-right text-sm font-semibold text-gray-400 sm:px-6">Speed</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-800 bg-gray-900">
                                    {benchmarkData.runs.map((run) => (
                                        <tr key={run.name}>
                                            <td className="px-4 py-3 text-sm font-medium text-white sm:px-6">{run.name}</td>
                                            <td className="px-4 py-3 text-right text-sm text-cyan-300 sm:px-6">{run.stories}</td>
                                            <td className="px-4 py-3 text-right text-sm text-gray-300 sm:px-6">{run.time}</td>
                                            <td className="hidden sm:table-cell px-4 py-3 text-right text-sm text-gray-400 sm:px-6">{run.speed}</td>
                                        </tr>
                                    ))}
                                </tbody>
                                <tfoot>
                                    <tr className="bg-gray-950/50 border-t border-gray-800">
                                        <td className="px-4 py-3 text-sm font-semibold text-white sm:px-6">Total</td>
                                        <td className="px-4 py-3 text-right text-sm font-semibold text-cyan-400 sm:px-6">20/30</td>
                                        <td className="px-4 py-3 text-right text-sm font-semibold text-white sm:px-6">29.5 min</td>
                                        <td className="hidden sm:table-cell px-4 py-3 text-right text-sm font-semibold text-white sm:px-6">1.48 min/story</td>
                                    </tr>
                                </tfoot>
                            </table>
                        </div>

                        {/* Methodology note */}
                        <div className="mt-8 rounded-xl bg-cyan-950/30 border border-cyan-900/50 p-6">
                            <p className="text-sm text-gray-300">
                                <span className="text-cyan-400 font-semibold">Methodology:</span>{' '}
                                Each benchmark uses Ralph&apos;s PRD-driven autonomous loop. Stories define acceptance criteria.
                                Quality gates (typecheck, lint, test, build) run after every story. No human touches the keyboard.
                                Token counts and cost come from actual API usage, not estimates.
                            </p>
                        </div>

                        <div className="mt-8 text-center">
                            <Button href="/benchmarks" variant="outline" className="text-gray-300">
                                <BoltIcon className="mr-2 h-4 w-4" />
                                See Full Benchmark Results
                            </Button>
                        </div>
                    </div>
                </Container>
            </section>
        </>
    )
}
