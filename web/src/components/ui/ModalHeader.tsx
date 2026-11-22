import { SparklesIcon, CloseIcon } from './ChatIcons'
import { EditIcon } from './ChatIcons2'

interface ModalHeaderProps {
    title: string
    subtitle: string
    onCancel: () => void
    onSwitchToManual: () => void
    onMouseDown?: (e: React.MouseEvent | React.PointerEvent) => void
    dragIcon?: React.ReactNode
}

export function ModalHeader({ title, subtitle, onCancel, onSwitchToManual, onMouseDown, dragIcon }: ModalHeaderProps) {
    return (
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-cyan-600 to-cyan-800 select-none">
            <div className="flex items-center gap-3">
                <div className="p-2 bg-white/20 rounded-lg">
                    <SparklesIcon className="h-5 w-5 text-white" />
                </div>
                <div className="flex items-center gap-2.5">
                    <div 
                        className="text-white/60 hover:text-white hover:bg-white/10 rounded p-1 -ml-1 transition-all scale-100 active:scale-95" 
                        title="Drag to move"
                    >
                        <div 
                            onMouseDown={onMouseDown}
                            className="cursor-grab active:cursor-grabbing"
                        >
                            <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
                                <path d="M7 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM7 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM4 7a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM4 13a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM13 7a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM13 13a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/>
                            </svg>
                        </div>
                    </div>
                    <div className="cursor-text">
                        <h2 className="text-lg font-semibold text-white">{title}</h2>
                        <p className="text-sm text-cyan-100">{subtitle}</p>
                    </div>
                </div>
            </div>
            <div className="flex items-center gap-2">
                <button
                    onClick={onSwitchToManual}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                >
                    <EditIcon className="h-4 w-4" />
                    Manual Mode
                </button>
                <button
                    type="button"
                    onClick={onCancel}
                    onMouseDown={(e) => e.stopPropagation()}
                    data-cy="modal-close-btn"
                    className="p-1.5 text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
                    style={{ cursor: 'pointer' }}
                >
                    <CloseIcon className="h-5 w-5" />
                </button>
            </div>
        </div>
    )
}
