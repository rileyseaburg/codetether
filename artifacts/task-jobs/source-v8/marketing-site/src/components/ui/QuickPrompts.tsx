export function QuickPrompts({ prompts, onSelect, disabled }: {
    prompts: string[]
    onSelect: (prompt: string) => void
    disabled?: boolean
}) {
    return (
        <div className="mb-4">
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">Quick start suggestions:</p>
            <div className="flex flex-wrap gap-2">
                {prompts.map((prompt, i) => (
                    <button
                        key={i}
                        onClick={() => onSelect(prompt)}
                        disabled={disabled}
                        className="px-3 py-1.5 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-full text-gray-700 dark:text-gray-300 hover:border-cyan-500 hover:text-cyan-600 dark:hover:text-cyan-400 transition-colors disabled:opacity-50"
                    >
                        {prompt}
                    </button>
                ))}
            </div>
        </div>
    )
}
