interface ModelSelectorProps {
    value: string
    suggestions: string[]
    onChange: (value: string) => void
}

export function ModelSelector({ value, suggestions, onChange }: ModelSelectorProps) {
    const hasSuggestions = suggestions.length > 0

    return (
        <div className="hidden md:flex flex-col items-end">
            <label
                className="text-[10px] text-gray-400 dark:text-gray-500"
                htmlFor="ct-model"
            >
                Model (optional)
            </label>
            <input
                id="ct-model"
                type="text"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                list="ct-model-options"
                placeholder="provider/model"
                className="w-[220px] rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-xs px-2 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
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
