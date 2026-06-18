import type { Counts } from '../types'

type Tone = 'slate' | 'amber' | 'rose' | 'sky' | 'emerald'

const statusTone: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-800 ring-amber-200',
  running: 'bg-sky-100 text-sky-800 ring-sky-200',
  failed: 'bg-rose-100 text-rose-800 ring-rose-200',
  completed: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
  queued: 'bg-purple-100 text-purple-800 ring-purple-200',
}

const cardTone: Record<Tone, string> = {
  slate: 'border-slate-200 bg-white text-slate-950',
  amber: 'border-amber-200 bg-gradient-to-br from-amber-50 to-white text-amber-950',
  rose: 'border-rose-200 bg-gradient-to-br from-rose-50 to-white text-rose-950',
  sky: 'border-sky-200 bg-gradient-to-br from-sky-50 to-white text-sky-950',
  emerald: 'border-emerald-200 bg-gradient-to-br from-emerald-50 to-white text-emerald-950',
}

const dotTone: Record<Tone, string> = {
  slate: 'bg-slate-400', amber: 'bg-amber-400', rose: 'bg-rose-400', sky: 'bg-sky-400', emerald: 'bg-emerald-400',
}

export function renderBadge(value?: string) {
  const tone = statusTone[value || ''] || 'bg-slate-100 text-slate-700 ring-slate-200'
  return <span className={`rounded-full px-2 py-1 text-xs font-semibold ring-1 ${tone}`}>{value || 'unknown'}</span>
}

export function renderCounts(counts: Counts) {
  const entries = Object.entries(counts || {}).filter(([, value]) => value)
  if (!entries.length) return <span className="text-slate-400">none</span>
  return <div className="flex flex-wrap gap-2">{entries.map(([key, value]) => <span key={key} className="rounded-lg bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">{key}: {value}</span>)}</div>
}

export function renderCountCard(label: string, value: number, hint?: string, tone: Tone = 'slate') {
  return (
    <div className={`rounded-3xl border p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${cardTone[tone]}`}>
      <div className="flex items-center justify-between gap-3"><div className="text-sm font-semibold text-slate-600">{label}</div><span className={`h-2.5 w-2.5 rounded-full ${dotTone[tone]} ${tone === 'sky' && value > 0 ? 'animate-pulse' : ''}`} /></div>
      <div className="mt-3 text-4xl font-bold tracking-tight">{value.toLocaleString()}</div>
      {hint ? <div className="mt-2 text-xs leading-5 text-slate-500">{hint}</div> : null}
    </div>
  )
}
