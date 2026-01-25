interface ModeSelectorProps {
    value: string
    onChange: (value: string) => void
}

const MODE_DESCRIPTIONS: Record<string, string> = {
    architect: 'Architect mode - for planning, designing, or strategizing before implementation',
    code: 'Code mode - for writing, modifying, or refactoring code',
    ask: 'Ask mode - for explanations, documentation, or answers to technical questions',
    debug: 'Debug mode - for troubleshooting issues, investigating errors, or diagnosing problems',
    orchestrator: 'Orchestrator mode - for complex, multi-step projects that require coordination across different specialties',
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
                            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${isActive
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

