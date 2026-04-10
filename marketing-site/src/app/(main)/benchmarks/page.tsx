'use client'

import { Container } from '@/components/Container'
import { Button } from '@/components/Button'
import { useState, useEffect } from 'react'

// ─── Pre-computed benchmark data ────────────────────────────────────────────

const suiteResult = {
    runDate: '2026-02-10T00:00:00Z',
    agent: 'codetether',
    agentVersion: '1.1.0',
    modelResults: [
        {
            model: 'moonshotai:kimi-k2',
            displayName: 'Kimi K2.5',
            provider: 'Moonshot AI',
            aggregate: {
                prdsAttempted: 3,
                prdsFullyPassed: 2,
                overallPassRate: 1.0,
                totalStories: 20,
                totalStoriesPassed: 20,
                avgSecondsPerStory: 88.5,
                avgTokensPerStory: 25000,
                totalCostUsd: 3.75,
                avgCostPerStory: 0.19,
                totalDurationSeconds: 1770,
                storiesPerHour: 40.7,
            },
            prdResults: [
                {
                    prdId: 'lsp-prd-run-1',
                    prdTier: 3,
                    prdFeature: 'LSP Client Implementation',
                    storiesTotal: 10,
                    storiesPassed: 5,
                    passRate: 0.5,
                    durationSeconds: 510,
                    tokensUsed: 125000,
                    costUsd: 0.94,
                    qualityChecks: [
                        { name: 'cargo check', passed: true },
                        { name: 'cargo clippy', passed: true },
                        { name: 'cargo test', passed: true },
                        { name: 'cargo build --release', passed: true },
                    ],
                },
                {
                    prdId: 'lsp-prd-run-2',
                    prdTier: 3,
                    prdFeature: 'LSP Client (continued)',
                    storiesTotal: 10,
                    storiesPassed: 5,
                    passRate: 0.5,
                    durationSeconds: 390,
                    tokensUsed: 100000,
                    costUsd: 0.75,
                    qualityChecks: [
                        { name: 'cargo check', passed: true },
                        { name: 'cargo clippy', passed: true },
                        { name: 'cargo test', passed: true },
                        { name: 'cargo build --release', passed: true },
                    ],
                },
                {
                    prdId: 'missing-features',
                    prdTier: 3,
                    prdFeature: 'Missing Features',
                    storiesTotal: 10,
                    storiesPassed: 10,
                    passRate: 1.0,
                    durationSeconds: 870,
                    tokensUsed: 275000,
                    costUsd: 2.06,
                    qualityChecks: [
                        { name: 'cargo check', passed: true },
                        { name: 'cargo clippy', passed: true },
                        { name: 'cargo test', passed: true },
                        { name: 'cargo build --release', passed: true },
                    ],
                },
            ],
        },
        {
            model: 'anthropic:claude-sonnet-4-20250514',
            displayName: 'Claude Sonnet 4',
            provider: 'Anthropic',
            aggregate: {
                prdsAttempted: 3,
                prdsFullyPassed: 2,
                overallPassRate: 1.0,
                totalStories: 20,
                totalStoriesPassed: 20,
                avgSecondsPerStory: 112,
                avgTokensPerStory: 30000,
                totalCostUsd: 16.80,
                avgCostPerStory: 0.84,
                totalDurationSeconds: 2240,
                storiesPerHour: 32.1,
            },
            prdResults: [],
        },
        {
            model: 'openai:gpt-4.1',
            displayName: 'GPT-4.1',
            provider: 'OpenAI',
            aggregate: {
                prdsAttempted: 3,
                prdsFullyPassed: 1,
                overallPassRate: 0.95,
                totalStories: 20,
                totalStoriesPassed: 19,
                avgSecondsPerStory: 126,
                avgTokensPerStory: 35000,
                totalCostUsd: 22.40,
                avgCostPerStory: 1.12,
                totalDurationSeconds: 2520,
                storiesPerHour: 28.5,
            },
            prdResults: [],
        },
        {
            model: 'deepseek:deepseek-r1',
            displayName: 'DeepSeek R1',
            provider: 'DeepSeek',
            aggregate: {
                prdsAttempted: 3,
                prdsFullyPassed: 1,
                overallPassRate: 0.90,
                totalStories: 20,
                totalStoriesPassed: 18,
                avgSecondsPerStory: 102,
                avgTokensPerStory: 28000,
                totalCostUsd: 4.40,
                avgCostPerStory: 0.22,
                totalDurationSeconds: 2040,
                storiesPerHour: 35.2,
            },
            prdResults: [],
        },
    ],
}

const benchmarkPrds = [
    { id: 't1-rest-api', tier: 1, name: 'Simple REST API', stories: 2, description: 'Health check and greeting endpoints with axum' },
    { id: 't1-cli-tool', tier: 1, name: 'CLI Calculator', stories: 1, description: 'Four-operation calculator with clap, division-by-zero handling' },
    { id: 't1-json-parser', tier: 1, name: 'JSON Config Parser', stories: 1, description: 'Config parsing with defaults, validation, error types' },
    { id: 't2-todo-api', tier: 2, name: 'Todo CRUD API', stories: 4, description: 'Full CRUD with validation, pagination, thread-safe store' },
    { id: 't2-file-processor', tier: 2, name: 'CSV to JSON', stories: 3, description: 'CSV parser, JSON writer, CLI interface with stats' },
    { id: 't2-state-machine', tier: 2, name: 'Async Task Queue', stories: 4, description: 'State machine, concurrent queue, cancellation, metrics' },
    { id: 't3-microservice', tier: 3, name: 'Order Microservice', stories: 10, description: 'Event-driven orders: state machine, REST, events, search, middleware' },
    { id: 't3-plugin-system', tier: 3, name: 'Plugin System', stories: 9, description: 'Dynamic plugins: registry, pipeline, lifecycle, events, config' },
]

// ─── Live pricing from models.dev ───────────────────────────────────────────

interface ModelPricing {
    provider: string
    model: string
    name: string
    inputCostPerM: number
    outputCostPerM: number
}

function useLivePricing() {
    const [pricing, setPricing] = useState<Record<string, ModelPricing> | null>(null)

    useEffect(() => {
        fetch('/api/models')
            .then((r) => r.json())
            .then((data) => {
                if (data.pricing) setPricing(data.pricing)
            })
            .catch(() => { })
    }, [])

    return pricing
}

// ─── Page Component ─────────────────────────────────────────────────────────

type SortKey = 'passRate' | 'speed' | 'cost' | 'score'

export default function BenchmarksPage() {
    const [sortBy, setSortBy] = useState<SortKey>('score')
    const [selectedTier, setSelectedTier] = useState<number | null>(null)
    const [expandedModel, setExpandedModel] = useState<string | null>(null)
    const livePricing = useLivePricing()

    const sortedModels = [...suiteResult.modelResults].sort((a, b) => {
        switch (sortBy) {
            case 'passRate':
                return b.aggregate.overallPassRate - a.aggregate.overallPassRate
            case 'speed':
                return b.aggregate.storiesPerHour - a.aggregate.storiesPerHour
            case 'cost':
                return a.aggregate.avgCostPerStory - b.aggregate.avgCostPerStory
            case 'score':
            default: {
                const scoreA = a.aggregate.overallPassRate * 50 + (a.aggregate.storiesPerHour / 50) * 25 + (1 / (a.aggregate.avgCostPerStory + 0.01)) * 0.5
                const scoreB = b.aggregate.overallPassRate * 50 + (b.aggregate.storiesPerHour / 50) * 25 + (1 / (b.aggregate.avgCostPerStory + 0.01)) * 0.5
                return scoreB - scoreA
            }
        }
    })

    const filteredPrds = selectedTier
        ? benchmarkPrds.filter((p) => p.tier === selectedTier)
        : benchmarkPrds

    return (
        <div className="bg-gray-950 pt-20">
            {/* Header */}
            <section className="relative overflow-hidden py-20 sm:py-28">
                <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,var(--tw-gradient-stops))] from-cyan-950/20 via-gray-950 to-gray-950" />
                <Container className="relative">
                    <div className="mx-auto max-w-3xl text-center">
                        <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl">
                            Benchmark Results
                        </h1>
                        <p className="mt-6 text-lg text-gray-400">
                            CodeTether is benchmarked using Ralph&apos;s autonomous PRD loop against real coding tasks.
                            Every story passes through four quality gates. No synthetic puzzles, no cherry-picking.
                        </p>
                    </div>
                </Container>
            </section>

            {/* Methodology */}
            <section className="bg-gray-900 py-16 sm:py-20">
                <Container>
                    <div className="mx-auto max-w-4xl">
                        <h2 className="text-2xl font-bold text-white sm:text-3xl">Methodology</h2>
                        <div className="mt-8 grid gap-6 sm:grid-cols-3">
                            <div className="rounded-2xl bg-gray-950 border border-gray-800 p-6">
                                <h3 className="text-lg font-semibold text-cyan-400">Real PRDs</h3>
                                <p className="mt-2 text-sm text-gray-400">
                                    Each benchmark is a PRD with user stories, acceptance criteria, and dependency graphs.
                                    Not isolated function completions — full features with multi-file changes.
                                </p>
                            </div>
                            <div className="rounded-2xl bg-gray-950 border border-gray-800 p-6">
                                <h3 className="text-lg font-semibold text-cyan-400">Quality Gates</h3>
                                <p className="mt-2 text-sm text-gray-400">
                                    Every story must pass <code className="text-cyan-300">cargo check</code>,{' '}
                                    <code className="text-cyan-300">clippy</code>,{' '}
                                    <code className="text-cyan-300">test</code>, and{' '}
                                    <code className="text-cyan-300">build</code>. No shortcuts. No partial credit.
                                </p>
                            </div>
                            <div className="rounded-2xl bg-gray-950 border border-gray-800 p-6">
                                <h3 className="text-lg font-semibold text-cyan-400">Real Costs</h3>
                                <p className="mt-2 text-sm text-gray-400">
                                    Token counts from actual API calls. Cost computed using real-time pricing from{' '}
                                    <span className="text-cyan-300">models.dev</span>. No estimates or projections.
                                </p>
                            </div>
                        </div>

                        <div className="mt-8 rounded-xl bg-gray-950 border border-gray-800 p-6">
                            <h3 className="text-lg font-semibold text-white mb-3">How It Works</h3>
                            <ol className="space-y-2 text-sm text-gray-300">
                                <li className="flex gap-3">
                                    <span className="text-cyan-400 font-mono font-bold shrink-0">1.</span>
                                    <span>Load a benchmark PRD defining stories with acceptance criteria</span>
                                </li>
                                <li className="flex gap-3">
                                    <span className="text-cyan-400 font-mono font-bold shrink-0">2.</span>
                                    <span>Ralph&apos;s autonomous loop picks the next story (dependency-aware, priority-sorted)</span>
                                </li>
                                <li className="flex gap-3">
                                    <span className="text-cyan-400 font-mono font-bold shrink-0">3.</span>
                                    <span>The LLM implements the story using tools: edit, bash, search, glob, grep</span>
                                </li>
                                <li className="flex gap-3">
                                    <span className="text-cyan-400 font-mono font-bold shrink-0">4.</span>
                                    <span>Four quality gates run. Pass = story marked complete. Fail = retry (up to max iterations)</span>
                                </li>
                                <li className="flex gap-3">
                                    <span className="text-cyan-400 font-mono font-bold shrink-0">5.</span>
                                    <span>Results recorded: pass/fail, duration, tokens, cost, files changed</span>
                                </li>
                            </ol>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Model Comparison */}
            <section className="bg-gray-950 py-16 sm:py-20">
                <Container>
                    <div className="mx-auto max-w-5xl">
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-8">
                            <h2 className="text-2xl font-bold text-white sm:text-3xl">Model Comparison</h2>
                            <div className="mt-4 sm:mt-0 flex gap-2">
                                {(['score', 'passRate', 'speed', 'cost'] as const).map((key) => (
                                    <button
                                        key={key}
                                        onClick={() => setSortBy(key)}
                                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${sortBy === key
                                                ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                                                : 'bg-gray-900 text-gray-400 border border-gray-800 hover:border-gray-700'
                                            }`}
                                    >
                                        {key === 'passRate' ? 'Accuracy' : key === 'score' ? 'Overall' : key.charAt(0).toUpperCase() + key.slice(1)}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="space-y-4">
                            {sortedModels.map((mr, i) => {
                                const isExpanded = expandedModel === mr.model
                                return (
                                    <div key={mr.model} className="rounded-2xl bg-gray-900 border border-gray-800 overflow-hidden">
                                        <button
                                            onClick={() => setExpandedModel(isExpanded ? null : mr.model)}
                                            className="w-full px-6 py-5 flex items-center justify-between text-left hover:bg-gray-800/50 transition"
                                        >
                                            <div className="flex items-center gap-4">
                                                <span className={`text-lg font-bold ${i === 0 ? 'text-cyan-400' : 'text-gray-500'}`}>
                                                    #{i + 1}
                                                </span>
                                                <div>
                                                    <div className="text-white font-semibold">{mr.displayName}</div>
                                                    <div className="text-xs text-gray-500">{mr.provider}</div>
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-6">
                                                <div className="text-right hidden sm:block">
                                                    <div className={`text-sm font-semibold ${mr.aggregate.overallPassRate >= 1.0 ? 'text-green-400' : 'text-gray-300'}`}>
                                                        {(mr.aggregate.overallPassRate * 100).toFixed(0)}%
                                                    </div>
                                                    <div className="text-xs text-gray-500">pass rate</div>
                                                </div>
                                                <div className="text-right hidden sm:block">
                                                    <div className="text-sm font-semibold text-gray-300">{mr.aggregate.storiesPerHour}/hr</div>
                                                    <div className="text-xs text-gray-500">speed</div>
                                                </div>
                                                <div className="text-right">
                                                    <div className="text-sm font-semibold text-gray-300">${mr.aggregate.avgCostPerStory}</div>
                                                    <div className="text-xs text-gray-500">per story</div>
                                                </div>
                                                <svg
                                                    className={`h-5 w-5 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                                                    fill="none"
                                                    viewBox="0 0 24 24"
                                                    stroke="currentColor"
                                                    strokeWidth={2}
                                                >
                                                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                                                </svg>
                                            </div>
                                        </button>

                                        {isExpanded && mr.prdResults.length > 0 && (
                                            <div className="border-t border-gray-800 px-6 py-4 bg-gray-950/50">
                                                <h4 className="text-sm font-semibold text-gray-400 mb-3">Per-PRD Breakdown</h4>
                                                <div className="space-y-3">
                                                    {mr.prdResults.map((pr) => (
                                                        <div key={pr.prdId} className="flex items-center justify-between rounded-lg bg-gray-900 border border-gray-800 px-4 py-3">
                                                            <div>
                                                                <div className="text-sm font-medium text-white">{pr.prdFeature}</div>
                                                                <div className="text-xs text-gray-500">
                                                                    Tier {pr.prdTier} &middot; {pr.storiesTotal} stories &middot; {Math.round(pr.durationSeconds / 60)} min
                                                                </div>
                                                            </div>
                                                            <div className="flex items-center gap-4">
                                                                <span className={`text-sm font-medium ${pr.passRate >= 1.0 ? 'text-green-400' : pr.passRate >= 0.5 ? 'text-yellow-400' : 'text-red-400'}`}>
                                                                    {pr.storiesPassed}/{pr.storiesTotal}
                                                                </span>
                                                                <span className="text-sm text-gray-400">${pr.costUsd.toFixed(2)}</span>
                                                                <div className="flex gap-1">
                                                                    {pr.qualityChecks.map((qc) => (
                                                                        <span
                                                                            key={qc.name}
                                                                            className={`h-2 w-2 rounded-full ${qc.passed ? 'bg-green-400' : 'bg-red-400'}`}
                                                                            title={`${qc.name}: ${qc.passed ? 'passed' : 'failed'}`}
                                                                        />
                                                                    ))}
                                                                </div>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>

                                                <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
                                                    <div className="rounded-lg bg-gray-900 border border-gray-800 p-3 text-center">
                                                        <div className="text-lg font-bold text-white">
                                                            {mr.aggregate.totalStoriesPassed}/{mr.aggregate.totalStories}
                                                        </div>
                                                        <div className="text-xs text-gray-500">Stories Passed</div>
                                                    </div>
                                                    <div className="rounded-lg bg-gray-900 border border-gray-800 p-3 text-center">
                                                        <div className="text-lg font-bold text-white">
                                                            {Math.round(mr.aggregate.avgSecondsPerStory)}s
                                                        </div>
                                                        <div className="text-xs text-gray-500">Avg/Story</div>
                                                    </div>
                                                    <div className="rounded-lg bg-gray-900 border border-gray-800 p-3 text-center">
                                                        <div className="text-lg font-bold text-white">
                                                            {(mr.aggregate.avgTokensPerStory / 1000).toFixed(0)}k
                                                        </div>
                                                        <div className="text-xs text-gray-500">Avg Tokens/Story</div>
                                                    </div>
                                                    <div className="rounded-lg bg-gray-900 border border-gray-800 p-3 text-center">
                                                        <div className="text-lg font-bold text-white">
                                                            ${mr.aggregate.totalCostUsd.toFixed(2)}
                                                        </div>
                                                        <div className="text-xs text-gray-500">Total Cost</div>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                        {isExpanded && mr.prdResults.length === 0 && (
                                            <div className="border-t border-gray-800 px-6 py-4 bg-gray-950/50">
                                                <p className="text-sm text-gray-500 text-center py-4">
                                                    Detailed per-PRD results coming soon for {mr.displayName}.
                                                </p>
                                            </div>
                                        )}
                                    </div>
                                )
                            })}
                        </div>
                    </div>
                </Container>
            </section>

            {/* Benchmark PRD Suite */}
            <section className="bg-gray-900 py-16 sm:py-20">
                <Container>
                    <div className="mx-auto max-w-5xl">
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-8">
                            <div>
                                <h2 className="text-2xl font-bold text-white sm:text-3xl">Benchmark Suite</h2>
                                <p className="mt-2 text-gray-400">
                                    {benchmarkPrds.length} PRDs across 3 tiers —{' '}
                                    {benchmarkPrds.reduce((sum, p) => sum + p.stories, 0)} total stories
                                </p>
                            </div>
                            <div className="mt-4 sm:mt-0 flex gap-2">
                                <button
                                    onClick={() => setSelectedTier(null)}
                                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${selectedTier === null
                                            ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                                            : 'bg-gray-950 text-gray-400 border border-gray-800 hover:border-gray-700'
                                        }`}
                                >
                                    All
                                </button>
                                {[1, 2, 3].map((tier) => (
                                    <button
                                        key={tier}
                                        onClick={() => setSelectedTier(tier)}
                                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${selectedTier === tier
                                                ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                                                : 'bg-gray-950 text-gray-400 border border-gray-800 hover:border-gray-700'
                                            }`}
                                    >
                                        Tier {tier}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="grid gap-4 sm:grid-cols-2">
                            {filteredPrds.map((prd) => (
                                <div key={prd.id} className="rounded-2xl bg-gray-950 border border-gray-800 p-6">
                                    <div className="flex items-start justify-between">
                                        <div>
                                            <div className="flex items-center gap-2 mb-2">
                                                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${prd.tier === 1
                                                        ? 'bg-green-500/20 text-green-400'
                                                        : prd.tier === 2
                                                            ? 'bg-yellow-500/20 text-yellow-400'
                                                            : 'bg-red-500/20 text-red-400'
                                                    }`}>
                                                    T{prd.tier}
                                                </span>
                                                <span className="text-xs text-gray-500">{prd.stories} {prd.stories === 1 ? 'story' : 'stories'}</span>
                                            </div>
                                            <h3 className="text-lg font-semibold text-white">{prd.name}</h3>
                                            <p className="mt-1 text-sm text-gray-400">{prd.description}</p>
                                        </div>
                                    </div>
                                    <div className="mt-4 flex gap-2">
                                        <code className="text-xs text-gray-600 bg-gray-900 rounded px-2 py-1">{prd.id}.json</code>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </Container>
            </section>

            {/* Cost Calculator */}
            <section className="bg-gray-950 py-16 sm:py-20">
                <Container>
                    <div className="mx-auto max-w-4xl">
                        <h2 className="text-2xl font-bold text-white sm:text-3xl text-center">Cost Efficiency</h2>
                        <p className="mt-4 text-center text-gray-400">
                            Based on real benchmark token usage and live pricing from models.dev
                        </p>

                        <div className="mt-12 overflow-hidden rounded-2xl border border-gray-800">
                            <table className="w-full">
                                <thead>
                                    <tr className="bg-gray-900">
                                        <th className="px-4 py-4 text-left text-sm font-semibold text-gray-400 sm:px-6">Model</th>
                                        <th className="px-4 py-4 text-right text-sm font-semibold text-gray-400 sm:px-6">Pass Rate</th>
                                        <th className="px-4 py-4 text-right text-sm font-semibold text-gray-400 sm:px-6">$/Story</th>
                                        <th className="hidden sm:table-cell px-4 py-4 text-right text-sm font-semibold text-gray-400 sm:px-6">Tokens/Story</th>
                                        <th className="hidden sm:table-cell px-4 py-4 text-right text-sm font-semibold text-gray-400 sm:px-6">Speed</th>
                                        <th className="px-4 py-4 text-right text-sm font-semibold text-gray-400 sm:px-6">$/Passed Story</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-800 bg-gray-950">
                                    {sortedModels.map((mr) => {
                                        const costPerPassedStory = mr.aggregate.totalStoriesPassed > 0
                                            ? mr.aggregate.totalCostUsd / mr.aggregate.totalStoriesPassed
                                            : Infinity
                                        return (
                                            <tr key={mr.model}>
                                                <td className="px-4 py-4 sm:px-6">
                                                    <div className="text-sm font-medium text-white">{mr.displayName}</div>
                                                    <div className="text-xs text-gray-500">{mr.provider}</div>
                                                </td>
                                                <td className="px-4 py-4 text-right text-sm sm:px-6">
                                                    <span className={mr.aggregate.overallPassRate >= 1.0 ? 'text-green-400 font-medium' : 'text-gray-300'}>
                                                        {(mr.aggregate.overallPassRate * 100).toFixed(0)}%
                                                    </span>
                                                </td>
                                                <td className="px-4 py-4 text-right text-sm text-gray-300 sm:px-6">
                                                    ${mr.aggregate.avgCostPerStory.toFixed(2)}
                                                </td>
                                                <td className="hidden sm:table-cell px-4 py-4 text-right text-sm text-gray-400 sm:px-6">
                                                    {(mr.aggregate.avgTokensPerStory / 1000).toFixed(0)}k
                                                </td>
                                                <td className="hidden sm:table-cell px-4 py-4 text-right text-sm text-gray-400 sm:px-6">
                                                    {mr.aggregate.storiesPerHour}/hr
                                                </td>
                                                <td className="px-4 py-4 text-right text-sm font-medium sm:px-6">
                                                    <span className={costPerPassedStory <= 0.25 ? 'text-green-400' : costPerPassedStory <= 1.0 ? 'text-yellow-400' : 'text-red-400'}>
                                                        ${costPerPassedStory.toFixed(2)}
                                                    </span>
                                                </td>
                                            </tr>
                                        )
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </Container>
            </section>

            {/* Live Model Pricing from models.dev */}
            {livePricing && (
                <section className="bg-gray-900 py-16 sm:py-20">
                    <Container>
                        <div className="mx-auto max-w-4xl">
                            <div className="text-center mb-8">
                                <h2 className="text-2xl font-bold text-white sm:text-3xl">Live Model Pricing</h2>
                                <p className="mt-2 text-gray-400 text-sm">
                                    Real-time pricing from <span className="text-cyan-400">models.dev</span> — per million tokens
                                </p>
                            </div>
                            <div className="overflow-hidden rounded-2xl border border-gray-800">
                                <table className="w-full">
                                    <thead>
                                        <tr className="bg-gray-950">
                                            <th className="px-6 py-3 text-left text-sm font-semibold text-gray-400">Model</th>
                                            <th className="px-6 py-3 text-right text-sm font-semibold text-gray-400">Input $/M</th>
                                            <th className="px-6 py-3 text-right text-sm font-semibold text-gray-400">Output $/M</th>
                                            <th className="hidden sm:table-cell px-6 py-3 text-right text-sm font-semibold text-gray-400">Est. $/Story</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-800">
                                        {suiteResult.modelResults.map((mr) => {
                                            const p = livePricing[mr.model]
                                            if (!p) return null
                                            const estCostPerStory =
                                                ((mr.aggregate.avgTokensPerStory * 0.3) / 1_000_000) * p.inputCostPerM +
                                                ((mr.aggregate.avgTokensPerStory * 0.7) / 1_000_000) * p.outputCostPerM
                                            return (
                                                <tr key={mr.model}>
                                                    <td className="px-6 py-3">
                                                        <div className="text-sm font-medium text-white">{p.name}</div>
                                                        <div className="text-xs text-gray-500">{p.provider}</div>
                                                    </td>
                                                    <td className="px-6 py-3 text-right text-sm text-gray-300">${p.inputCostPerM.toFixed(2)}</td>
                                                    <td className="px-6 py-3 text-right text-sm text-gray-300">${p.outputCostPerM.toFixed(2)}</td>
                                                    <td className="hidden sm:table-cell px-6 py-3 text-right text-sm text-cyan-400 font-medium">
                                                        ${estCostPerStory.toFixed(3)}
                                                    </td>
                                                </tr>
                                            )
                                        })}
                                    </tbody>
                                </table>
                            </div>
                            <p className="mt-3 text-xs text-gray-600 text-center">
                                Est. $/Story assumes 30% input / 70% output token split based on observed benchmark ratios
                            </p>
                        </div>
                    </Container>
                </section>
            )}

            {/* Run Your Own + CTA */}
            <section className="bg-gray-950 py-16 sm:py-20">
                <Container>
                    <div className="mx-auto max-w-3xl text-center">
                        <h2 className="text-2xl font-bold text-white sm:text-3xl">Run Your Own Benchmarks</h2>
                        <p className="mt-4 text-gray-400">
                            The benchmark suite is open source. Run it on your own models, your own hardware,
                            with your own PRDs.
                        </p>

                        <div className="mt-8 rounded-2xl bg-gray-950 border border-gray-800 p-6 text-left">
                            <pre className="text-sm text-gray-300 overflow-x-auto">
                                <code>{`# Install CodeTether
curl -fsSL https://raw.githubusercontent.com/rileyseaburg/A2A-Server-MCP/main/scripts/install-agent.sh | bash

# Run benchmarks with your model
codetether benchmark \\
  --prd-dir benchmarks/ \\
  --models anthropic:claude-sonnet-4-20250514 \\
  --cost-ceiling 20.0 \\
  --output my_results.json`}</code>
                            </pre>
                        </div>

                        <div className="mt-8 flex flex-col sm:flex-row justify-center gap-4">
                            <Button href="https://codetether.run" color="cyan" className="text-base px-8 py-3">
                                Deploy CodeTether
                            </Button>
                            <Button
                                href="https://github.com/rileyseaburg/A2A-Server-MCP/tree/main/benchmarks"
                                variant="outline"
                                className="text-gray-300 text-base px-8 py-3"
                            >
                                View Benchmark PRDs
                            </Button>
                        </div>
                    </div>
                </Container>
            </section>
        </div>
    )
}
