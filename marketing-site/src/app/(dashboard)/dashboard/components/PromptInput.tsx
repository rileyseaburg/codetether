// PromptInput - Single Responsibility: Task prompt input

import { CodeIcon, BeakerIcon, GlobeIcon } from './Icons'

interface PromptInputProps {
    prompt: string
    osPrompt: string
    onPromptChange: (value: string) => void
    onOsPromptChange: (value: string) => void
    selectedAgent: string
    onAgentChange: (value: string) => void
    isRunning: boolean
    disabled?: boolean
}

const AGENT_OPTIONS = [
    { value: 'build', label: 'Build', icon: CodeIcon },
    { value: 'plan', label: 'Plan', icon: BeakerIcon },
    { value: 'explore', label: 'Explore', icon: GlobeIcon },
]

export function PromptInput({
    prompt,
    osPrompt,
    onPromptChange,
    onOsPromptChange,
    selectedAgent,
    onAgentChange,
    isRunning,
    disabled,
}: PromptInputProps) {
    return (
        <div className="space-y-4">
            {/* Agent Type Selector */}
            <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Agent Type
                </label>
                <div className="flex gap-2">
                    {AGENT_OPTIONS.map(({ value, label, icon: Icon }) => (
                        <button
                            key={value}
                            onClick={() => onAgentChange(value)}
                            disabled={isRunning}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-all ${
                                selectedAgent === value
                                    ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-300'
                                    : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:border-indigo-300'
                            } disabled:opacity-50`}
                        >
                            <Icon className="w-4 h-4" />
                            {label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Main Prompt */}
            <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Task Prompt
                </label>
                <textarea
                    value={prompt}
                    onChange={(e) => onPromptChange(e.target.value)}
                    placeholder="Describe what you want to build..."
                    disabled={isRunning || disabled}
                    rows={4}
                    className="w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500 disabled:opacity-50"
                />
            </div>

            {/* OS Prompt */}
            <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    OS Context (optional)
                </label>
                <textarea
                    value={osPrompt}
                    onChange={(e) => onOsPromptChange(e.target.value)}
                    placeholder="Additional OS-level context..."
                    disabled={isRunning || disabled}
                    rows={2}
                    className="w-full rounded-lg border-gray-300 dark:border-gray-600 dark:bg-gray-800 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500 disabled:opacity-50"
                />
            </div>
        </div>
    )
}
