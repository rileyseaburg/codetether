import type { Counts } from '../types'

export function JsonCounts({ counts }: { counts: Counts }) {
  const entries = Object.entries(counts || {}).filter(([, value]) => value)
  if (!entries.length) return <span className="text-slate-400">none</span>
  return (
    <div className="flex flex-wrap gap-2">
      {entries.map(([key, value]) => (
        <span
          key={key}
          className="rounded-lg bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700"
        >
          {key}: {value}
        </span>
      ))}
    </div>
  )
}
