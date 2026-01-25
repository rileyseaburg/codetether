import { motion } from 'framer-motion'
import { CheckCircleIcon, DocumentIcon } from './ChatIcons2'
import { PRDCard } from './PRDCard'

interface PRDPreviewPanelProps {
    project: string
    branchName: string
    description: string
    userStoryCount: number
    onUse: () => void
    onEdit: () => void
    onClose: () => void
}

export function PRDPreviewPanel({ project, branchName, description, userStoryCount, onUse, onEdit, onClose }: PRDPreviewPanelProps) {
    return (
        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="border-t border-gray-200 dark:border-gray-700 bg-emerald-50 dark:bg-emerald-900/20">
            <div className="p-4">
                <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                        <CheckCircleIcon className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                        <span className="font-medium text-emerald-800 dark:text-emerald-300">PRD Generated!</span>
                    </div>
                    <button onClick={onClose} className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">Hide</button>
                </div>
                <PRDCard project={project} branchName={branchName} description={description} userStoryCount={userStoryCount} />
                <div className="flex gap-2">
                    <button onClick={onUse} className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-500 text-sm font-medium">
                        <DocumentIcon className="h-4 w-4" />Use This PRD
                    </button>
                    <button onClick={onEdit} className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 text-sm">Edit Manually</button>
                </div>
            </div>
        </motion.div>
    )
}
