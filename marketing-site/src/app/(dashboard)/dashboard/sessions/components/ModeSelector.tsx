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
    const modes = Object.keys(MODE_DESCRIPTIONS)

    return (
        <div className="flex flex-col gap-1">
            <span className="text-[10px] font-medium uppercase tracking-wide text-gray-400">Mode</span>
            <div
                role="radiogroup"
                aria-label="Agent mode"
                className="flex flex-wrap items-center gap-1 rounded-full bg-gray-100 p-1 dark:bg-gray-700/70"
            >
                {modes.map((mode) => {
                    const isActive = value === mode
                    return (
                        <button
                            key={mode}
                            type="button"
                            role="radio"
                            aria-checked={isActive}
                            onClick={() => onChange(mode)}
                            title={MODE_DESCRIPTIONS[mode] || mode}
                            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                                isActive
                                    ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-900 dark:text-white'
                                    : 'text-gray-500 hover:text-gray-700 dark:text-gray-300 dark:hover:text-white'
                            }`}
                        >
                            {mode}
                        </button>
                    )
                })}
            </div>
        </div>
    )
}
