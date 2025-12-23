interface ModeSelectorProps {
    value: string
    onChange: (value: string) => void
}

const MODE_DESCRIPTIONS: Record<string, string> = {
    build: 'Build mode - for writing and editing code',
    plan: 'Plan mode - for creating implementation plans',
    explore: 'Explore mode - for navigating and understanding code',
    general: 'General mode - for general questions and tasks',
}

export function ModeSelector({ value, onChange }: ModeSelectorProps) {
    return (
        <div className="flex flex-col">
            <label htmlFor="agent-mode" className="sr-only">
                Agent mode
            </label>
            <select
                id="agent-mode"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                className="rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-xs px-2 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                aria-describedby="mode-description"
            >
                <option value="build">build</option>
                <option value="plan">plan</option>
                <option value="explore">explore</option>
                <option value="general">general</option>
            </select>
            <span id="mode-description" className="sr-only">
                {MODE_DESCRIPTIONS[value] || 'Select an agent mode'}
            </span>
        </div>
    )
}
