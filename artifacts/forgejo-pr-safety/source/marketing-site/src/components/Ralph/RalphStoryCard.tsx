'use client'

import { useState } from 'react'
import { RalphEyeIcon, RalphRetryIcon } from '../ui/RalphIcons'
import type { UserStory } from '@/app/(dashboard)/dashboard/ralph/store'

interface RalphStoryCardProps { story: UserStory; isActive: boolean; isRunning: boolean; onRetry: (id: string) => void; onViewTask: (id: string) => void }

export function RalphStoryCard({ story, isActive, isRunning, onRetry, onViewTask }: RalphStoryCardProps) {
    const [expanded, setExpanded] = useState(false)
    const getStatusInfo = () => {
        if (story.passes) return { icon: '✅', color: 'border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20' }
        if (story.taskStatus === 'failed') return { icon: '❌', color: 'border-red-500 bg-red-50 dark:bg-red-900/20' }
        if (story.taskStatus === 'running' || isActive) return { icon: '⏳', color: 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20' }
        if (story.taskStatus === 'pending') return { icon: '🔄', color: 'border-yellow-500 bg-yellow-50' }
        return { icon: '○', color: 'border-gray-200 dark:border-gray-700' }
    }
    const { icon, color } = getStatusInfo()

    return (
        <div className={`p-3 border-l-4 ${color}`} data-cy="ralph-story-card" data-story-id={story.id} data-story-status={story.taskStatus || 'pending'}>
            <div className="flex items-start justify-between">
                <div className="flex items-start gap-2 flex-1 min-w-0">
                    <span className="text-sm mt-0.5" data-cy="ralph-story-icon">{icon}</span>
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                            <span className="text-xs font-mono font-bold" data-cy="ralph-story-id">{story.id}</span>
                            {story.taskStatus && <span className={`text-[10px] px-1.5 py-0.5 rounded ${story.taskStatus === 'completed' ? 'bg-emerald-100 text-emerald-700' : story.taskStatus === 'failed' ? 'bg-red-100 text-red-700' : story.taskStatus === 'running' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-700'}`} data-cy="ralph-story-status">{story.taskStatus}</span>}
                        </div>
                        <p className="text-xs font-medium mt-0.5" data-cy="ralph-story-title">{story.title}</p>
                        {expanded && (
                            <div className="mt-2 space-y-2" data-cy="ralph-story-details">
                                <p className="text-xs">{story.description}</p>
                                <div className="text-xs">
                                    <ul className="list-disc list-inside">{story.acceptanceCriteria.map((c, i) => <li key={i}>{c}</li>)}</ul>
                                </div>
                                {story.taskId && <p className="text-[10px] font-mono" data-cy="ralph-story-task-id">Task: {story.taskId}</p>}
                            </div>
                        )}
                    </div>
                </div>
                <div className="flex items-center gap-1 ml-2">
                    <button onClick={() => setExpanded(!expanded)} data-cy="ralph-story-expand-btn" className="p-1 text-gray-400"><svg className={`w-4 h-4 transition-transform ${expanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg></button>
                    {story.taskId && <button onClick={() => onViewTask(story.id)} data-cy="ralph-story-view-btn" className="p-1 text-gray-400"><RalphEyeIcon className="w-4 h-4" /></button>}
                    {(story.taskStatus === 'failed' || story.passes === false) && !isRunning && <button onClick={() => onRetry(story.id)} data-cy="ralph-story-retry-btn" className="p-1 text-gray-400"><RalphRetryIcon className="w-4 h-4" /></button>}
                </div>
            </div>
        </div>
    )
}
