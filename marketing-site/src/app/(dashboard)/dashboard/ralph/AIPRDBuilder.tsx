'use client'

import { useState, useEffect, useRef } from 'react'
import { AnimatePresence } from 'framer-motion'
import { useRalphStore, type PRD } from './store'
import { ModelSelector } from '@/components/ModelSelector'
import { WorkerSelector } from '@/components/WorkerSelector'
import { useCodebases } from '../sessions/hooks/useCodebases'
import { ChatArea } from '@/components/ui/ChatArea'
import { PRDPreviewPanel } from '@/components/ui/PRDPreviewPanel'
import { ChatInput } from '@/components/ui/ChatInput'
import { CodebaseSelector } from '@/components/ui/CodebaseSelector'
import { AIPRDModal } from '@/components/ui/AIPRDModal'
import { useAIPRDChat, type GeneratedPRD } from './useAIPRDChat'

export function AIPRDBuilder({ onPRDComplete, onCancel, onMinimize, onSwitchToManual, resumeSession, visible = true }: {
    onPRDComplete: (prd: PRD) => void
    onCancel: () => void
    onMinimize?: () => void
    onSwitchToManual: () => void
    resumeSession?: { sessionId: string; title: string; messages: Array<{ role: 'user' | 'assistant'; content: string; timestamp: string }> } | null
    visible?: boolean
}) {
    const { selectedCodebase, setSelectedCodebase, selectedWorker, setSelectedWorker } = useRalphStore()
    const { codebases } = useCodebases()
    const [input, setInput] = useState('')
    const [showPreview, setShowPreview] = useState(false)
    const [isRestoredConversation, setIsRestoredConversation] = useState(false)
    const { messages, isLoading, generatedPRD, setGeneratedPRD, sendMessage, initializeChat, loadSession, messagesEndRef } = useAIPRDChat(selectedCodebase)
    
    // Track if we've already initialized to prevent re-init on visibility changes
    const hasInitialized = useRef(false)
    const lastSessionId = useRef<string | null>(null)

    // Initialize or load session messages
    useEffect(() => { 
        // If resuming a session with messages
        if (resumeSession && resumeSession.sessionId !== lastSessionId.current) {
            lastSessionId.current = resumeSession.sessionId
            hasInitialized.current = true
            if (resumeSession.messages.length > 0) {
                loadSession(resumeSession.messages)
                setIsRestoredConversation(true)
            } else {
                // No messages found, start fresh with context
                initializeChat(`I see you want to continue working on "${resumeSession.title}". What would you like to focus on?`)
                setIsRestoredConversation(false)
            }
            return
        }
        
        // Skip if already initialized
        if (hasInitialized.current) {
            return
        }
        
        hasInitialized.current = true
        setIsRestoredConversation(false)
        initializeChat()
    }, [resumeSession?.sessionId])

    const quickPrompts = ["I want to add user authentication", "I need a dashboard with analytics", "Create a REST API for products", "Build a notification system"]

    const handleUsePRD = () => {
        if (generatedPRD) {
            onPRDComplete({
                project: generatedPRD.project,
                branchName: generatedPRD.branchName,
                description: generatedPRD.description,
                userStories: generatedPRD.userStories.map((s: any) => ({ ...s, passes: false }))
            })
        }
    }

    const handleSend = () => {
        if (input.trim()) {
            sendMessage(input)
            setInput('')
        }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    return (
        <AIPRDModal title="AI PRD Assistant" subtitle="Let me help you create your PRD" onCancel={onCancel} onMinimize={onMinimize} onSwitchToManual={onSwitchToManual} visible={visible}>
            <ChatArea messages={messages} isLoading={isLoading} quickPrompts={quickPrompts} onQuickPrompt={sendMessage} restoredConversation={isRestoredConversation} />
            <AnimatePresence>
                {showPreview && generatedPRD && (
                    <PRDPreviewPanel {...generatedPRD} userStoryCount={generatedPRD.userStories.length} onUse={handleUsePRD} onEdit={onSwitchToManual} onClose={() => setShowPreview(false)} />
                )}
            </AnimatePresence>
            <div className="px-4 py-2 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                <div className="flex items-center gap-4 flex-wrap">
                    <CodebaseSelector selectedCodebase={selectedCodebase || ''} codebases={codebases} onChange={setSelectedCodebase} />
                    <WorkerSelector value={selectedWorker || ''} onChange={setSelectedWorker} />
                    <ModelSelector visualVariant="compact" />
                </div>
            </div>
            <ChatInput value={input} onChange={setInput} onSubmit={handleSend} onKeyDown={handleKeyDown} disabled={isLoading} placeholder="Describe your feature..." />
        </AIPRDModal>
    )
}
