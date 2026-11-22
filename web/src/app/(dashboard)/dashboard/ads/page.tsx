'use client'

import { useState, useEffect, useCallback } from 'react'
import {
    BarChart, Bar, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
    ResponsiveContainer, Cell, PieChart, Pie, Legend,
} from 'recharts'

// ─── Types ──────────────────────────────────────────────────────────────────

interface FacebookAccount {
    id: string
    account_id: string
    name: string
    currency: string
    account_status: number
}

interface CampaignInsights {
    impressions?: string
    clicks?: string
    spend?: string
    cpc?: string
    cpm?: string
    ctr?: string
    actions?: Array<{ action_type: string; value: string }>
    video_thruplay_watched_actions?: Array<{ action_type: string; value: string }>
    cost_per_thruplay?: Array<{ action_type: string; value: string }>
}

interface Campaign {
    id: string
    name: string
    status: string
    objective: string
    daily_budget?: string
    lifetime_budget?: string
    insights: CampaignInsights | null
}

interface DashboardData {
    account: FacebookAccount | null
    campaigns: Campaign[]
    totals: {
        impressions: number
        clicks: number
        spend: number
        ctr: string
        campaignCount: number
        activeCampaigns: number
    }
}

interface LaunchFormState {
    videoUrl: string
    campaignName: string
    dailyBudget: number
    headline: string
    message: string
    landingUrl: string
    ctaType: string
}

type Tab = 'overview' | 'campaigns' | 'launch'

// ─── Chart Colors ───────────────────────────────────────────────────────────

const COLORS = {
    blue: '#3b82f6',
    cyan: '#06b6d4',
    purple: '#8b5cf6',
    amber: '#f59e0b',
    green: '#10b981',
    red: '#ef4444',
    pink: '#ec4899',
}

const PIE_COLORS = [COLORS.cyan, COLORS.purple, COLORS.amber, COLORS.green, COLORS.pink, COLORS.blue]

const tooltipStyle = {
    contentStyle: {
        backgroundColor: '#1f2937',
        border: '1px solid #374151',
        borderRadius: '0.5rem',
        fontSize: '12px',
    },
    labelStyle: { color: '#9ca3af' },
    itemStyle: { color: '#e5e7eb' },
}

// ─── Icons ──────────────────────────────────────────────────────────────────

function FacebookIcon({ className }: { className?: string }) {
    return (
        <svg className={className} viewBox="0 0 24 24" fill="currentColor">
            <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
        </svg>
    )
}

function PlayIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    )
}

function PauseIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
    )
}

function TrashIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
        </svg>
    )
}

function RocketIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.59 14.37a6 6 0 01-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 006.16-12.12A14.98 14.98 0 009.631 8.41m5.96 5.96a14.926 14.926 0 01-5.841 2.58m-.119-8.54a6 6 0 00-7.381 5.84h4.8m2.581-5.84a14.927 14.927 0 00-2.58 5.84m2.699 2.7c-.103.021-.207.041-.311.06a15.09 15.09 0 01-2.448-2.448 14.9 14.9 0 01.06-.312m-2.24 2.39a4.493 4.493 0 00-1.757 4.306 4.493 4.493 0 004.306-1.758M16.5 9a1.5 1.5 0 11-3 0 1.5 1.5 0 013 0z" />
        </svg>
    )
}

function RefreshIcon({ className }: { className?: string }) {
    return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
    )
}

// ─── MetricCard ─────────────────────────────────────────────────────────────

function MetricCard({
    label, value, sub, icon, color = 'cyan',
}: {
    label: string
    value: string
    sub?: string
    icon: React.ReactNode
    color?: 'cyan' | 'purple' | 'amber' | 'green' | 'red' | 'blue'
}) {
    const colorMap = {
        cyan: 'bg-cyan-500/10 text-cyan-400',
        purple: 'bg-purple-500/10 text-purple-400',
        amber: 'bg-amber-500/10 text-amber-400',
        green: 'bg-green-500/10 text-green-400',
        red: 'bg-red-500/10 text-red-400',
        blue: 'bg-blue-500/10 text-blue-400',
    }

    return (
        <div className="rounded-xl bg-gray-900 border border-gray-800 p-5">
            <div className="flex items-center gap-3">
                <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${colorMap[color]}`}>
                    {icon}
                </div>
                <div className="min-w-0 flex-1">
                    <p className="text-2xl font-bold text-white truncate">{value}</p>
                    <p className="text-sm text-gray-400">{label}</p>
                </div>
            </div>
            {sub && <p className="text-xs text-gray-500 mt-2">{sub}</p>}
        </div>
    )
}

// ─── Status Badge ───────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
    const map: Record<string, string> = {
        ACTIVE: 'bg-green-500/20 text-green-400',
        PAUSED: 'bg-yellow-500/20 text-yellow-400',
        DELETED: 'bg-red-500/20 text-red-400',
        ARCHIVED: 'bg-gray-500/20 text-gray-400',
    }
    return (
        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${map[status] ?? 'bg-gray-500/20 text-gray-400'}`}>
            <span className={`mr-1.5 h-1.5 w-1.5 rounded-full ${status === 'ACTIVE' ? 'bg-green-400 animate-pulse' :
                    status === 'PAUSED' ? 'bg-yellow-400' : 'bg-gray-400'
                }`} />
            {status}
        </span>
    )
}

// ─── Campaigns Table ────────────────────────────────────────────────────────

function CampaignsTable({
    campaigns, onAction, actionLoading,
}: {
    campaigns: Campaign[]
    onAction: (action: string, campaignId: string) => void
    actionLoading: string | null
}) {
    return (
        <div className="rounded-2xl bg-gray-900 border border-gray-800 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-800">
                <h3 className="text-sm font-semibold text-gray-300">Campaigns</h3>
                <p className="text-xs text-gray-500 mt-0.5">{campaigns.length} total campaigns</p>
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-gray-800 text-left">
                            <th className="px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Campaign</th>
                            <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Status</th>
                            <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Objective</th>
                            <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">Impressions</th>
                            <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">Clicks</th>
                            <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">CTR</th>
                            <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">Spend</th>
                            <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800/50">
                        {campaigns.length === 0 && (
                            <tr>
                                <td colSpan={8} className="px-6 py-12 text-center text-gray-500">
                                    No campaigns found. Launch your first video ad below.
                                </td>
                            </tr>
                        )}
                        {campaigns.map((c) => {
                            const ins = c.insights
                            const impressions = Number(ins?.impressions ?? 0)
                            const clicks = Number(ins?.clicks ?? 0)
                            const spend = parseFloat(String(ins?.spend ?? '0'))
                            const ctr = ins?.ctr ?? (impressions > 0 ? ((clicks / impressions) * 100).toFixed(2) : '0')
                            const isLoading = actionLoading === c.id

                            return (
                                <tr key={c.id} className="hover:bg-gray-800/30 transition">
                                    <td className="px-6 py-3">
                                        <div>
                                            <p className="font-medium text-white truncate max-w-[240px]">{c.name}</p>
                                            <p className="text-xs text-gray-500 mt-0.5">ID: {c.id}</p>
                                        </div>
                                    </td>
                                    <td className="px-4 py-3"><StatusBadge status={c.status} /></td>
                                    <td className="px-4 py-3">
                                        <span className="text-xs text-gray-400 bg-gray-800 px-2 py-1 rounded">
                                            {c.objective.replace('OUTCOME_', '')}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-right text-gray-300 font-mono text-xs">
                                        {impressions.toLocaleString()}
                                    </td>
                                    <td className="px-4 py-3 text-right text-gray-300 font-mono text-xs">
                                        {clicks.toLocaleString()}
                                    </td>
                                    <td className="px-4 py-3 text-right text-gray-300 font-mono text-xs">{ctr}%</td>
                                    <td className="px-4 py-3 text-right text-gray-300 font-mono text-xs">${spend.toFixed(2)}</td>
                                    <td className="px-4 py-3 text-right">
                                        <div className="flex items-center justify-end gap-1">
                                            {c.status === 'PAUSED' && (
                                                <button
                                                    onClick={() => onAction('activate', c.id)}
                                                    disabled={isLoading}
                                                    className="p-1.5 rounded-lg hover:bg-green-500/20 text-green-400 transition disabled:opacity-50"
                                                    title="Activate"
                                                >
                                                    <PlayIcon className="h-4 w-4" />
                                                </button>
                                            )}
                                            {c.status === 'ACTIVE' && (
                                                <button
                                                    onClick={() => onAction('pause', c.id)}
                                                    disabled={isLoading}
                                                    className="p-1.5 rounded-lg hover:bg-yellow-500/20 text-yellow-400 transition disabled:opacity-50"
                                                    title="Pause"
                                                >
                                                    <PauseIcon className="h-4 w-4" />
                                                </button>
                                            )}
                                            {c.status !== 'DELETED' && (
                                                <button
                                                    onClick={() => onAction('delete', c.id)}
                                                    disabled={isLoading}
                                                    className="p-1.5 rounded-lg hover:bg-red-500/20 text-red-400 transition disabled:opacity-50"
                                                    title="Delete"
                                                >
                                                    <TrashIcon className="h-4 w-4" />
                                                </button>
                                            )}
                                            {isLoading && (
                                                <div className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-500 border-t-transparent" />
                                            )}
                                        </div>
                                    </td>
                                </tr>
                            )
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

// ─── Launch Form ────────────────────────────────────────────────────────────

function LaunchVideoAdForm({
    onLaunch, isLaunching,
}: {
    onLaunch: (form: LaunchFormState) => void
    isLaunching: boolean
}) {
    const [form, setForm] = useState<LaunchFormState>({
        videoUrl: '',
        campaignName: `CodeTether Video ${new Date().toISOString().split('T')[0]}`,
        dailyBudget: 25,
        headline: 'AI Agents That Actually Deliver',
        message: 'Stop babysitting ChatGPT. CodeTether runs AI tasks in the background and delivers real files — CSV, PDF, code.',
        landingUrl: 'https://codetether.run',
        ctaType: 'LEARN_MORE',
    })

    const update = (key: keyof LaunchFormState, value: string | number) =>
        setForm((prev) => ({ ...prev, [key]: value }))

    return (
        <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6">
            <div className="flex items-center gap-3 mb-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/10">
                    <RocketIcon className="h-5 w-5 text-blue-400" />
                </div>
                <div>
                    <h3 className="text-sm font-semibold text-white">Launch Video Ad</h3>
                    <p className="text-xs text-gray-500">Upload a video and create a Facebook campaign</p>
                </div>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
                {/* Video URL */}
                <div className="sm:col-span-2">
                    <label className="block text-xs font-medium text-gray-400 mb-1.5">Video URL *</label>
                    <input
                        type="url"
                        value={form.videoUrl}
                        onChange={(e) => update('videoUrl', e.target.value)}
                        placeholder="https://cdn.creatify.ai/..."
                        className="w-full rounded-lg bg-gray-800 border border-gray-700 px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition"
                    />
                </div>

                {/* Campaign Name */}
                <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1.5">Campaign Name</label>
                    <input
                        type="text"
                        value={form.campaignName}
                        onChange={(e) => update('campaignName', e.target.value)}
                        className="w-full rounded-lg bg-gray-800 border border-gray-700 px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition"
                    />
                </div>

                {/* Daily Budget */}
                <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1.5">Daily Budget ($)</label>
                    <input
                        type="number"
                        min={1}
                        value={form.dailyBudget}
                        onChange={(e) => update('dailyBudget', parseInt(e.target.value) || 1)}
                        className="w-full rounded-lg bg-gray-800 border border-gray-700 px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition"
                    />
                </div>

                {/* Headline */}
                <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1.5">Headline</label>
                    <input
                        type="text"
                        value={form.headline}
                        onChange={(e) => update('headline', e.target.value)}
                        className="w-full rounded-lg bg-gray-800 border border-gray-700 px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition"
                    />
                </div>

                {/* Landing URL */}
                <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1.5">Landing URL</label>
                    <input
                        type="url"
                        value={form.landingUrl}
                        onChange={(e) => update('landingUrl', e.target.value)}
                        className="w-full rounded-lg bg-gray-800 border border-gray-700 px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition"
                    />
                </div>

                {/* CTA Type */}
                <div>
                    <label className="block text-xs font-medium text-gray-400 mb-1.5">CTA Button</label>
                    <select
                        value={form.ctaType}
                        onChange={(e) => update('ctaType', e.target.value)}
                        className="w-full rounded-lg bg-gray-800 border border-gray-700 px-4 py-2.5 text-sm text-white focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition"
                    >
                        <option value="LEARN_MORE">Learn More</option>
                        <option value="SIGN_UP">Sign Up</option>
                        <option value="GET_STARTED">Get Started</option>
                        <option value="TRY_IT">Try It Now</option>
                        <option value="WATCH_MORE">Watch More</option>
                    </select>
                </div>

                {/* Ad Message */}
                <div className="sm:col-span-2">
                    <label className="block text-xs font-medium text-gray-400 mb-1.5">Ad Message</label>
                    <textarea
                        rows={3}
                        value={form.message}
                        onChange={(e) => update('message', e.target.value)}
                        className="w-full rounded-lg bg-gray-800 border border-gray-700 px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 outline-none transition resize-none"
                    />
                </div>
            </div>

            {/* Info Box */}
            <div className="mt-5 rounded-lg bg-blue-500/5 border border-blue-500/20 px-4 py-3">
                <p className="text-xs text-blue-300">
                    <strong>Note:</strong> Campaign will be created as <strong>PAUSED</strong>. Review it in Facebook Ads Manager before activating.
                    Budget: ${form.dailyBudget}/day. Targeting: US, ages 25-55, tech/developer interests.
                </p>
            </div>

            <div className="mt-5 flex justify-end">
                <button
                    onClick={() => onLaunch(form)}
                    disabled={!form.videoUrl || isLaunching}
                    className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition"
                >
                    {isLaunching ? (
                        <>
                            <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                            Launching...
                        </>
                    ) : (
                        <>
                            <RocketIcon className="h-4 w-4" />
                            Launch Campaign
                        </>
                    )}
                </button>
            </div>
        </div>
    )
}

// ─── Charts ─────────────────────────────────────────────────────────────────

function CampaignSpendChart({ campaigns }: { campaigns: Campaign[] }) {
    const data = campaigns
        .filter((c) => c.insights && parseFloat(String(c.insights.spend ?? '0')) > 0)
        .map((c) => ({
            name: c.name.length > 25 ? c.name.slice(0, 25) + '...' : c.name,
            spend: parseFloat(String(c.insights!.spend ?? '0')),
            clicks: Number(c.insights!.clicks ?? 0),
        }))
        .sort((a, b) => b.spend - a.spend)
        .slice(0, 8)

    if (data.length === 0) {
        return (
            <div className="flex items-center justify-center h-[260px] text-gray-500 text-sm">
                No spend data yet
            </div>
        )
    }

    return (
        <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data} layout="vertical" margin={{ left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
                <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
                <YAxis type="category" dataKey="name" tick={{ fill: '#d1d5db', fontSize: 11 }} width={160} />
                <Tooltip {...tooltipStyle} formatter={(value) => [`$${Number(value ?? 0).toFixed(2)}`, 'Spend']} />
                <Bar dataKey="spend" name="Spend" radius={[0, 4, 4, 0]}>
                    {data.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                </Bar>
            </BarChart>
        </ResponsiveContainer>
    )
}

function ObjectiveDistribution({ campaigns }: { campaigns: Campaign[] }) {
    const counts: Record<string, number> = {}
    campaigns.forEach((c) => {
        const obj = c.objective.replace('OUTCOME_', '')
        counts[obj] = (counts[obj] || 0) + 1
    })
    const data = Object.entries(counts)
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => b.value - a.value)

    if (data.length === 0) {
        return (
            <div className="flex items-center justify-center h-[260px] text-gray-500 text-sm">
                No campaigns
            </div>
        )
    }

    return (
        <div className="flex items-center gap-4">
            <ResponsiveContainer width="55%" height={240}>
                <PieChart>
                    <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={85} innerRadius={50} strokeWidth={0}>
                        {data.map((_, i) => (
                            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                        ))}
                    </Pie>
                    <Tooltip {...tooltipStyle} />
                </PieChart>
            </ResponsiveContainer>
            <div className="flex-1 space-y-2">
                {data.map((entry, i) => {
                    const total = data.reduce((s, e) => s + e.value, 0)
                    const pct = total > 0 ? ((entry.value / total) * 100).toFixed(0) : '0'
                    return (
                        <div key={entry.name} className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-2">
                                <span className="h-3 w-3 rounded-sm" style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }} />
                                <span className="text-gray-300 text-xs">{entry.name}</span>
                            </div>
                            <span className="text-gray-500 text-xs">{pct}%</span>
                        </div>
                    )
                })}
            </div>
        </div>
    )
}

function StatusDistribution({ campaigns }: { campaigns: Campaign[] }) {
    const statusCounts = campaigns.reduce((acc, c) => {
        acc[c.status] = (acc[c.status] || 0) + 1
        return acc
    }, {} as Record<string, number>)

    const statusColorMap: Record<string, string> = {
        ACTIVE: COLORS.green,
        PAUSED: COLORS.amber,
        DELETED: COLORS.red,
        ARCHIVED: '#6b7280',
    }

    return (
        <div className="flex items-center gap-4 flex-wrap">
            {Object.entries(statusCounts).map(([status, count]) => (
                <div key={status} className="flex items-center gap-2">
                    <span className="h-3 w-3 rounded-full" style={{ backgroundColor: statusColorMap[status] ?? '#6b7280' }} />
                    <span className="text-sm text-gray-300">{status}</span>
                    <span className="text-sm font-bold text-white">{count}</span>
                </div>
            ))}
        </div>
    )
}

// ─── Main Page ──────────────────────────────────────────────────────────────

export default function AdsPage() {
    const [data, setData] = useState<DashboardData | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [tab, setTab] = useState<Tab>('overview')
    const [actionLoading, setActionLoading] = useState<string | null>(null)
    const [isLaunching, setIsLaunching] = useState(false)
    const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)

    const showToast = (message: string, type: 'success' | 'error' = 'success') => {
        setToast({ message, type })
        setTimeout(() => setToast(null), 5000)
    }

    const loadData = useCallback(async () => {
        try {
            setLoading(true)
            setError(null)
            const res = await fetch('/api/facebook/dashboard')
            if (!res.ok) {
                const body = await res.json().catch(() => ({}))
                throw new Error((body as { error?: string }).error ?? `HTTP ${res.status}`)
            }
            const json = await res.json()
            setData(json as DashboardData)
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load')
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        loadData()
    }, [loadData])

    const handleCampaignAction = async (action: string, campaignId: string) => {
        if (action === 'delete' && !confirm('Delete this campaign? This cannot be undone.')) return

        setActionLoading(campaignId)
        try {
            const res = await fetch('/api/facebook/dashboard', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action, campaignId }),
            })
            const body = await res.json()
            if (!res.ok) throw new Error((body as { error?: string }).error ?? 'Failed')
            showToast(`Campaign ${action}d successfully`)
            loadData()
        } catch (e) {
            showToast(e instanceof Error ? e.message : 'Action failed', 'error')
        } finally {
            setActionLoading(null)
        }
    }

    const handleLaunch = async (form: LaunchFormState) => {
        setIsLaunching(true)
        try {
            const res = await fetch('/api/facebook/dashboard', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action: 'launch',
                    videoUrl: form.videoUrl,
                    campaignName: form.campaignName,
                    dailyBudgetDollars: form.dailyBudget,
                    headline: form.headline,
                    message: form.message,
                    landingUrl: form.landingUrl,
                    ctaType: form.ctaType,
                }),
            })
            const body = await res.json()
            if (!res.ok) throw new Error((body as { error?: string }).error ?? 'Launch failed')
            showToast('Video ad campaign launched successfully! Created as PAUSED.')
            setTab('campaigns')
            loadData()
        } catch (e) {
            showToast(e instanceof Error ? e.message : 'Launch failed', 'error')
        } finally {
            setIsLaunching(false)
        }
    }

    const tabs: { id: Tab; label: string }[] = [
        { id: 'overview', label: 'Overview' },
        { id: 'campaigns', label: 'Campaigns' },
        { id: 'launch', label: 'Launch Ad' },
    ]

    return (
        <div className="min-h-screen bg-gray-950 text-white p-4 sm:p-6">
            <div className="max-w-7xl mx-auto">
                {/* Toast */}
                {toast && (
                    <div className={`fixed top-4 right-4 z-50 rounded-lg px-4 py-3 text-sm font-medium shadow-lg transition-all ${toast.type === 'success' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'
                        }`}>
                        {toast.message}
                    </div>
                )}

                {/* Header */}
                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-6">
                    <div className="flex items-center gap-3">
                        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-600">
                            <FacebookIcon className="h-6 w-6 text-white" />
                        </div>
                        <div>
                            <h1 className="text-2xl font-bold">Facebook Ads</h1>
                            <p className="text-sm text-gray-400">
                                {data?.account ? `${data.account.name} · ${data.account.currency}` : 'Video ad campaign management'}
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={loadData}
                        disabled={loading}
                        className="inline-flex items-center gap-2 rounded-lg bg-gray-800 border border-gray-700 px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 hover:text-white disabled:opacity-50 transition"
                    >
                        <RefreshIcon className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex gap-1 rounded-lg bg-gray-900 border border-gray-800 p-1 mb-6 w-fit">
                    {tabs.map((t) => (
                        <button
                            key={t.id}
                            onClick={() => setTab(t.id)}
                            className={`rounded-md px-4 py-2 text-sm font-medium transition ${tab === t.id
                                    ? 'bg-blue-600 text-white'
                                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                                }`}
                        >
                            {t.label}
                        </button>
                    ))}
                </div>

                {/* Error State */}
                {error && (
                    <div className="rounded-xl bg-red-500/10 border border-red-500/20 p-4 mb-6">
                        <div className="flex items-center gap-2">
                            <svg className="h-5 w-5 text-red-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                            </svg>
                            <div>
                                <p className="text-sm font-medium text-red-400">Failed to load Facebook Ads data</p>
                                <p className="text-xs text-red-300/70 mt-0.5">{error}</p>
                            </div>
                        </div>
                        <p className="text-xs text-red-300/50 mt-2">
                            Make sure FACEBOOK_ACCESS_TOKEN, FACEBOOK_AD_ACCOUNT_ID, and FACEBOOK_PAGE_ID environment variables are set.
                        </p>
                    </div>
                )}

                {/* Loading State */}
                {loading && !data ? (
                    <div className="flex items-center justify-center h-64">
                        <div className="text-center">
                            <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent mx-auto" />
                            <p className="text-sm text-gray-500 mt-3">Connecting to Facebook...</p>
                        </div>
                    </div>
                ) : data ? (
                    <>
                        {/* ═════════════ OVERVIEW TAB ═════════════ */}
                        {tab === 'overview' && (
                            <>
                                {/* KPI Cards */}
                                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6 mb-6">
                                    <MetricCard
                                        label="Campaigns"
                                        value={String(data.totals.campaignCount)}
                                        sub={`${data.totals.activeCampaigns} active`}
                                        icon={<FacebookIcon className="h-5 w-5" />}
                                        color="blue"
                                    />
                                    <MetricCard
                                        label="Impressions"
                                        value={data.totals.impressions.toLocaleString()}
                                        icon={
                                            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                            </svg>
                                        }
                                        color="cyan"
                                    />
                                    <MetricCard
                                        label="Clicks"
                                        value={data.totals.clicks.toLocaleString()}
                                        icon={
                                            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
                                            </svg>
                                        }
                                        color="purple"
                                    />
                                    <MetricCard
                                        label="CTR"
                                        value={`${data.totals.ctr}%`}
                                        icon={
                                            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                                            </svg>
                                        }
                                        color="green"
                                    />
                                    <MetricCard
                                        label="Total Spend"
                                        value={`$${data.totals.spend.toFixed(2)}`}
                                        icon={
                                            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                            </svg>
                                        }
                                        color="amber"
                                    />
                                    <MetricCard
                                        label="Account"
                                        value={data.account ? 'Active' : 'N/A'}
                                        sub={data.account?.name}
                                        icon={
                                            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                                            </svg>
                                        }
                                        color={data.account ? 'green' : 'red'}
                                    />
                                </div>

                                {/* Campaign Status Bar */}
                                <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6 mb-6">
                                    <h3 className="text-sm font-semibold text-gray-300 mb-4">Campaign Status</h3>
                                    <StatusDistribution campaigns={data.campaigns} />
                                </div>

                                {/* Charts */}
                                <div className="grid gap-6 lg:grid-cols-2 mb-6">
                                    <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6">
                                        <h3 className="text-sm font-semibold text-gray-300 mb-4">Spend by Campaign</h3>
                                        <CampaignSpendChart campaigns={data.campaigns} />
                                    </div>
                                    <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6">
                                        <h3 className="text-sm font-semibold text-gray-300 mb-4">Objective Distribution</h3>
                                        <ObjectiveDistribution campaigns={data.campaigns} />
                                    </div>
                                </div>

                                {/* Top Campaigns Mini-table */}
                                <div className="rounded-2xl bg-gray-900 border border-gray-800 p-6">
                                    <div className="flex items-center justify-between mb-4">
                                        <h3 className="text-sm font-semibold text-gray-300">Top Campaigns by Spend</h3>
                                        <button
                                            onClick={() => setTab('campaigns')}
                                            className="text-xs text-cyan-400 hover:text-cyan-300 transition"
                                        >
                                            View all →
                                        </button>
                                    </div>
                                    <div className="space-y-3">
                                        {data.campaigns
                                            .filter((c) => c.insights)
                                            .sort((a, b) => parseFloat(String(b.insights?.spend ?? '0')) - parseFloat(String(a.insights?.spend ?? '0')))
                                            .slice(0, 5)
                                            .map((c) => {
                                                const spend = parseFloat(String(c.insights?.spend ?? '0'))
                                                const impressions = Number(c.insights?.impressions ?? 0)
                                                const maxSpend = Math.max(...data!.campaigns.map((cc) => parseFloat(String(cc.insights?.spend ?? '0'))), 1)
                                                return (
                                                    <div key={c.id} className="flex items-center gap-3">
                                                        <StatusBadge status={c.status} />
                                                        <div className="flex-1 min-w-0">
                                                            <p className="text-sm text-white truncate">{c.name}</p>
                                                            <div className="mt-1 h-1.5 rounded-full bg-gray-800 overflow-hidden">
                                                                <div
                                                                    className="h-full rounded-full bg-gradient-to-r from-blue-500 to-cyan-400"
                                                                    style={{ width: `${(spend / maxSpend) * 100}%` }}
                                                                />
                                                            </div>
                                                        </div>
                                                        <div className="text-right shrink-0">
                                                            <p className="text-sm font-medium text-white">${spend.toFixed(2)}</p>
                                                            <p className="text-xs text-gray-500">{impressions.toLocaleString()} imp</p>
                                                        </div>
                                                    </div>
                                                )
                                            })}
                                        {data.campaigns.filter((c) => c.insights && parseFloat(String(c.insights.spend ?? '0')) > 0).length === 0 && (
                                            <p className="text-sm text-gray-500 text-center py-4">No campaigns with spend data yet</p>
                                        )}
                                    </div>
                                </div>
                            </>
                        )}

                        {/* ═════════════ CAMPAIGNS TAB ═════════════ */}
                        {tab === 'campaigns' && (
                            <CampaignsTable
                                campaigns={data.campaigns}
                                onAction={handleCampaignAction}
                                actionLoading={actionLoading}
                            />
                        )}

                        {/* ═════════════ LAUNCH TAB ═════════════ */}
                        {tab === 'launch' && (
                            <LaunchVideoAdForm onLaunch={handleLaunch} isLaunching={isLaunching} />
                        )}
                    </>
                ) : null}
            </div>
        </div>
    )
}
