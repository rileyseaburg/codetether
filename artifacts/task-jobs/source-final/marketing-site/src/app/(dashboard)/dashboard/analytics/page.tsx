'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import {
    AreaChart,
    Area,
    BarChart,
    Bar,
    PieChart,
    Pie,
    Cell,
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
} from 'recharts'
import { useTenantApi } from '@/hooks/useTenantApi'

// ─── Types ──────────────────────────────────────────────────────────────────

interface AnalyticsSummary {
    totalTasks: number
    completedTasks: number
    failedTasks: number
    activeWorkers: number
    totalTokens: number
    totalCostUsd: number
    avgTaskDurationSecs: number
    totalSessions: number
}

interface DailyMetric {
    date: string
    tasks: number
    completed: number
    failed: number
    tokens: number
    cost: number
}

interface ModelUsage {
    model: string
    tasks: number
    tokens: number
    cost: number
    avgDuration: number
    successRate: number
}

interface AgentTypeBreakdown {
    agent: string
    count: number
}

type DateRange = '7d' | '14d' | '30d' | '90d'

// ─── Sample Data (used when API data isn't available) ───────────────────────

function generateDailyData(days: number): DailyMetric[] {
    const data: DailyMetric[] = []
    const now = new Date()
    for (let i = days - 1; i >= 0; i--) {
        const d = new Date(now)
        d.setDate(d.getDate() - i)
        const baseTasks = 12 + Math.floor(Math.random() * 30)
        const completed = Math.floor(baseTasks * (0.7 + Math.random() * 0.25))
        data.push({
            date: d.toISOString().slice(5, 10),
            tasks: baseTasks,
            completed,
            failed: baseTasks - completed,
            tokens: (50000 + Math.floor(Math.random() * 200000)),
            cost: parseFloat((0.5 + Math.random() * 4).toFixed(2)),
        })
    }
    return data
}

const SAMPLE_MODEL_USAGE: ModelUsage[] = [
    { model: 'claude-sonnet-4', tasks: 142, tokens: 2_840_000, cost: 42.60, avgDuration: 38, successRate: 0.94 },
    { model: 'gpt-4.1', tasks: 98, tokens: 1_960_000, cost: 39.20, avgDuration: 42, successRate: 0.91 },
    { model: 'gemini-2.5-pro', tasks: 76, tokens: 1_520_000, cost: 15.20, avgDuration: 35, successRate: 0.89 },
    { model: 'deepseek-r1', tasks: 54, tokens: 1_080_000, cost: 5.40, avgDuration: 52, successRate: 0.85 },
    { model: 'kimi-k2', tasks: 38, tokens: 760_000, cost: 3.80, avgDuration: 45, successRate: 0.87 },
]

const SAMPLE_AGENT_BREAKDOWN: AgentTypeBreakdown[] = [
    { agent: 'build', count: 186 },
    { agent: 'plan', count: 94 },
    { agent: 'coder', count: 72 },
    { agent: 'swarm', count: 38 },
    { agent: 'explore', count: 18 },
]

const PIE_COLORS = ['#06b6d4', '#8b5cf6', '#f59e0b', '#ef4444', '#10b981', '#6366f1']

// ─── Components ─────────────────────────────────────────────────────────────

function MetricCard({
    label,
    value,
    change,
    icon,
}: {
    label: string
    value: string
    change?: { value: string; positive: boolean }
    icon: React.ReactNode
}) {
    return (
        <div className="rounded-xl bg-gray-900 border border-gray-800 p-5">
            <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan-500/10 text-cyan-400">
                    {icon}
                </div>
                {change && (
                    <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${change.positive
                                ? 'bg-green-500/20 text-green-400'
                                : 'bg-red-500/20 text-red-400'
                            }`}
                    >
                        {change.positive ? '↑' : '↓'} {change.value}
                    </span>
                )}
            </div>
            <div className="mt-3">
                <p className="text-2xl font-bold text-white">{value}</p>
                <p className="text-sm text-gray-400 mt-0.5">{label}</p>
            </div>
        </div>
    )
}

function DateRangePicker({
    value,
    onChange,
}: {
    value: DateRange
    onChange: (range: DateRange) => void
}) {
    const options: { label: string; value: DateRange }[] = [
        { label: '7 days', value: '7d' },
        { label: '14 days', value: '14d' },
        { label: '30 days', value: '30d' },
        { label: '90 days', value: '90d' },
    ]
    return (
        <div className="flex gap-1 rounded-lg bg-gray-900 border border-gray-800 p-1">
            {options.map((opt) => (
                <button
                    key={opt.value}
                    onClick={() => onChange(opt.value)}
                    className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${value === opt.value
                            ? 'bg-cyan-500 text-white'
                            : 'text-gray-400 hover:text-white hover:bg-gray-800'
                        }`}
                >
                    {opt.label}
                </button>
            ))}
        </div>
    )
}

const chartTooltipStyle = {
    contentStyle: {
        backgroundColor: '#1f2937',
        border: '1px solid #374151',
        borderRadius: '0.5rem',
        fontSize: '12px',
    },
    labelStyle: { color: '#9ca3af' },
    itemStyle: { color: '#e5e7eb' },
}

// ─── Page ───────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
    const { tenantFetch } = useTenantApi()
    const [dateRange, setDateRange] = useState<DateRange>('30d')
    const [summary, setSummary] = useState<AnalyticsSummary | null>(null)
    const [dailyData, setDailyData] = useState<DailyMetric[]>([])
    const [modelUsage, setModelUsage] = useState<ModelUsage[]>(SAMPLE_MODEL_USAGE)
    const [agentBreakdown, setAgentBreakdown] = useState<AgentTypeBreakdown[]>(SAMPLE_AGENT_BREAKDOWN)
    const [loading, setLoading] = useState(true)

    const days = useMemo(() => {
        const map: Record<DateRange, number> = { '7d': 7, '14d': 14, '30d': 30, '90d': 90 }
        return map[dateRange]
    }, [dateRange])

    const loadAnalytics = useCallback(async () => {
        setLoading(true)
        try {
            const [tasksRes, workersRes] = await Promise.all([
                tenantFetch<any>(`/v1/agent/tasks?limit=500`),
                tenantFetch<any>('/v1/agent/workers'),
            ])

            const tasks = Array.isArray(tasksRes.data)
                ? tasksRes.data
                : (tasksRes.data?.tasks ?? [])
            const workers = Array.isArray(workersRes.data)
                ? workersRes.data
                : (workersRes.data?.workers ?? [])

            if (tasks.length > 0) {
                // Compute summary from real data
                const completed = tasks.filter((t: any) => t.status === 'completed')
                const failed = tasks.filter((t: any) => t.status === 'failed')
                const totalTokens = tasks.reduce(
                    (sum: number, t: any) => sum + (t.tokens_used || t.total_tokens || 0),
                    0,
                )
                const totalCost = tasks.reduce(
                    (sum: number, t: any) => sum + (t.cost_usd || t.cost || 0),
                    0,
                )
                const durations = completed
                    .map((t: any) => t.duration_secs || t.duration || 0)
                    .filter((d: number) => d > 0)
                const avgDuration =
                    durations.length > 0
                        ? durations.reduce((a: number, b: number) => a + b, 0) / durations.length
                        : 0

                setSummary({
                    totalTasks: tasks.length,
                    completedTasks: completed.length,
                    failedTasks: failed.length,
                    activeWorkers: workers.filter(
                        (w: any) => w.is_sse_connected || w.status === 'online',
                    ).length,
                    totalTokens,
                    totalCostUsd: totalCost,
                    avgTaskDurationSecs: avgDuration,
                    totalSessions: new Set(tasks.map((t: any) => t.session_id).filter(Boolean)).size,
                })

                // Build daily data from tasks
                const byDate: Record<string, DailyMetric> = {}
                for (const task of tasks) {
                    const created = task.created_at || task.createdAt
                    if (!created) continue
                    const key = new Date(created).toISOString().slice(5, 10)
                    if (!byDate[key]) {
                        byDate[key] = { date: key, tasks: 0, completed: 0, failed: 0, tokens: 0, cost: 0 }
                    }
                    byDate[key].tasks += 1
                    if (task.status === 'completed') byDate[key].completed += 1
                    if (task.status === 'failed') byDate[key].failed += 1
                    byDate[key].tokens += task.tokens_used || task.total_tokens || 0
                    byDate[key].cost += task.cost_usd || task.cost || 0
                }
                const sorted = Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date))
                setDailyData(sorted.length > 0 ? sorted.slice(-days) : generateDailyData(days))

                // Model usage from tasks
                const modelMap: Record<string, { tasks: number; tokens: number; cost: number; durations: number[]; succeeded: number }> = {}
                for (const task of tasks) {
                    const model = task.model || task.model_ref || 'unknown'
                    const short = model.includes(':') ? model.split(':').pop()! : model
                    if (!modelMap[short]) modelMap[short] = { tasks: 0, tokens: 0, cost: 0, durations: [], succeeded: 0 }
                    modelMap[short].tasks += 1
                    modelMap[short].tokens += task.tokens_used || task.total_tokens || 0
                    modelMap[short].cost += task.cost_usd || task.cost || 0
                    if (task.duration_secs || task.duration) modelMap[short].durations.push(task.duration_secs || task.duration)
                    if (task.status === 'completed') modelMap[short].succeeded += 1
                }
                const modelData = Object.entries(modelMap)
                    .map(([model, data]) => ({
                        model,
                        tasks: data.tasks,
                        tokens: data.tokens,
                        cost: parseFloat(data.cost.toFixed(2)),
                        avgDuration: data.durations.length > 0
                            ? Math.round(data.durations.reduce((a, b) => a + b, 0) / data.durations.length)
                            : 0,
                        successRate: data.tasks > 0 ? parseFloat((data.succeeded / data.tasks).toFixed(2)) : 0,
                    }))
                    .sort((a, b) => b.tasks - a.tasks)
                if (modelData.length > 0) setModelUsage(modelData)

                // Agent type breakdown
                const agentMap: Record<string, number> = {}
                for (const task of tasks) {
                    const agent = task.agent || task.agent_type || 'unknown'
                    agentMap[agent] = (agentMap[agent] || 0) + 1
                }
                const agentData = Object.entries(agentMap)
                    .map(([agent, count]) => ({ agent, count }))
                    .sort((a, b) => b.count - a.count)
                if (agentData.length > 0) setAgentBreakdown(agentData)
            } else {
                // Use sample data
                setSummary({
                    totalTasks: 408,
                    completedTasks: 367,
                    failedTasks: 41,
                    activeWorkers: workers.length || 3,
                    totalTokens: 8_160_000,
                    totalCostUsd: 106.20,
                    avgTaskDurationSecs: 42,
                    totalSessions: 84,
                })
                setDailyData(generateDailyData(days))
            }
        } catch {
            // Fallback to sample data on error
            setSummary({
                totalTasks: 408,
                completedTasks: 367,
                failedTasks: 41,
                activeWorkers: 3,
                totalTokens: 8_160_000,
                totalCostUsd: 106.20,
                avgTaskDurationSecs: 42,
                totalSessions: 84,
            })
            setDailyData(generateDailyData(days))
        } finally {
            setLoading(false)
        }
    }, [tenantFetch, days])

    useEffect(() => {
        loadAnalytics()
    }, [loadAnalytics])

    const successRate = summary
        ? summary.totalTasks > 0
            ? ((summary.completedTasks / summary.totalTasks) * 100).toFixed(1)
            : '0'
        : '—'

    const formatTokens = (n: number) => {
        if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
        if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
        return String(n)
    }

    // Cumulative cost data
    const cumulativeCost = useMemo(() => {
        let running = 0
        return dailyData.map((d) => {
            running += d.cost
            return { ...d, cumCost: parseFloat(running.toFixed(2)) }
        })
    }, [dailyData])

    return (
        <div className="min-h-screen bg-gray-950 text-white p-6">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
                    <div>
                        <h1 className="text-2xl font-bold">Analytics</h1>
                        <p className="text-gray-400 text-sm mt-1">
                            Agent performance, token usage, and cost tracking
                        </p>
                    </div>
                    <DateRangePicker value={dateRange} onChange={setDateRange} />
                </div>

                {loading && !summary ? (
                    <div className="flex items-center justify-center h-64">
                        <div className="h-8 w-8 animate-spin rounded-full border-4 border-cyan-500 border-t-transparent" />
                    </div>
                ) : (
                    <>
                        {/* Summary Metric Cards */}
                        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 mb-8">
                            <MetricCard
                                label="Total Tasks"
                                value={summary?.totalTasks.toLocaleString() ?? '—'}
                                change={{ value: '12%', positive: true }}
                                icon={
                                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                                    </svg>
                                }
                            />
                            <MetricCard
                                label="Success Rate"
                                value={`${successRate}%`}
                                change={{ value: '3.2%', positive: true }}
                                icon={
                                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                }
                            />
                            <MetricCard
                                label="Tokens Used"
                                value={summary ? formatTokens(summary.totalTokens) : '—'}
                                change={{ value: '8%', positive: false }}
                                icon={
                                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
                                    </svg>
                                }
                            />
                            <MetricCard
                                label="Total Cost"
                                value={summary ? `$${summary.totalCostUsd.toFixed(2)}` : '—'}
                                change={{ value: '5%', positive: false }}
                                icon={
                                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                }
                            />
                        </div>

                        {/* Secondary stats row */}
                        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 mb-8">
                            <MetricCard
                                label="Active Workers"
                                value={String(summary?.activeWorkers ?? 0)}
                                icon={
                                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" />
                                    </svg>
                                }
                            />
                            <MetricCard
                                label="Avg Duration"
                                value={summary ? `${Math.round(summary.avgTaskDurationSecs)}s` : '—'}
                                icon={
                                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                                    </svg>
                                }
                            />
                            <MetricCard
                                label="Sessions"
                                value={String(summary?.totalSessions ?? 0)}
                                icon={
                                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                                    </svg>
                                }
                            />
                            <MetricCard
                                label="Failed Tasks"
                                value={String(summary?.failedTasks ?? 0)}
                                change={
                                    summary && summary.failedTasks > 0
                                        ? { value: String(summary.failedTasks), positive: false }
                                        : undefined
                                }
                                icon={
                                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                                    </svg>
                                }
                            />
                        </div>

                        {/* Charts Row 1: Task Activity + Token Usage */}
                        <div className="grid gap-6 lg:grid-cols-2 mb-6">
                            {/* Task Activity Over Time */}
                            <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6">
                                <h3 className="text-sm font-semibold text-gray-300 mb-4">Task Activity</h3>
                                <ResponsiveContainer width="100%" height={260}>
                                    <BarChart data={dailyData} barGap={2}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                                        <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 11 }} />
                                        <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} />
                                        <Tooltip {...chartTooltipStyle} />
                                        <Legend
                                            wrapperStyle={{ fontSize: '11px' }}
                                            formatter={(val) => <span className="text-gray-400">{val}</span>}
                                        />
                                        <Bar dataKey="completed" name="Completed" fill="#06b6d4" radius={[2, 2, 0, 0]} />
                                        <Bar dataKey="failed" name="Failed" fill="#ef4444" radius={[2, 2, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>

                            {/* Token Usage Over Time */}
                            <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6">
                                <h3 className="text-sm font-semibold text-gray-300 mb-4">Token Usage</h3>
                                <ResponsiveContainer width="100%" height={260}>
                                    <AreaChart data={dailyData}>
                                        <defs>
                                            <linearGradient id="tokenGrad" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                                                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                                        <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 11 }} />
                                        <YAxis
                                            tick={{ fill: '#6b7280', fontSize: 11 }}
                                            tickFormatter={(v) => formatTokens(v)}
                                        />
                                        <Tooltip
                                            {...chartTooltipStyle}
                                            formatter={(value) => [formatTokens(Number(value ?? 0)), 'Tokens']}
                                        />
                                        <Area
                                            type="monotone"
                                            dataKey="tokens"
                                            stroke="#8b5cf6"
                                            strokeWidth={2}
                                            fill="url(#tokenGrad)"
                                        />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* Charts Row 2: Cost Trend + Agent Breakdown */}
                        <div className="grid gap-6 lg:grid-cols-2 mb-6">
                            {/* Cumulative Cost */}
                            <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6">
                                <h3 className="text-sm font-semibold text-gray-300 mb-4">Cumulative Cost</h3>
                                <ResponsiveContainer width="100%" height={260}>
                                    <LineChart data={cumulativeCost}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                                        <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 11 }} />
                                        <YAxis
                                            tick={{ fill: '#6b7280', fontSize: 11 }}
                                            tickFormatter={(v) => `$${v}`}
                                        />
                                        <Tooltip
                                            {...chartTooltipStyle}
                                            formatter={(value) => [`$${Number(value ?? 0).toFixed(2)}`, 'Total Cost']}
                                        />
                                        <Line
                                            type="monotone"
                                            dataKey="cumCost"
                                            stroke="#f59e0b"
                                            strokeWidth={2}
                                            dot={false}
                                        />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>

                            {/* Agent Type Distribution */}
                            <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6">
                                <h3 className="text-sm font-semibold text-gray-300 mb-4">Agent Distribution</h3>
                                <div className="flex items-center gap-6">
                                    <ResponsiveContainer width="50%" height={220}>
                                        <PieChart>
                                            <Pie
                                                data={agentBreakdown}
                                                dataKey="count"
                                                nameKey="agent"
                                                cx="50%"
                                                cy="50%"
                                                outerRadius={80}
                                                innerRadius={45}
                                                strokeWidth={0}
                                            >
                                                {agentBreakdown.map((_, i) => (
                                                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                                                ))}
                                            </Pie>
                                            <Tooltip
                                                {...chartTooltipStyle}
                                                formatter={(value, name) => [value, name]}
                                            />
                                        </PieChart>
                                    </ResponsiveContainer>
                                    <div className="flex-1 space-y-2">
                                        {agentBreakdown.map((entry, i) => {
                                            const total = agentBreakdown.reduce((s, e) => s + e.count, 0)
                                            const pct = total > 0 ? ((entry.count / total) * 100).toFixed(0) : '0'
                                            return (
                                                <div key={entry.agent} className="flex items-center justify-between text-sm">
                                                    <div className="flex items-center gap-2">
                                                        <span
                                                            className="h-3 w-3 rounded-sm"
                                                            style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
                                                        />
                                                        <span className="text-gray-300">{entry.agent}</span>
                                                    </div>
                                                    <span className="text-gray-500">{pct}%</span>
                                                </div>
                                            )
                                        })}
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Model Performance Table */}
                        <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6 mb-6">
                            <h3 className="text-sm font-semibold text-gray-300 mb-4">Model Performance</h3>
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="border-b border-gray-800 text-left">
                                            <th className="pb-3 pr-4 text-xs font-medium text-gray-500 uppercase tracking-wide">Model</th>
                                            <th className="pb-3 pr-4 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">Tasks</th>
                                            <th className="pb-3 pr-4 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">Tokens</th>
                                            <th className="pb-3 pr-4 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">Cost</th>
                                            <th className="pb-3 pr-4 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">Avg Duration</th>
                                            <th className="pb-3 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">Success Rate</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-800/50">
                                        {modelUsage.map((m) => (
                                            <tr key={m.model} className="hover:bg-gray-800/30 transition">
                                                <td className="py-3 pr-4">
                                                    <span className="font-medium text-white">{m.model}</span>
                                                </td>
                                                <td className="py-3 pr-4 text-right text-gray-300">{m.tasks}</td>
                                                <td className="py-3 pr-4 text-right text-gray-300">{formatTokens(m.tokens)}</td>
                                                <td className="py-3 pr-4 text-right text-gray-300">${m.cost.toFixed(2)}</td>
                                                <td className="py-3 pr-4 text-right text-gray-300">{m.avgDuration}s</td>
                                                <td className="py-3 text-right">
                                                    <span
                                                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${m.successRate >= 0.9
                                                                ? 'bg-green-500/20 text-green-400'
                                                                : m.successRate >= 0.7
                                                                    ? 'bg-yellow-500/20 text-yellow-400'
                                                                    : 'bg-red-500/20 text-red-400'
                                                            }`}
                                                    >
                                                        {(m.successRate * 100).toFixed(0)}%
                                                    </span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* Cost per Model Bar Chart */}
                        <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6">
                            <h3 className="text-sm font-semibold text-gray-300 mb-4">Cost by Model</h3>
                            <ResponsiveContainer width="100%" height={280}>
                                <BarChart data={modelUsage} layout="vertical" margin={{ left: 20 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
                                    <XAxis
                                        type="number"
                                        tick={{ fill: '#6b7280', fontSize: 11 }}
                                        tickFormatter={(v) => `$${v}`}
                                    />
                                    <YAxis
                                        type="category"
                                        dataKey="model"
                                        tick={{ fill: '#d1d5db', fontSize: 12 }}
                                        width={120}
                                    />
                                    <Tooltip
                                        {...chartTooltipStyle}
                                        formatter={(value) => [`$${Number(value ?? 0).toFixed(2)}`, 'Cost']}
                                    />
                                    <Bar dataKey="cost" name="Cost (USD)" radius={[0, 4, 4, 0]}>
                                        {modelUsage.map((_, i) => (
                                            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </>
                )}
            </div>
        </div>
    )
}
