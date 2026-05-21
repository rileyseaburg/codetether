const statusTone: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-800 ring-amber-200',
  running: 'bg-sky-100 text-sky-800 ring-sky-200',
  failed: 'bg-rose-100 text-rose-800 ring-rose-200',
  completed: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
  queued: 'bg-purple-100 text-purple-800 ring-purple-200',
}

export function Badge({ value }: { value?: string }) {
  const tone =
    statusTone[value || ''] || 'bg-slate-100 text-slate-700 ring-slate-200'
  return (
    <span className={`rounded-full px-2 py-1 text-xs font-semibold ring-1 ${tone}`}>
      {value || 'unknown'}
    </span>
  )
}
