'use client'

import { useRalphStore, useAvailableModels } from '../app/(dashboard)/dashboard/ralph/store'
import { SessionsSelector, CompactSelector, CardSelector, DefaultSelector } from './ModelSelector/variants'

export interface ModelSelectorProps {
    visualVariant?: 'default' | 'compact' | 'card' | 'sessions'
    showSelectedInfo?: boolean
    showEmptyState?: boolean
    showCountBadge?: boolean
    hasCountBadge?: boolean  // Alias for showCountBadge
    label?: string
    className?: string
    disabled?: boolean
}

export function ModelSelector({
    visualVariant = 'default',
    showSelectedInfo = true,
    showEmptyState = true,
    showCountBadge,
    hasCountBadge,
    label = 'Model',
    className = '',
    disabled = false
}: ModelSelectorProps) {
    const { selectedModel, setSelectedModel, loadingAgents } = useRalphStore()
    const availableModels = useAvailableModels()

    const Comp = (() => {
        switch (visualVariant) {
            case 'sessions': return { comp: SessionsSelector, hasBadge: true }
            case 'compact': return { comp: CompactSelector, hasBadge: false }
            case 'card': return { comp: CardSelector, hasBadge: false }
            default: return { comp: DefaultSelector, hasBadge: false }
        }
    })()

    // Use hasCountBadge or showCountBadge, fallback to variant default
    const showBadge = hasCountBadge ?? showCountBadge ?? Comp.hasBadge

    return (
        <Comp.comp
            selectedModel={selectedModel}
            setSelectedModel={disabled ? () => {} : setSelectedModel}
            availableModels={availableModels}
            loadingAgents={loadingAgents}
            showSelectedInfo={showSelectedInfo}
            showEmptyState={showEmptyState}
            hasCountBadge={showBadge}
            label={label}
            className={`${className}${disabled ? ' opacity-50 pointer-events-none' : ''}`}
        />
    )
}
