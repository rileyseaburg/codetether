'use client'

import { useState } from 'react'
import { AIPRDBuilder } from '../../app/(dashboard)/dashboard/ralph/AIPRDBuilder'
import { PRDBuilder } from '../../app/(dashboard)/dashboard/ralph/PRDBuilder'

interface PRDConfigPanelProps {
    prdJson: string
    error: string | null
    isRunning: boolean
    showBuilder: boolean
    builderMode: 'ai' | 'manual'
    prdBuilderMode: 'ai' | 'manual'
    resumeSession?: { sessionId: string; title: string; messages: Array<{ role: 'user' | 'assistant'; content: string; timestamp: string }> } | null
    onChange: (json: string) => void
    onLoadExample: () => void
    onBuilderComplete: (prd: any) => void
    onSetShowBuilder: (show: boolean) => void
    onSetBuilderMode: (mode: 'ai' | 'manual') => void
    onSetPrdBuilderMode: (mode: 'ai' | 'manual') => void
    onClearResumeSession?: () => void
}

export function RalphPRDConfigPanel({ prdJson, error, isRunning, showBuilder, builderMode, prdBuilderMode, resumeSession, onChange, onLoadExample, onBuilderComplete, onSetShowBuilder, onSetBuilderMode, onSetPrdBuilderMode, onClearResumeSession }: PRDConfigPanelProps) {
    // Track if AI builder has been opened (to keep it mounted for state preservation)
    const [aiBuilderMounted, setAiBuilderMounted] = useState(false)
    
    // Mount AI builder when first opened
    if (showBuilder && builderMode === 'ai' && !aiBuilderMounted) {
        setAiBuilderMounted(true)
    }
    
    const handleCancel = () => {
        onSetShowBuilder(false)
        onClearResumeSession?.()
        setAiBuilderMounted(false) // Fully unmount on explicit cancel (X button)
    }
    
    const handleMinimize = () => {
        onSetShowBuilder(false) // Just hide, don't unmount - preserves chat state
    }
    
    const isAiBuilderVisible = showBuilder && builderMode === 'ai'
    
    return (
        <div className="rounded-lg bg-white shadow-sm dark:bg-gray-800 dark:ring-1 dark:ring-white/10" data-cy="ralph-prd-panel">
            {/* Keep AI builder mounted but hidden when minimized to preserve chat state */}
            {aiBuilderMounted && <AIPRDBuilder onPRDComplete={onBuilderComplete} onCancel={handleCancel} onMinimize={handleMinimize} onSwitchToManual={() => onSetBuilderMode('manual')} resumeSession={resumeSession} visible={isAiBuilderVisible} />}
            {showBuilder && builderMode === 'manual' && <PRDBuilder onPRDComplete={onBuilderComplete} onCancel={() => onSetShowBuilder(false)} />}
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
                <h2 className="text-sm font-semibold text-gray-900 dark:text-white" data-cy="ralph-prd-title">PRD Configuration</h2>
                <div className="flex items-center gap-2">
                    <div className="flex items-center">
                        <button onClick={() => { onSetPrdBuilderMode('ai'); onSetShowBuilder(true) }} disabled={isRunning} data-cy="ralph-ai-assist-btn" className="text-xs bg-gradient-to-r from-purple-500 to-indigo-500 text-white px-3 py-1.5 rounded-l-lg hover:from-purple-600 hover:to-indigo-600 disabled:opacity-50 flex items-center gap-1.5">
                            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" /></svg>
                            AI Assist
                        </button>
                        <button onClick={() => { onSetPrdBuilderMode('manual'); onSetShowBuilder(true) }} disabled={isRunning} data-cy="ralph-manual-btn" className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-2 py-1.5 rounded-r-lg border-l border-gray-200 dark:border-gray-600 hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50">
                            Manual
                        </button>
                    </div>
                    <button onClick={onLoadExample} disabled={isRunning} data-cy="ralph-load-example-btn" className="text-xs text-purple-600 hover:text-purple-500 dark:text-purple-400 disabled:opacity-50">
                        Load Example
                    </button>
                </div>
            </div>
            <div className="p-4">
                <textarea value={prdJson} onChange={(e) => onChange(e.target.value)} placeholder='Paste your prd.json here or click "Create PRD" to use the builder...' data-cy="ralph-prd-textarea" className="w-full h-64 p-3 text-xs font-mono bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg resize-none focus:ring-2 focus:ring-purple-500 focus:border-transparent" disabled={isRunning} />
                {error && <p className="mt-2 text-xs text-red-500" data-cy="ralph-prd-error">{error}</p>}
            </div>
        </div>
    )
}
