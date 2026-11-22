import Link from 'next/link'
import { Badge } from './Badge'
import { runnerLabel, statusCopy } from './taskHelpers'
import type { WorkflowTask } from '../types'

export function ActiveTaskCards({ rows }: { rows: WorkflowTask[] }) {
  if (!rows.length) return null
  return (
    <div className="grid gap-3 border-b border-slate-100 bg-slate-50/70 p-4 md:grid-cols-2 xl:grid-cols-3">
      {rows.slice(0, 6).map((task) => (
        <Link key={task.id} href={`/dashboard/tasks?taskId=${task.id}`} className="group rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-cyan-300 hover:shadow-md">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                {task.status === 'running' ? <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" /> : null}
                <div className="truncate text-sm font-semibold text-slate-950">{task.title || 'Untitled task'}</div>
              </div>
              <div className="mt-1 text-xs text-slate-500">{task.repo} #{task.issue_pr || '-'}</div>
            </div>
            <Badge value={task.status} />
          </div>
          <div className="mt-3 text-xs font-medium text-slate-700">{statusCopy(task.status)}</div>
          <div className="mt-2 truncate text-xs text-slate-500" title={runnerLabel(task)}>
            Runner: {runnerLabel(task)}
          </div>
        </Link>
      ))}
    </div>
  )
}
