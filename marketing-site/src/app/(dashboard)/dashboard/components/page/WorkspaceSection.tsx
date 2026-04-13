import { WorkspaceCard } from '../WorkspaceCard'
import type { Workspace } from '../../types'

interface Props {
  workspaces: Workspace[]
  onCreate: () => void
  onRemove: (id: string) => void
  onTrigger: (id: string) => void
}

export function WorkspaceSection({ workspaces, onCreate, onRemove, onTrigger }: Props) {
  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Workspaces</h2>
        <button onClick={onCreate} className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500">
          New workspace
        </button>
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {workspaces.map((workspace) => (
          <WorkspaceCard key={workspace.id} workspace={workspace} onUnregister={onRemove} onTrigger={onTrigger} />
        ))}
      </div>
    </section>
  )
}
