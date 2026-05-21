import { formatDate } from '../utils'
import type { TetherScriptWorkflowResponse } from '../types'

export function HeaderControls(props: {
  data: TetherScriptWorkflowResponse | null
  repos: string
  setRepos: (value: string) => void
  autoRefresh: boolean
  setAutoRefresh: (value: boolean) => void
  load: () => void
}) {
  return <>
    <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div><div className="text-sm font-semibold uppercase tracking-wide text-cyan-600">Workflow observability</div><h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">TetherScript workflows</h1><p className="mt-2 max-w-3xl text-sm text-slate-600">One pane of glass for GitHub App tasks, task_runs, routing, worker freshness, and retryable failure classes across the TetherScript automation loop.</p></div>
      <div className="flex flex-wrap items-center gap-3"><label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-sm"><input type="checkbox" checked={props.autoRefresh} onChange={(e) => props.setAutoRefresh(e.target.checked)} />Auto-refresh 15s</label><button onClick={props.load} className="rounded-xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-slate-800">Refresh</button></div>
    </div>
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">Repositories</label>
      <div className="mt-2 flex flex-col gap-3 sm:flex-row"><input value={props.repos} onChange={(e) => props.setRepos(e.target.value)} className="flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm focus:border-cyan-500 focus:outline-none focus:ring-2 focus:ring-cyan-100" placeholder="owner/repo,owner/repo" /><button onClick={props.load} className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Apply</button></div>
      {props.data ? <div className="mt-2 text-xs text-slate-500">Last generated {formatDate(props.data.generated_at)}</div> : null}
    </div>
  </>
}
