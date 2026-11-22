import { WorkspaceSelector } from './WorkspaceSelector'

interface CodebaseSelectorProps {
  selectedCodebase: string
  codebases: Array<{ id: string; name?: string }>
  onChange: (id: string) => void
}

/**
 * Backward-compat shim for legacy prop names.
 * Prefer `WorkspaceSelector` in new code.
 */
export function CodebaseSelector({
  selectedCodebase,
  codebases,
  onChange,
}: CodebaseSelectorProps) {
  return (
    <WorkspaceSelector
      selectedWorkspace={selectedCodebase}
      workspaces={codebases}
      onChange={onChange}
    />
  )
}

