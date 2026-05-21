import { CountCard } from './CountCard'
import { JsonCounts } from './JsonCounts'
import type { TetherScriptWorkflowResponse } from '../types'

export function SummaryPanels({ data }: { data: TetherScriptWorkflowResponse | null }) {
  const totals = data?.totals || {}
  const active = (totals.pending || 0) + (totals.running || 0) + (totals.failed || 0)
  const hasBadRoutes = Object.keys(data?.route_states || {}).some((k) => k !== 'active_worker')
  return <>
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5"><CountCard label="Active workflow tasks" value={active} hint="pending + running + failed" /><CountCard label="Pending" value={totals.pending || 0} hint="waiting to be claimed" tone="amber" /><CountCard label="Running" value={totals.running || 0} hint="currently leased/active" tone="sky" /><CountCard label="Failed" value={totals.failed || 0} hint="needs triage or retry" tone="rose" /><CountCard label="Open task runs" value={data?.runs.length || 0} hint="non-completed task_run rows" tone="emerald" /></div>
    <div className="grid gap-4 lg:grid-cols-2"><section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-lg font-semibold text-slate-950">Routing health</h2><div className="mt-4"><JsonCounts counts={data?.route_states || {}} /></div>{hasBadRoutes ? <p className="mt-3 text-xs text-amber-700">Watch non-active routes first: missing targets, stale workers, or unscoped pending items are common stuck-queue causes.</p> : null}</section><section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-lg font-semibold text-slate-950">Failure classes</h2><div className="mt-4"><JsonCounts counts={data?.failure_classes || {}} /></div></section></div>
  </>
}
