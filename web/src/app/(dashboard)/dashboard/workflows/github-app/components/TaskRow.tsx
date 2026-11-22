import Link from 'next/link'
import { Badge } from './Badge'
import { formatDate } from '../utils'
import { runnerDetail, runnerLabel, statusCopy } from './taskHelpers'
import type { WorkflowTask } from '../types'

export function TaskRow({ task }: { task: WorkflowTask }) {
  const evidenceLinks = evidenceForTask(task)
  return (
    <tr className={`align-top ${task.status === 'running' ? 'bg-sky-50/40' : ''}`}>
      <td className="px-4 py-4">
        <Link href={`/dashboard/tasks?taskId=${task.id}`} className="font-mono text-xs font-semibold text-cyan-700 hover:underline">
          {task.id}
        </Link>
        <div className="mt-1 max-w-xs truncate font-medium text-slate-800" title={task.title}>{task.title || 'Untitled task'}</div>
        <div className="text-xs text-slate-500">{task.repo} #{task.issue_pr || '-'} · {task.agent_type}</div>
        {evidenceLinks.length ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {evidenceLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                target="_blank"
                rel="noreferrer"
                className="rounded-full bg-cyan-50 px-2.5 py-1 text-[11px] font-semibold text-cyan-700 ring-1 ring-cyan-100 hover:bg-cyan-100"
              >
                {link.label}
              </a>
            ))}
          </div>
        ) : null}
      </td>
      <td className="px-4 py-4">
        <div className="space-y-2"><Badge value={task.status} /><div className="text-xs text-slate-500">{statusCopy(task.status)}</div></div>
      </td>
      <td className="px-4 py-4"><Badge value={task.route_state} /></td>
      <td className="px-4 py-4 text-xs text-slate-600">
        <div className="max-w-xs truncate font-medium" title={runnerLabel(task)}>{runnerLabel(task)}</div>
        <div className="max-w-xs truncate" title={runnerDetail(task)}>{runnerDetail(task)}</div>
      </td>
      <td className="px-4 py-4 text-xs text-slate-600">{formatDate(task.updated_at)}</td>
      <td className="px-4 py-4">
        <Badge value={task.error_class} />
        {task.error ? <div className="mt-2 max-w-sm truncate text-xs text-slate-500" title={task.error}>{task.error}</div> : null}
      </td>
    </tr>
  )
}

function evidenceForTask(task: WorkflowTask) {
  const links: Array<{ label: string; href: string }> = []
  const githubUrl = task.pr_url || task.url
  if (githubUrl) links.push({ label: 'Open PR', href: githubUrl })
  if (task.evidence_url) links.push({ label: 'Evidence', href: task.evidence_url })
  if (task.session_id) {
    links.push({
      label: 'Agent session',
      href: `/dashboard/tasks?sessionId=${task.session_id}`,
    })
  }
  return links
}
