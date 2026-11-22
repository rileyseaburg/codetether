'use client'

import { useState, useCallback } from 'react'

// ─── Types ──────────────────────────────────────────────────────────────────

interface BenchmarkConfig {
    prdDir: string
    models: string[]
    costCeiling: number
    parallel: boolean
}

interface BenchmarkRun {
    id: string
    status: 'pending' | 'running' | 'completed' | 'failed'
    config: BenchmarkConfig
    startedAt: string
    completedAt?: string
    progress: { completed: number; total: number; currentPrd?: string; currentModel?: string }
    results?: BenchmarkSuiteResult
    error?: string
}

interface BenchmarkSuiteResult {
    totalPrds: number
    totalModels: number
    results: PrdBenchmarkResult[]
}

interface PrdBenchmarkResult {
    prdFile: string
    prdFeature: string
    tier: number
    modelResults: ModelPrdResult[]
}

interface ModelPrdResult {
    model: string
    passRate: number
    durationSecs: number
    tokensUsed: number
    costUsd: number
    stories: StoryResult[]
}

interface StoryResult {
    storyId: string
    title: string
    passed: boolean
    durationSecs: number
    tokensUsed: number
    qualityChecks: { name: string; passed: boolean }[]
}

// ─── Available models for benchmark runs ────────────────────────────────────

const AVAILABLE_MODELS = [
    'moonshotai:kimi-k2',
    'anthropic:claude-sonnet-4-20250514',
    'openai:gpt-4.1',
    'deepseek:deepseek-r1',
    'google:gemini-2.5-pro',
]

const DEFAULT_CONFIG: BenchmarkConfig = {
    prdDir: 'benchmarks/',
    models: ['moonshotai:kimi-k2'],
    costCeiling: 20.0,
    parallel: false,
}

// ─── Page ───────────────────────────────────────────────────────────────────

export default function DashboardBenchmarksPage() {
    const [runs, setRuns] = useState<BenchmarkRun[]>([])
    const [config, setConfig] = useState<BenchmarkConfig>(DEFAULT_CONFIG)
    const [isConfigOpen, setIsConfigOpen] = useState(false)
    const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

    const startBenchmark = useCallback(() => {
        if (config.models.length === 0) return

        const run: BenchmarkRun = {
            id: `bench-${Date.now()}`,
            status: 'pending',
            config: { ...config },
            startedAt: new Date().toISOString(),
            progress: { completed: 0, total: config.models.length * 8 },
        }

        setRuns((prev) => [run, ...prev])
        setSelectedRunId(run.id)
        setIsConfigOpen(false)

        // In production this would dispatch an A2A task to the agent
        // For now, mark it as pending for manual execution
        setTimeout(() => {
            setRuns((prev) =>
                prev.map((r) => (r.id === run.id ? { ...r, status: 'running' as const } : r)),
            )
        }, 500)
    }, [config])

    const toggleModel = (model: string) => {
        setConfig((prev) => ({
            ...prev,
            models: prev.models.includes(model)
                ? prev.models.filter((m) => m !== model)
                : [...prev.models, model],
        }))
    }

    const selectedRun = runs.find((r) => r.id === selectedRunId)

    return (
        <div className="min-h-screen bg-gray-950 text-white p-6">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h1 className="text-2xl font-bold">Benchmarks</h1>
                        <p className="text-gray-400 text-sm mt-1">
                            Run and monitor benchmark suites against different models
                        </p>
                    </div>
                    <button
                        onClick={() => setIsConfigOpen(!isConfigOpen)}
                        className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 text-white rounded-lg font-medium text-sm transition"
                    >
                        New Benchmark Run
                    </button>
                </div>

                {/* Configuration Panel */}
                {isConfigOpen && (
                    <div className="mb-8 rounded-2xl bg-gray-900 border border-gray-800 p-6">
                        <h2 className="text-lg font-semibold mb-4">Configure Benchmark Run</h2>

                        <div className="grid gap-6 sm:grid-cols-2">
                            {/* PRD Directory */}
                            <div>
                                <label className="block text-sm font-medium text-gray-400 mb-2">
                                    PRD Directory
                                </label>
                                <input
                                    type="text"
                                    value={config.prdDir}
                                    onChange={(e) => setConfig((prev) => ({ ...prev, prdDir: e.target.value }))}
                                    className="w-full px-3 py-2 bg-gray-950 border border-gray-700 rounded-lg text-white text-sm focus:border-cyan-500 focus:outline-none"
                                />
                            </div>

                            {/* Cost Ceiling */}
                            <div>
                                <label className="block text-sm font-medium text-gray-400 mb-2">
                                    Cost Ceiling (USD)
                                </label>
                                <input
                                    type="number"
                                    value={config.costCeiling}
                                    onChange={(e) =>
                                        setConfig((prev) => ({
                                            ...prev,
                                            costCeiling: Math.max(0, parseFloat(e.target.value) || 0),
                                        }))
                                    }
                                    step="1"
                                    min="1"
                                    className="w-full px-3 py-2 bg-gray-950 border border-gray-700 rounded-lg text-white text-sm focus:border-cyan-500 focus:outline-none"
                                />
                            </div>
                        </div>

                        {/* Model Selection */}
                        <div className="mt-6">
                            <label className="block text-sm font-medium text-gray-400 mb-2">
                                Models
                            </label>
                            <div className="flex flex-wrap gap-2">
                                {AVAILABLE_MODELS.map((model) => (
                                    <button
                                        key={model}
                                        onClick={() => toggleModel(model)}
                                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${config.models.includes(model)
                                                ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                                                : 'bg-gray-950 text-gray-400 border border-gray-800 hover:border-gray-700'
                                            }`}
                                    >
                                        {model.split(':')[1] || model}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Parallel toggle */}
                        <div className="mt-4 flex items-center gap-3">
                            <button
                                onClick={() => setConfig((prev) => ({ ...prev, parallel: !prev.parallel }))}
                                className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${config.parallel ? 'bg-cyan-500' : 'bg-gray-700'
                                    }`}
                            >
                                <span
                                    className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${config.parallel ? 'translate-x-6' : 'translate-x-1'
                                        }`}
                                />
                            </button>
                            <span className="text-sm text-gray-400">Run models in parallel</span>
                        </div>

                        {/* Actions */}
                        <div className="mt-6 flex gap-3">
                            <button
                                onClick={startBenchmark}
                                disabled={config.models.length === 0}
                                className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg font-medium text-sm transition"
                            >
                                Start Benchmark ({config.models.length} model{config.models.length !== 1 ? 's' : ''})
                            </button>
                            <button
                                onClick={() => setIsConfigOpen(false)}
                                className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg font-medium text-sm transition"
                            >
                                Cancel
                            </button>
                        </div>

                        {/* CLI equivalent */}
                        <div className="mt-4 rounded-lg bg-gray-950 border border-gray-800 p-3">
                            <div className="text-xs text-gray-500 mb-1">CLI equivalent:</div>
                            <code className="text-xs text-cyan-400 break-all">
                                codetether benchmark --prd-dir {config.prdDir} --models {config.models.join(',')} --cost-ceiling {config.costCeiling}
                                {config.parallel ? ' --parallel' : ''}
                            </code>
                        </div>
                    </div>
                )}

                <div className="grid gap-6 lg:grid-cols-3">
                    {/* Run List */}
                    <div className="lg:col-span-1">
                        <h2 className="text-sm font-semibold text-gray-400 mb-3">Benchmark Runs</h2>
                        {runs.length === 0 ? (
                            <div className="rounded-xl bg-gray-900 border border-gray-800 p-8 text-center">
                                <div className="text-gray-500 text-sm">No benchmark runs yet</div>
                                <button
                                    onClick={() => setIsConfigOpen(true)}
                                    className="mt-3 text-cyan-400 text-sm hover:text-cyan-300 transition"
                                >
                                    Start your first run →
                                </button>
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {runs.map((run) => (
                                    <button
                                        key={run.id}
                                        onClick={() => setSelectedRunId(run.id)}
                                        className={`w-full text-left rounded-xl border p-4 transition ${selectedRunId === run.id
                                                ? 'bg-gray-900 border-cyan-500/30'
                                                : 'bg-gray-900 border-gray-800 hover:border-gray-700'
                                            }`}
                                    >
                                        <div className="flex items-center justify-between mb-1">
                                            <span className="text-sm font-medium text-white">
                                                {run.config.models.length} model{run.config.models.length !== 1 ? 's' : ''}
                                            </span>
                                            <StatusBadge status={run.status} />
                                        </div>
                                        <div className="text-xs text-gray-500">
                                            {new Date(run.startedAt).toLocaleString()}
                                        </div>
                                        {run.status === 'running' && (
                                            <div className="mt-2">
                                                <div className="flex justify-between text-xs text-gray-400 mb-1">
                                                    <span>{run.progress.currentPrd ?? 'Starting...'}</span>
                                                    <span>{run.progress.completed}/{run.progress.total}</span>
                                                </div>
                                                <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                                                    <div
                                                        className="h-full bg-cyan-500 rounded-full transition-all"
                                                        style={{
                                                            width: `${run.progress.total > 0 ? (run.progress.completed / run.progress.total) * 100 : 0}%`,
                                                        }}
                                                    />
                                                </div>
                                            </div>
                                        )}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Run Detail */}
                    <div className="lg:col-span-2">
                        {selectedRun ? (
                            <RunDetail run={selectedRun} />
                        ) : (
                            <div className="rounded-xl bg-gray-900 border border-gray-800 p-12 text-center">
                                <div className="text-gray-500">
                                    {runs.length > 0
                                        ? 'Select a run to view details'
                                        : 'Click "New Benchmark Run" to get started'}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}

// ─── Sub-components ─────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: BenchmarkRun['status'] }) {
    const styles = {
        pending: 'bg-yellow-500/20 text-yellow-400',
        running: 'bg-cyan-500/20 text-cyan-400',
        completed: 'bg-green-500/20 text-green-400',
        failed: 'bg-red-500/20 text-red-400',
    }

    return (
        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${styles[status]}`}>
            {status === 'running' && (
                <span className="mr-1 h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
            )}
            {status}
        </span>
    )
}

function RunDetail({ run }: { run: BenchmarkRun }) {
    if (run.status === 'pending' || (run.status === 'running' && !run.results)) {
        return (
            <div className="rounded-xl bg-gray-900 border border-gray-800 p-8">
                <div className="flex items-center gap-3 mb-6">
                    <StatusBadge status={run.status} />
                    <span className="text-sm text-gray-400">
                        Started {new Date(run.startedAt).toLocaleString()}
                    </span>
                </div>

                <div className="space-y-4">
                    <div>
                        <h3 className="text-sm font-medium text-gray-400 mb-2">Configuration</h3>
                        <div className="grid grid-cols-2 gap-3">
                            <div className="rounded-lg bg-gray-950 border border-gray-800 p-3">
                                <div className="text-xs text-gray-500">PRD Directory</div>
                                <div className="text-sm text-white font-mono">{run.config.prdDir}</div>
                            </div>
                            <div className="rounded-lg bg-gray-950 border border-gray-800 p-3">
                                <div className="text-xs text-gray-500">Cost Ceiling</div>
                                <div className="text-sm text-white">${run.config.costCeiling.toFixed(2)}</div>
                            </div>
                        </div>
                    </div>

                    <div>
                        <h3 className="text-sm font-medium text-gray-400 mb-2">Models</h3>
                        <div className="flex flex-wrap gap-2">
                            {run.config.models.map((model) => (
                                <span
                                    key={model}
                                    className="px-3 py-1 bg-gray-950 border border-gray-800 rounded-lg text-xs text-gray-300"
                                >
                                    {model}
                                </span>
                            ))}
                        </div>
                    </div>

                    {run.status === 'running' && run.progress.currentModel && (
                        <div className="rounded-lg bg-gray-950 border border-cyan-500/20 p-4">
                            <div className="flex items-center gap-2 mb-2">
                                <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse" />
                                <span className="text-sm text-cyan-400">Running</span>
                            </div>
                            <div className="text-sm text-white">
                                {run.progress.currentModel} → {run.progress.currentPrd}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        )
    }

    if (run.status === 'failed') {
        return (
            <div className="rounded-xl bg-gray-900 border border-red-500/20 p-8">
                <div className="flex items-center gap-3 mb-4">
                    <StatusBadge status={run.status} />
                    <span className="text-sm text-gray-400">
                        Failed at {new Date(run.completedAt ?? run.startedAt).toLocaleString()}
                    </span>
                </div>
                <pre className="text-sm text-red-400 bg-gray-950 rounded-lg p-4 overflow-x-auto">
                    {run.error ?? 'Unknown error'}
                </pre>
            </div>
        )
    }

    // Completed with results
    const results = run.results
    if (!results) return null

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-3">
                <StatusBadge status={run.status} />
                <span className="text-sm text-gray-400">
                    Completed {new Date(run.completedAt ?? run.startedAt).toLocaleString()}
                </span>
            </div>

            {/* Summary stats */}
            <div className="grid grid-cols-3 gap-3">
                <div className="rounded-lg bg-gray-900 border border-gray-800 p-4 text-center">
                    <div className="text-2xl font-bold text-white">{results.totalPrds}</div>
                    <div className="text-xs text-gray-500 mt-1">PRDs</div>
                </div>
                <div className="rounded-lg bg-gray-900 border border-gray-800 p-4 text-center">
                    <div className="text-2xl font-bold text-white">{results.totalModels}</div>
                    <div className="text-xs text-gray-500 mt-1">Models</div>
                </div>
                <div className="rounded-lg bg-gray-900 border border-gray-800 p-4 text-center">
                    <div className="text-2xl font-bold text-white">
                        {results.results.reduce((sum, p) => sum + p.modelResults.length, 0)}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">Total Runs</div>
                </div>
            </div>

            {/* Per-PRD results */}
            {results.results.map((prd) => (
                <div key={prd.prdFile} className="rounded-xl bg-gray-900 border border-gray-800 p-5">
                    <div className="flex items-center gap-3 mb-4">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${prd.tier === 1
                                ? 'bg-green-500/20 text-green-400'
                                : prd.tier === 2
                                    ? 'bg-yellow-500/20 text-yellow-400'
                                    : 'bg-red-500/20 text-red-400'
                            }`}>
                            T{prd.tier}
                        </span>
                        <h3 className="text-white font-semibold">{prd.prdFeature}</h3>
                    </div>

                    <div className="space-y-2">
                        {prd.modelResults.map((mr) => (
                            <div
                                key={mr.model}
                                className="flex items-center justify-between rounded-lg bg-gray-950 border border-gray-800 px-4 py-3"
                            >
                                <div className="text-sm font-medium text-white">{mr.model}</div>
                                <div className="flex items-center gap-4">
                                    <span className={`text-sm font-medium ${mr.passRate >= 1.0 ? 'text-green-400' : mr.passRate >= 0.5 ? 'text-yellow-400' : 'text-red-400'}`}>
                                        {(mr.passRate * 100).toFixed(0)}%
                                    </span>
                                    <span className="text-sm text-gray-400">
                                        {Math.round(mr.durationSecs)}s
                                    </span>
                                    <span className="text-sm text-gray-400">
                                        ${mr.costUsd.toFixed(2)}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    )
}
