import { useGithubAppWorkflows } from '../GithubAppWorkflowsContext'
import { Badge } from './Badge'
import { formatDate } from '../utils'

export function RunsTable() {
  const { data, loading } = useGithubAppWorkflows()
  const rows = data?.runs || []
  return (
    <section className="rounded-3xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 p-5">
        <h2 className="text-lg font-semibold text-slate-950">Recent task runs</h2>
        <p className="mt-1 text-sm text-slate-500">
          Latest task_run rows, including completed runs and their lease owner.
        </p>
      </div>
      <div className="divide-y divide-slate-100">
        {rows.map((run) => (
          <article key={run.run_id} className="grid gap-4 p-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge value={run.status} />
                <span className="font-mono text-xs font-semibold text-slate-700">{run.run_id}</span>
              </div>
              <div className="mt-2 text-sm font-medium text-slate-900">{run.repo} #{run.issue_pr || '-'}</div>
              <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                <span>Lease: {run.lease_owner || '-'}</span>
                <span>Expires: {formatDate(run.lease_expires_at)}</span>
                <span>Completed: {formatDate(run.completed_at)}</span>
              </div>
              {run.last_error ? <div className="mt-3 truncate rounded-2xl bg-rose-50 px-3 py-2 text-xs text-rose-700 ring-1 ring-rose-100" title={run.last_error}>{run.last_error}</div> : null}
            </div>
            <div className="justify-self-start md:justify-self-end"><Badge value={run.error_class} /></div>
          </article>
        ))}
        {!loading && !rows.length ? <div className="px-4 py-8 text-center text-sm text-slate-500">No recent task_run rows found.</div> : null}
      </div>
    </section>
  )
}
