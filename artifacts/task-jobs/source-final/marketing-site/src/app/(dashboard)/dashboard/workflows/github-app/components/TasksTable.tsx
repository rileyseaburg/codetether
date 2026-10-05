import { useGithubAppWorkflows } from '../GithubAppWorkflowsContext'
import { ActiveTaskCards } from './ActiveTaskCards'
import { TaskRow } from './TaskRow'
import { activeRows } from './taskHelpers'

export function TasksTable() {
  const { data } = useGithubAppWorkflows()
  const rows = data?.tasks || []
  const active = activeRows(rows)
  return (
    <section className="rounded-3xl border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Agent activity</h2>
            <p className="mt-1 text-sm text-slate-500">
              Live GitHub App tasks. Running rows mean a worker has claimed the task and is doing work.
            </p>
          </div>
          <span className="rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold text-sky-800">
            {active.length} active
          </span>
        </div>
      </div>
      <ActiveTaskCards rows={active} />
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-3">Task</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Route</th><th className="px-4 py-3">Runner</th><th className="px-4 py-3">Updated</th><th className="px-4 py-3">Error</th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {rows.map((task) => <TaskRow key={task.id} task={task} />)}
            {!rows.length ? <tr><td colSpan={6} className="px-4 py-8 text-center text-slate-500">No recent GitHub App task rows found.</td></tr> : null}
          </tbody>
        </table>
      </div>
    </section>
  )
}
