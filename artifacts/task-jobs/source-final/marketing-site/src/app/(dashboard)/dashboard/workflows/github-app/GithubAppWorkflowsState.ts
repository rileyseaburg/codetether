import type { GithubAppWorkflowResponse } from './types'

export type GithubAppWorkflowsState = {
  data: GithubAppWorkflowResponse | null
  error: string | null
  loading: boolean
  repos: string
  autoRefresh: boolean
}

type Action =
  | { type: 'loading' }
  | { type: 'loaded'; data: GithubAppWorkflowResponse }
  | { type: 'failed'; error: string }
  | { type: 'setRepos'; repos: string }
  | { type: 'setAutoRefresh'; autoRefresh: boolean }

export const initialGithubAppWorkflowsState: GithubAppWorkflowsState = {
  data: null,
  error: null,
  loading: true,
  repos: '',
  autoRefresh: true,
}

export function githubAppWorkflowsReducer(
  state: GithubAppWorkflowsState,
  action: Action,
): GithubAppWorkflowsState {
  if (action.type === 'loading') return { ...state, loading: true, error: null }
  if (action.type === 'loaded') return { ...state, loading: false, data: action.data, error: null }
  if (action.type === 'failed') return { ...state, loading: false, error: action.error }
  if (action.type === 'setRepos') return { ...state, repos: action.repos }
  if (action.type === 'setAutoRefresh') return { ...state, autoRefresh: action.autoRefresh }
  return state
}

const emptyWorkflowResponse = (): GithubAppWorkflowResponse => ({
  generated_at: new Date().toISOString(),
  totals: {},
  route_states: {},
  failure_classes: {},
  workflows: [],
  tasks: [],
  runs: [],
})

export function normalizeWorkflowResponse(value: unknown): GithubAppWorkflowResponse {
  if (!value || Array.isArray(value) || typeof value !== 'object') return emptyWorkflowResponse()
  const response = value as Partial<GithubAppWorkflowResponse>
  return {
    generated_at: response.generated_at || new Date().toISOString(),
    totals: response.totals || {},
    route_states: response.route_states || {},
    failure_classes: response.failure_classes || {},
    workflows: Array.isArray(response.workflows) ? response.workflows : [],
    tasks: Array.isArray(response.tasks) ? response.tasks : [],
    runs: Array.isArray(response.runs) ? response.runs : [],
  }
}

export function githubAppWorkflowsApiPath(repos: string, apiUrl: string) {
  const query = new URLSearchParams({ repos, limit: '250' })
  const prefix = apiUrl === '/api' ? '/tenant/v1' : '/v1'
  return `${prefix}/agent/workflows/github-app?${query.toString()}`
}
