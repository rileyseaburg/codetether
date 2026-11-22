'use client'

import { RalphStoryCard } from './RalphStoryCard'
import type { UserStory } from '@/app/(dashboard)/dashboard/ralph/store'
import type { RalphRun } from '@/app/(dashboard)/dashboard/ralph/store'

interface RalphStoriesPanelProps {
    prd: { userStories: UserStory[] } | null
    run: RalphRun | null
    passedCount: number
    totalCount: number
    isRunning: boolean
    onResume: () => void
    onRetryStory: (storyId: string) => void
    onViewTask: (storyId: string) => void
}

export function RalphStoriesPanel({ prd, run, passedCount, totalCount, isRunning, onResume, onRetryStory, onViewTask }: RalphStoriesPanelProps) {
    if (!prd) return null

    return (
        <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10" data-cy="ralph-stories-panel">
            <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-gray-900 dark:text-white">User Stories</h2>
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500 dark:text-gray-400" data-cy="ralph-stories-progress">{passedCount}/{totalCount} passed</span>
                        {!isRunning && passedCount < totalCount && <button onClick={onResume} data-cy="ralph-resume-btn" className="text-xs px-2 py-1 bg-purple-600 text-white rounded hover:bg-purple-500">Resume</button>}
                    </div>
                </div>
            </div>
            <div className="divide-y divide-gray-200 dark:divide-gray-700 max-h-96 overflow-y-auto" data-cy="ralph-stories-list">
                {prd.userStories.map((story) => (
                    <RalphStoryCard key={story.id} story={story} isActive={run?.currentStoryId === story.id} isRunning={isRunning} onRetry={onRetryStory} onViewTask={onViewTask} />
                ))}
            </div>
        </div>
    )
}
