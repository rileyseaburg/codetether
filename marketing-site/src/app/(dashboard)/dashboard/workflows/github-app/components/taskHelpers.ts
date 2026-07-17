import { formatDate } from '../utils'
import type { WorkflowTask } from '../types'

export function runnerLabel(task: WorkflowTask): string {
  return task.worker_name || task.target_agent_name || task.target_worker_id || task.worker_id || '-'
}

export function runnerDetail(task: WorkflowTask): string {
  const details = []
  if (task.worker_status) details.push(task.worker_status)
  if (task.worker_last_seen) details.push(`seen ${formatDate(task.worker_last_seen)}`)
  if (!task.worker_name && task.target_agent_name) details.push('target agent')
  if (task.target_worker_id && task.target_worker_id !== task.worker_id) details.push(task.target_worker_id)
  return details.length ? details.join(' · ') : '-'
}

export function statusCopy(status: string) {
  if (status === 'running') return 'Agent is actively working'
  if (status === 'pending' || status === 'queued') return 'Waiting for a worker'
  if (status === 'failed') return 'Needs retry or triage'
  if (status === 'completed') return 'Finished'
  return status || 'Unknown state'
}

export function activeRows(rows: WorkflowTask[]) {
  return rows.filter((task) => ['running', 'pending', 'queued'].includes(task.status))
}
