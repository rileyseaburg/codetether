import { WorkerList } from '../WorkerList'
import type { Worker } from '../../types'

interface Props {
  workers: Worker[]
  selectedWorkerId: string
  onSelect: (workerId: string) => void
}

export function WorkerSection({ workers, selectedWorkerId, onSelect }: Props) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Workers</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">Choose the worker that should execute dashboard actions.</p>
      </div>
      <WorkerList workers={workers} selectedId={selectedWorkerId} onSelect={onSelect} />
    </section>
  )
}
