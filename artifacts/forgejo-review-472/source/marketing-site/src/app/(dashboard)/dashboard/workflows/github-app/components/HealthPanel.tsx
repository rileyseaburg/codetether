import { JsonCounts } from './JsonCounts'

type Props = {
  title: string
  description: string
  counts: Record<string, number>
  badge: string
  tone?: 'good' | 'warn' | 'neutral'
  note?: string
}

const badgeTone = {
  good: 'bg-emerald-100 text-emerald-800',
  warn: 'bg-amber-100 text-amber-800',
  neutral: 'bg-slate-100 text-slate-700',
}

export function HealthPanel({ title, description, counts, badge, tone = 'neutral', note }: Props) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">{title}</h2>
          <p className="mt-1 text-sm text-slate-500">{description}</p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${badgeTone[tone]}`}>{badge}</span>
      </div>
      <div className="mt-4">
        <JsonCounts counts={counts} />
      </div>
      {note ? <p className="mt-3 rounded-2xl bg-amber-50 p-3 text-xs leading-5 text-amber-800">{note}</p> : null}
    </section>
  )
}
