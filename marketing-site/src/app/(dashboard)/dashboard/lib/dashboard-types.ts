export interface Notice {
  type: 'success' | 'warning' | 'error'
  message: string
  detail?: string
}

export interface RegisterDraft {
  name: string
  path: string
  description: string
  git_url: string
  git_branch: string
  external_provider: string
  external_reference: string
}

export const emptyRegisterDraft = (): RegisterDraft => ({
  name: '',
  path: '',
  description: '',
  git_url: '',
  git_branch: 'main',
  external_provider: '',
  external_reference: '',
})
