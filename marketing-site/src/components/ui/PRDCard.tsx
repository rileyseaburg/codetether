interface PRDCardProps {
    project: string
    branchName: string
    description: string
    userStoryCount: number
}

export function PRDCard({ project, branchName, description, userStoryCount }: PRDCardProps) {
    return (
        <div className="bg-white dark:bg-gray-800 rounded-lg p-3 mb-3 border border-emerald-200 dark:border-emerald-800">
            <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-gray-900 dark:text-white">{project}</h4>
                <span className="text-xs font-mono text-cyan-600 dark:text-cyan-400">{branchName}</span>
            </div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">{description}</p>
            <div className="text-xs text-gray-500">
                {userStoryCount} user {userStoryCount === 1 ? 'story' : 'stories'}
            </div>
        </div>
    )
}
