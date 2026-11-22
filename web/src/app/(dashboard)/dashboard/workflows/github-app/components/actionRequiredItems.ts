import type { GithubAppWorkflowResponse } from '../types'

export type ActionTone = 'rose' | 'amber' | 'sky' | 'emerald'

export interface ActionItem {
  title: string
  detail: string
  count: number
  tone: ActionTone
  cta: string
}

const badRouteStates = new Set([
  'missing_worker',
  'stale_worker',
  'unscoped_or_missing_target',
])
const activeStatuses = new Set(['pending', 'queued', 'running', 'working'])

export const toneClasses: Record<ActionTone, string> = {
  rose: 'border-rose-200 bg-rose-50 text-rose-950',
  amber: 'border-amber-200 bg-amber-50 text-amber-950',
  sky: 'border-sky-200 bg-sky-50 text-sky-950',
  emerald: 'border-emerald-200 bg-emerald-50 text-emerald-950',
}

export const badgeClasses: Record<ActionTone, string> = {
  rose: 'bg-rose-100 text-rose-800 ring-rose-200',
  amber: 'bg-amber-100 text-amber-800 ring-amber-200',
  sky: 'bg-sky-100 text-sky-800 ring-sky-200',
  emerald: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
}

export function buildActionItems(data: GithubAppWorkflowResponse | null) {
  if (!data) return []
  const failed = data.totals?.failed || 0
  const failures = Object.keys(data.failure_classes || {}).length
  const stale = data.workflows.reduce(
    (sum, workflow) => sum + (workflow.stale_pending_count || 0),
    0,
  )
  const badRoutes = Object.entries(data.route_states || {})
    .filter(([state]) => badRouteStates.has(state))
    .reduce((sum, [, count]) => sum + count, 0)
  const unclaimed = data.tasks.filter(
    (task) => activeStatuses.has(task.status) && !task.worker_id,
  ).length
  return [
    stale && item('Stale GitHub work', stale, 'rose', 'Old queued work can create duplicate PRs or surprise customers.', 'Cancel, retry intentionally, or mark ignored'),
    failed && item('Failed automations', failed, 'amber', `${failures || 1} failure classes need triage evidence.`, 'Open failed runs and inspect provenance'),
    (badRoutes || unclaimed) && item('Routing risk', badRoutes + unclaimed, 'sky', 'Tasks may not be attached to a healthy persistent worker.', 'Check worker leases and route targets'),
  ].filter(Boolean).slice(0, 3) as ActionItem[]
}

function item(
  title: string,
  count: number,
  tone: ActionTone,
  detail: string,
  cta: string,
): ActionItem {
  return { title, count, tone, detail, cta }
}
