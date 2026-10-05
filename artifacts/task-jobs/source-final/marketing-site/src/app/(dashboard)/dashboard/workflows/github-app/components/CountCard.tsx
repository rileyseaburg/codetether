type Tone = 'slate' | 'amber' | 'rose' | 'sky' | 'emerald'

const tones: Record<Tone, string> = {
  slate: 'border-slate-200 bg-white text-slate-950',
  amber: 'border-amber-200 bg-gradient-to-br from-amber-50 to-white text-amber-950',
  rose: 'border-rose-200 bg-gradient-to-br from-rose-50 to-white text-rose-950',
  sky: 'border-sky-200 bg-gradient-to-br from-sky-50 to-white text-sky-950',
  emerald: 'border-emerald-200 bg-gradient-to-br from-emerald-50 to-white text-emerald-950',
}

const dots: Record<Tone, string> = {
  slate: 'bg-slate-400',
  amber: 'bg-amber-400',
  rose: 'bg-rose-400',
  sky: 'bg-sky-400',
  emerald: 'bg-emerald-400',
}

export function CountCard({
  label, value, hint, tone = 'slate',
}: { label: string; value: number; hint?: string; tone?: Tone }) {
  return (
    <div className={`rounded-3xl border p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${tones[tone]}`}>
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-semibold text-slate-600">{label}</div>
        <span className={`h-2.5 w-2.5 rounded-full ${dots[tone]} ${tone === 'sky' && value > 0 ? 'animate-pulse' : ''}`} />
      </div>
      <div className="mt-3 text-4xl font-bold tracking-tight">{value.toLocaleString()}</div>
      {hint ? <div className="mt-2 text-xs leading-5 text-slate-500">{hint}</div> : null}
    </div>
  )
}
