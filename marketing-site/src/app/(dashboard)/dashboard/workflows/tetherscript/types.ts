export type Counts = Record<string, number>

export interface WorkflowSummary {
  repo?: string
  issue_pr?: string
  url?: string
  status_counts: Counts
  agent_counts: Counts
  incomplete_count: number
  pending_count: number
  running_count: number
  failed_count: number
  unscoped_pending_count: number
  stale_pending_count: number
  last_update?: string
  errors?: string
  error_class: string
}

export interface WorkflowTask {
  id: string
  status: string
  title?: string
  agent_type?: string
  updated_at?: string
  repo?: string
  issue_pr?: string
  target_worker_id?: string
  worker_name?: string
  worker_status?: string
  worker_last_seen?: string
  route_state: string
  error?: string
  error_class: string
}

export interface WorkflowRun {
  run_id: string
  task_id: string
  status: string
  lease_owner?: string
  lease_expires_at?: string
  last_error?: string
  error_class: string
  repo?: string
  issue_pr?: string
}

export interface TetherScriptWorkflowResponse {
  generated_at: string
  totals: Counts
  route_states: Counts
  failure_classes: Counts
  workflows: WorkflowSummary[]
  tasks: WorkflowTask[]
  runs: WorkflowRun[]
}
