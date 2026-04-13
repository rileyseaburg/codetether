import { useState, useCallback, useMemo } from 'react'
import type { AgentDefinition } from '../types'

interface UseAgentDefinitionsReturn {
    agentDefinitions: AgentDefinition[]
    setAgentDefinitions: React.Dispatch<React.SetStateAction<AgentDefinition[]>>
    buildAgents: AgentDefinition[]
    planAgents: AgentDefinition[]
    exploreAgents: AgentDefinition[]
    generalAgents: AgentDefinition[]
}

export function useAgentDefinitions(): UseAgentDefinitionsReturn {
    const [agentDefinitions, setAgentDefinitions] = useState<AgentDefinition[]>([])

    const buildAgents = useMemo(
        () => agentDefinitions.filter((a) => a.mode === 'build' && !a.hidden),
        [agentDefinitions]
    )
    const planAgents = useMemo(
        () => agentDefinitions.filter((a) => a.mode === 'plan' && !a.hidden),
        [agentDefinitions]
    )
    const exploreAgents = useMemo(
        () => agentDefinitions.filter((a) => a.mode === 'explore' && !a.hidden),
        [agentDefinitions]
    )
    const generalAgents = useMemo(
        () => agentDefinitions.filter((a) => a.mode === 'general' && !a.hidden),
        [agentDefinitions]
    )

    return {
        agentDefinitions,
        setAgentDefinitions,
        buildAgents,
        planAgents,
        exploreAgents,
        generalAgents,
    }
}
