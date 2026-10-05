import { SendIcon } from './ChatIcons'

interface ChatInputProps {
    value: string
    onChange: (value: string) => void
    onSubmit: () => void
    onKeyDown: (e: React.KeyboardEvent) => void
    disabled?: boolean
    placeholder?: string
}

export function ChatInput({ value, onChange, onSubmit, onKeyDown, disabled, placeholder = "Type a message..." }: ChatInputProps) {
    return (
        <form onSubmit={(e) => { e.preventDefault(); onSubmit() }} className="p-4 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
            <div className="flex items-end gap-3">
                <div className="flex-1 relative">
                    <input
                        type="text"
                        value={value}
                        onChange={(e) => onChange(e.target.value)}
                        onKeyDown={onKeyDown}
                        placeholder={placeholder}
                        disabled={disabled}
                        className="w-full px-4 py-3 pr-12 border border-gray-200 dark:border-gray-600 rounded-xl bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent disabled:opacity-50"
                    />
                </div>
                <button
                    type="submit"
                    disabled={!value.trim() || disabled}
                    className="p-3 bg-cyan-500 text-white rounded-xl hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                    <SendIcon className="h-5 w-5" />
                </button>
            </div>
            <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">
                Press Enter to send
            </p>
        </form>
    )
}
