import type { GithubAppWorkflowResponse } from '../types'

export function HeaderHero({ data }: { data: GithubAppWorkflowResponse | null }) {
  const running = data?.totals?.running || 0
  const pending = data?.totals?.pending || 0
  return (
    <div className="bg-gradient-to-br from-slate-950 via-slate-900 to-cyan-950 px-6 py-7 text-white lg:px-8">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/30 bg-cyan-300/10 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-cyan-100">
            <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_0_4px_rgba(52,211,153,0.18)]" />
            GitHub agent control room
          </div>
          <h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">GitHub App workflows</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
            See what the GitHub agents are doing right now: running work, queued jobs,
            routing health, worker leases, and recent failures in one place.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:min-w-[18rem]">
          <HeroStat label="Running now" value={running} pulse={running > 0} />
          <HeroStat label="Queued" value={pending} />
        </div>
      </div>
    </div>
  )
}

function HeroStat({ label, value, pulse = false }: { label: string; value: number; pulse?: boolean }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/10 p-4 backdrop-blur">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-300">{label}</div>
      <div className="mt-2 flex items-end gap-2">
        <span className="text-4xl font-bold">{value}</span>
        {pulse ? <span className="mb-2 flex h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse" /> : null}
      </div>
    </div>
  )
}
