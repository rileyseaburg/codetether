import { useWorkspaces } from './useWorkspaces'

/**
 * Backward-compat shim for legacy imports while workspace migration is in progress.
 * Prefer importing `useWorkspaces` directly in new code.
 */
export function useCodebases() {
  const { workspaces, loadWorkspaces } = useWorkspaces()
  return {
    codebases: workspaces,
    loadCodebases: loadWorkspaces,
  }
}

