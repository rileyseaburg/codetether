import VoiceAgentButton from '../voice/VoiceAgentButton'
import type { Worker } from '../../types'

interface Props {
  osPrompt: string
  setOsPrompt: (value: string) => void
  workers: Worker[]
  codebaseId?: string
}

export function LaunchSection({ osPrompt, setOsPrompt, workers, codebaseId }: Props) {
  return (
    <section className="space-y-4 rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
      <div>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Voice agent</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">Launch a voice-driven workflow against the selected workspace.</p>
      </div>
      <textarea value={osPrompt} onChange={(e) => setOsPrompt(e.target.value)} rows={4} className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-700" placeholder="Describe what you want the voice agent to do..." />
      <VoiceAgentButton codebaseId={codebaseId} workers={workers} />
    </section>
  )
}
