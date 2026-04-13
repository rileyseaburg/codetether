// AdvancedControls - Single Responsibility: Swarm advanced settings

interface AdvancedControlsProps {
    showAdvancedControls: boolean
    onToggle: () => void
    workerPersonality: string
    onWorkerPersonalityChange: (value: string) => void
    swarmStrategy: 'auto' | 'domain' | 'data' | 'stage' | 'none'
    onSwarmStrategyChange: (value: 'auto' | 'domain' | 'data' | 'stage' | 'none') => void
    swarmMaxSubagents: number
    onSwarmMaxSubagentsChange: (value: number) => void
    swarmMaxSteps: number
    onSwarmMaxStepsChange: (value: number) => void
    swarmTimeoutSecs: number
    onSwarmTimeoutSecsChange: (value: number) => void
    swarmParallelEnabled: boolean
    onSwarmParallelEnabledChange: (value: boolean) => void
}

export function AdvancedControls({
    showAdvancedControls,
    onToggle,
    workerPersonality,
    onWorkerPersonalityChange,
    swarmStrategy,
    onSwarmStrategyChange,
    swarmMaxSubagents,
    onSwarmMaxSubagentsChange,
    swarmMaxSteps,
    onSwarmMaxStepsChange,
    swarmTimeoutSecs,
    onSwarmTimeoutSecsChange,
    swarmParallelEnabled,
    onSwarmParallelEnabledChange,
}: AdvancedControlsProps) {
    return (
        <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
            <button
                onClick={onToggle}
                className="text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300"
            >
                {showAdvancedControls ? '▼ Hide' : '▶ Show'} Advanced Controls
            </button>

            {showAdvancedControls && (
                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Worker Personality */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Worker Personality
                        </label>
                        <input
                            type="text"
                            value={workerPersonality}
                            onChange={(e) => onWorkerPersonalityChange(e.target.value)}
                            placeholder="e.g., react-expert, fullstack-genai"
                            className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                        />
                    </div>

                    {/* Swarm Strategy */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Swarm Strategy
                        </label>
                        <select
                            value={swarmStrategy}
                            onChange={(e) => onSwarmStrategyChange(e.target.value as typeof swarmStrategy)}
                            className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                        >
                            <option value="auto">Auto</option>
                            <option value="domain">Domain</option>
                            <option value="data">Data</option>
                            <option value="stage">Stage</option>
                            <option value="none">None</option>
                        </select>
                    </div>

                    {/* Max Subagents */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Max Subagents
                        </label>
                        <input
                            type="number"
                            min={1}
                            max={32}
                            value={swarmMaxSubagents}
                            onChange={(e) => onSwarmMaxSubagentsChange(Number(e.target.value))}
                            className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                        />
                    </div>

                    {/* Max Steps */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Max Steps
                        </label>
                        <input
                            type="number"
                            min={1}
                            max={500}
                            value={swarmMaxSteps}
                            onChange={(e) => onSwarmMaxStepsChange(Number(e.target.value))}
                            className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                        />
                    </div>

                    {/* Timeout */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Timeout (seconds)
                        </label>
                        <input
                            type="number"
                            min={60}
                            max={3600}
                            value={swarmTimeoutSecs}
                            onChange={(e) => onSwarmTimeoutSecsChange(Number(e.target.value))}
                            className="w-full rounded-md border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white"
                        />
                    </div>

                    {/* Parallel Enabled */}
                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            id="parallel-enabled"
                            checked={swarmParallelEnabled}
                            onChange={(e) => onSwarmParallelEnabledChange(e.target.checked)}
                            className="rounded border-gray-300"
                        />
                        <label htmlFor="parallel-enabled" className="text-sm text-gray-700 dark:text-gray-300">
                            Enable Parallel Execution
                        </label>
                    </div>
                </div>
            )}
        </div>
    )
}
