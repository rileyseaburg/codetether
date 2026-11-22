import { useGithubAppWorkflows } from '../GithubAppWorkflowsContext'
import { Badge } from './Badge'
import { JsonCounts } from './JsonCounts'
import { formatDate } from '../utils'

export function WorkflowsTable() {
  const { data, loading } = useGithubAppWorkflows()
  const rows = data?.workflows || []
  return (
    <section className="rounded-3xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 p-5">
        <h2 className="text-lg font-semibold text-slate-950">Workflow groups</h2>
        <p className="mt-1 text-sm text-slate-500">Grouped by repository and GitHub issue/PR identity.</p>
      </div>
      <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-3">
        {rows.map((w, i) => {
          const running = w.running_count || w.status_counts.running || 0
          const pending = w.pending_count || w.status_counts.pending || 0
          const failed = w.failed_count || w.status_counts.failed || 0
          return (
            <article key={`${w.repo}-${w.issue_pr}-${w.url}-${i}`} className="rounded-2xl border border-slate-200 bg-slate-50/60 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0"><div className="truncate font-semibold text-slate-950" title={w.repo}>{w.repo}</div><div className="text-xs text-slate-500">#{w.issue_pr || 'unlinked'}</div></div>
                <Badge value={w.error_class} />
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                <WorkflowCount label="running" value={running} tone="text-sky-700" />
                <WorkflowCount label="queued" value={pending} tone="text-amber-700" />
                <WorkflowCount label="failed" value={failed} tone="text-rose-700" />
              </div>
              <div className="mt-4 space-y-3 text-xs text-slate-600">
                <div><div className="mb-1 font-semibold text-slate-700">Agents</div><JsonCounts counts={w.agent_counts} /></div>
                <div className="flex items-center justify-between gap-3 border-t border-slate-200 pt-3"><span>Updated {formatDate(w.last_update)}</span>{w.url ? <a className="font-semibold text-cyan-700 hover:underline" href={w.url} target="_blank" rel="noreferrer">Open GitHub</a> : null}</div>
                {w.errors ? <div className="truncate rounded-xl bg-white p-2 text-rose-700 ring-1 ring-rose-100" title={w.errors}>{w.errors}</div> : null}
              </div>
            </article>
          )
        })}
        {!loading && !rows.length ? <div className="col-span-full rounded-2xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">No GitHub App workflow groups found.</div> : null}
      </div>
    </section>
  )
}

function WorkflowCount({ label, value, tone }: { label: string; value: number; tone: string }) {
  return <div className="rounded-xl bg-white p-3 ring-1 ring-slate-200"><div className={`text-lg font-bold ${tone}`}>{value}</div><div className="text-[11px] font-medium text-slate-500">{label}</div></div>
}
