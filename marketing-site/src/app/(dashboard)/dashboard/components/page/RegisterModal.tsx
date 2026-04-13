import type { RegisterMode, RegisterRuntime } from '../../types'
import type { RegisterDraft } from '../../lib/dashboard-types'

interface Props {
  draft: RegisterDraft
  mode: RegisterMode
  runtime: RegisterRuntime
  open: boolean
  setDraft: (updater: (draft: RegisterDraft) => RegisterDraft) => void
  setMode: (mode: RegisterMode) => void
  setRuntime: (runtime: RegisterRuntime) => void
  onClose: () => void
  onSubmit: () => void
}

export function RegisterModal({ draft, mode, runtime, open, setDraft, setMode, setRuntime, onClose, onSubmit }: Props) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-2xl rounded-lg bg-white p-6 dark:bg-gray-800">
        <div className="grid gap-4 md:grid-cols-2">
          <input value={draft.name} onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))} placeholder="Workspace name" className="rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700" />
          <input value={draft.path} onChange={(e) => setDraft((d) => ({ ...d, path: e.target.value }))} placeholder="Path" className="rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700" />
          <select value={mode} onChange={(e) => setMode(e.target.value as RegisterMode)} className="rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700"><option value="local">Local</option><option value="git">Git</option><option value="external">External</option></select>
          <select value={runtime} onChange={(e) => setRuntime(e.target.value as RegisterRuntime)} className="rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700"><option value="container">Container</option><option value="vm">VM</option></select>
          <input value={draft.description} onChange={(e) => setDraft((d) => ({ ...d, description: e.target.value }))} placeholder="Description" className="rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 md:col-span-2" />
          {mode === 'git' ? <input value={draft.git_url} onChange={(e) => setDraft((d) => ({ ...d, git_url: e.target.value }))} placeholder="Git URL" className="rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700 md:col-span-2" /> : null}
          {mode === 'git' ? <input value={draft.git_branch} onChange={(e) => setDraft((d) => ({ ...d, git_branch: e.target.value }))} placeholder="Git branch" className="rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700" /> : null}
          {mode === 'external' ? <input value={draft.external_provider} onChange={(e) => setDraft((d) => ({ ...d, external_provider: e.target.value }))} placeholder="Provider" className="rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700" /> : null}
          {mode === 'external' ? <input value={draft.external_reference} onChange={(e) => setDraft((d) => ({ ...d, external_reference: e.target.value }))} placeholder="Reference" className="rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700" /> : null}
        </div>
        <div className="mt-6 flex justify-end gap-3"><button onClick={onClose} className="rounded-md px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 dark:text-gray-300">Cancel</button><button onClick={onSubmit} disabled={!draft.name.trim()} className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50">Create</button></div>
      </div>
    </div>
  )
}
