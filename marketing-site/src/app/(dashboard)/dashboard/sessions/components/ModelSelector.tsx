interface ModelSelectorProps {
    value: string
    suggestions: string[]
    onChange: (value: string) => void
}

export function ModelSelector({ value, suggestions, onChange }: ModelSelectorProps) {
    const hasSuggestions = suggestions.length > 0

    return (
        <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2">
                <label
                    className="text-[10px] font-medium uppercase tracking-wide text-gray-400"
                    htmlFor="ct-model"
                >
                    Model override
                </label>
                {hasSuggestions && (
                    <span className="rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500 dark:bg-gray-700 dark:text-gray-300">
                        {suggestions.length} suggestions
                    </span>
                )}
            </div>
            <input
                id="ct-model"
                type="text"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                list="ct-model-options"
                placeholder="provider/model"
                className="w-full min-w-[180px] rounded-md border border-gray-300 bg-white px-3 py-2 text-xs text-gray-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white sm:w-[220px]"
                aria-describedby="model-hint"
                autoComplete="off"
            />
            <span id="model-hint" className="sr-only">
                Override the model used when resuming or sending messages.
                {hasSuggestions && ` ${suggestions.length} suggested model${suggestions.length !== 1 ? 's' : ''} available.`}
            </span>
            <datalist id="ct-model-options">
                {suggestions.map((m) => (
                    <option key={m} value={m} />
                ))}
            </datalist>
        </div>
    )
}
