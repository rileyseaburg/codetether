'use client'

import { useState, useEffect, useRef, memo } from 'react'
import type { RLMStep, RLMStats } from '../hooks'

interface RLMExecutionPaneProps {
    isOpen: boolean
    onClose: () => void
    sessionId?: string
    liveDraft?: string
    steps?: RLMStep[]
    stats?: RLMStats
    variant?: 'overlay' | 'dock'
    className?: string
}

export function RLMExecutionPane({ isOpen, onClose, sessionId, liveDraft, steps: liveSteps, stats: liveStats, variant = 'overlay', className = '' }: RLMExecutionPaneProps) {
    const [isExpanded, setIsExpanded] = useState(true)
    const scrollRef = useRef<HTMLDivElement>(null)

    const steps = liveSteps || []
    const stats = liveStats || { tokens: 0, chunks: 0, subcalls: { completed: 0, total: 0 } }
    const isProcessing = liveDraft && liveDraft.length > 0
    const sessionIdShort = sessionId ? sessionId.slice(0, 8) : ''
    const errorCount = steps.filter((s) => s.type === 'error' || s.status === 'error').length
    const runningCount = steps.filter((s) => s.status === 'running').length
    const completedCount = steps.filter((s) => s.status === 'completed').length
    const latestStep = steps[steps.length - 1]
    const latestSnippet = latestStep?.content
        ? latestStep.content.length > 180
            ? `${latestStep.content.slice(0, 180)}...`
            : latestStep.content
        : ''

    // Auto-scroll to bottom
    useEffect(() => {
        if (scrollRef.current && isExpanded) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight
        }
    }, [steps, isExpanded])

    if (!isOpen) return null

    // Variant styles: overlay (default) is fixed/modal, dock is inline
    const baseClass = variant === 'dock'
        ? 'flex h-full w-full flex-col bg-gray-950'
        : 'fixed inset-y-0 right-0 z-50 flex w-full flex-col border-l border-gray-800 bg-gray-950 shadow-2xl sm:w-96'

    return (
        <div className={`${baseClass} ${className}`} role="complementary" aria-label="RLM inspector">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-gray-800 bg-gray-900 px-4 py-3">
                <div className="flex items-center gap-3">
                    <div className={`h-2 w-2 rounded-full ${isProcessing ? 'bg-cyan-500 animate-pulse' : 'bg-gray-500'}`} />
                    <div>
                        <h3 className="text-sm font-semibold text-white">RLM Inspector</h3>
                        <div className="text-xs text-gray-500">
                            {isProcessing ? 'Live' : 'Idle'}
                            {sessionIdShort && ` - ${sessionIdShort}`}
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="p-1 text-gray-400 hover:text-white transition-colors"
                        aria-label={isExpanded ? 'Collapse' : 'Expand'}
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} 
                                d={isExpanded ? "M20 12H4" : "M4 12h16"} />
                        </svg>
                    </button>
                    <button
                        onClick={onClose}
                        className="p-1 text-gray-400 hover:text-white transition-colors"
                        aria-label="Close RLM pane"
                    >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>
            </div>

            {/* Stats bar */}
            <div className="grid grid-cols-2 gap-3 border-b border-gray-800 bg-gray-900/50 px-4 py-2 text-xs sm:grid-cols-4">
                <div className="flex items-center gap-1">
                    <span className="text-gray-500">Tokens</span>
                    <span className="font-mono text-cyan-400">{stats.tokens.toLocaleString()}</span>
                </div>
                <div className="flex items-center gap-1">
                    <span className="text-gray-500">Chunks</span>
                    <span className="font-mono text-cyan-400">{stats.chunks}</span>
                </div>
                <div className="flex items-center gap-1">
                    <span className="text-gray-500">Sub-calls</span>
                    <span className="font-mono text-cyan-400">{stats.subcalls.completed}/{stats.subcalls.total}</span>
                </div>
                <div className="flex items-center gap-1">
                    <span className="text-gray-500">Errors</span>
                    <span className={`font-mono ${errorCount ? 'text-red-400' : 'text-gray-400'}`}>{errorCount}</span>
                </div>
            </div>

            {/* Execution steps */}
            <div
                ref={scrollRef}
                className={`flex-1 overflow-y-auto p-3 ${isExpanded ? 'space-y-3' : 'hidden'}`}
            >
                {steps.length === 0 && !isProcessing && (
                    <div className="flex flex-col items-center justify-center h-full text-center text-gray-500">
                        <svg className="w-12 h-12 mb-3 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                        <p className="text-sm">No RLM activity</p>
                        <p className="text-xs mt-1">RLM steps will appear here when processing large inputs</p>
                    </div>
                )}

                {steps.length === 0 && isProcessing && (
                    <div className="flex flex-col items-center justify-center h-full text-center text-gray-500">
                        <div className="flex gap-1 mb-3">
                            <span className="h-2 w-2 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                            <span className="h-2 w-2 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                            <span className="h-2 w-2 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                        </div>
                        <p className="text-sm">Waiting for RLM patterns...</p>
                        <p className="text-xs mt-1">Monitoring stream for large input processing</p>
                    </div>
                )}

                {steps.map((step) => (
                    <RLMStepItem key={step.id} step={step} />
                ))}

                {/* Current activity indicator */}
                {steps.length > 0 && steps.some(s => s.status === 'running') && (
                    <div className="flex items-center gap-2 text-xs text-gray-500">
                        <div className="flex gap-1">
                            <span className="h-1.5 w-1.5 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: '0ms' }} />
                            <span className="h-1.5 w-1.5 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: '150ms' }} />
                            <span className="h-1.5 w-1.5 rounded-full bg-cyan-500 animate-bounce" style={{ animationDelay: '300ms' }} />
                        </div>
                        <span>
                            {stats.subcalls.total > 0 
                                ? `Processing chunk ${stats.subcalls.completed + 1}/${stats.subcalls.total}...`
                                : 'Processing...'
                            }
                        </span>
                    </div>
                )}
            </div>

            {!isExpanded && (
                <div className="flex-1 p-4">
                    {steps.length === 0 ? (
                        <div className="rounded-lg border border-dashed border-gray-800 bg-gray-900/40 p-4 text-xs text-gray-500">
                            Collapse mode. Expand to view live steps and detailed output.
                        </div>
                    ) : (
                        <div className="space-y-3 text-xs text-gray-400">
                            <div className="rounded-lg bg-gray-900/50 p-3">
                                <div className="flex items-center justify-between text-[10px] uppercase tracking-wide text-gray-500">
                                    <span>Latest activity</span>
                                    <span>{latestStep?.type || 'step'}</span>
                                </div>
                                <p className="mt-2 text-gray-200">{latestSnippet || 'No content yet.'}</p>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="rounded-full bg-gray-900 px-2 py-1 text-[10px] text-gray-400">
                                    {runningCount} running
                                </span>
                                <span className="rounded-full bg-gray-900 px-2 py-1 text-[10px] text-gray-400">
                                    {completedCount} completed
                                </span>
                                <span className={`rounded-full px-2 py-1 text-[10px] ${errorCount ? 'bg-red-900/40 text-red-300' : 'bg-gray-900 text-gray-400'}`}>
                                    {errorCount} errors
                                </span>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Footer with info */}
            <div className="px-4 py-3 border-t border-gray-800 bg-gray-900">
                <div className="flex items-center justify-between text-xs">
                    <a 
                        href="https://arxiv.org/html/2512.24601v1" 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                    >
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z" />
                            <path fillRule="evenodd" d="M4 5a2 2 0 012-2 3 3 0 003 3h2a3 3 0 003-3 2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm3 4a1 1 0 000 2h.01a1 1 0 100-2H7zm3 0a1 1 0 000 2h3a1 1 0 100-2h-3zm-3 4a1 1 0 100 2h.01a1 1 0 100-2H7zm3 0a1 1 0 100 2h3a1 1 0 100-2h-3z" clipRule="evenodd" />
                        </svg>
                        RLM Paper (MIT)
                    </a>
                    <span className="text-gray-500">
                        Est. completion: ~2 min
                    </span>
                </div>
            </div>
        </div>
    )
}

const RLMStepItem = memo(function RLMStepItem({ step }: { step: RLMStep }) {
    const typeConfig = {
        load: { icon: '📥', label: 'Load', color: 'text-blue-400 bg-blue-950' },
        code: { icon: '💻', label: 'Code', color: 'text-green-400 bg-green-950' },
        output: { icon: '📤', label: 'Output', color: 'text-gray-400 bg-gray-800' },
        subcall: { icon: '🔄', label: 'Sub-call', color: 'text-cyan-400 bg-cyan-950' },
        result: { icon: '✅', label: 'Result', color: 'text-emerald-400 bg-emerald-950' },
        error: { icon: '❌', label: 'Error', color: 'text-red-400 bg-red-950' },
    }

    const config = typeConfig[step.type]

    return (
        <div className={`rounded-lg ${config.color} p-3 transition-shadow animate-fadeIn`}>
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    <span>{config.icon}</span>
                    <span className="text-xs font-medium">{config.label}</span>
                    {step.status === 'running' && (
                        <span className="h-1.5 w-1.5 rounded-full bg-current animate-pulse" />
                    )}
                </div>
                {step.duration && (
                    <span className="text-[10px] text-gray-500">{step.duration}s</span>
                )}
            </div>
            <pre className="text-xs font-mono whitespace-pre-wrap wrap-break-word overflow-x-auto">
                {step.content}
            </pre>
        </div>
    )
})
