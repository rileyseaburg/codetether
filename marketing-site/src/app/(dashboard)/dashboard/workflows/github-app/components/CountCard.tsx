type Tone = 'slate' | 'amber' | 'rose' | 'sky' | 'emerald'

const tones: Record<Tone, string> = {
  slate: 'border-slate-200 bg-white text-slate-900',
  amber: 'border-amber-200 bg-amber-50 text-amber-950',
  rose: 'border-rose-200 bg-rose-50 text-rose-950',
  sky: 'border-sky-200 bg-sky-50 text-sky-950',
  emerald: 'border-emerald-200 bg-emerald-50 text-emerald-950',
}

export function CountCard({
  label, value, hint, tone = 'slate',
}: { label: string; value: number; hint?: string; tone?: Tone }) {
  return (
    <div className={`rounded-2xl border p-5 shadow-sm ${tones[tone]}`}>
      <div className="text-sm font-medium text-slate-500">{label}</div>
      <div className="mt-2 text-4xl font-bold">{value}</div>
      {hint ? <div className="mt-2 text-xs text-slate-500">{hint}</div> : null}
    </div>
  )
}
