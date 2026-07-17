import { useGithubAppWorkflows } from '../GithubAppWorkflowsContext'
import { HeaderHero } from './HeaderHero'
import { formatDate } from '../utils'

export function HeaderControls() {
  const { data, repos, setRepos, autoRefresh, setAutoRefresh, load } = useGithubAppWorkflows()
  return (
    <div className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm">
      <HeaderHero data={data} />
      <div className="grid gap-4 p-4 lg:grid-cols-[1fr_auto] lg:items-end lg:p-5">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">
            Repository filter
          </label>
          <div className="mt-2 flex flex-col gap-3 sm:flex-row">
            <input
              value={repos}
              onChange={(e) => setRepos(e.target.value)}
              className="min-h-11 flex-1 rounded-2xl border border-slate-300 bg-slate-50 px-4 py-2 text-sm text-slate-900 outline-none transition focus:border-cyan-500 focus:bg-white focus:ring-4 focus:ring-cyan-100"
              placeholder="owner/repo, owner/repo"
            />
            <button onClick={load} className="min-h-11 rounded-2xl border border-slate-300 bg-white px-5 py-2 text-sm font-semibold text-slate-800 shadow-sm transition hover:bg-slate-50">
              Apply
            </button>
          </div>
          {data ? <div className="mt-2 text-xs text-slate-500">Last generated {formatDate(data.generated_at)}</div> : null}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="inline-flex min-h-11 items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm font-medium text-slate-700">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-cyan-600 focus:ring-cyan-500"
            />
            Auto-refresh 15s
          </label>
          <button onClick={load} className="min-h-11 rounded-2xl bg-slate-950 px-5 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800">
            Refresh now
          </button>
        </div>
      </div>
    </div>
  )
}
