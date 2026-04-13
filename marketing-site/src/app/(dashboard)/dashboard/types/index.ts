export interface Workspace {
  id: string
  name: string
  path: string
  description?: string
  status: string
  worker_id?: string
  runtime: 'container' | 'vm'
  vm_status?: string
  vm_name?: string
  vm_ssh_service?: string
  vm_ssh_host?: string
  vm_ssh_port?: number
}

export interface Worker {
  worker_id: string
  name: string
  hostname?: string
  status: string
  global_workspace_id?: string
  global_codebase_id?: string
  last_seen?: string
  is_sse_connected?: boolean
  supported_protocols?: string[]
  preferred_protocol?: string
  supports_grpc?: boolean
  supports_grpc_web?: boolean
  is_knative_worker?: boolean
  is_harvester_backed?: boolean
  infrastructure_provider?: string
}

export interface AgentDefinition {
  id: string
  name: string
  description?: string | null
  mode: string
  native: boolean
  hidden: boolean
  model?: string | null
  max_steps?: number | null
  worker_id?: string | null
}

export interface RegisterForm {
  name: string
  path: string
  description: string
  git_url: string
  git_branch: string
  worker_id: string
  runtime: 'container' | 'vm'
  external_provider: string
  external_reference: string
}

export type RegisterMode = 'local' | 'git' | 'external'
export type RegisterRuntime = 'container' | 'vm'
