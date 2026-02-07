export const parseModel = (modelStr: string) => {
    const [provider, ...modelParts] = modelStr.split(':')
    return { provider: provider || '', model: modelParts.join(':') || '' }
}

export const fuzzyMatch = (search: string, text: string, threshold = 0.6) => {
    const searchLower = search.toLowerCase().replace(/\s+/g, '')
    const textLower = text.toLowerCase().replace(/\s+/g, '')
    if (!searchLower) return true
    if (textLower.includes(searchLower)) return true
    const searchChars = searchLower.split('')
    const textChars = textLower.split('')
    let matchCount = 0
    let textIndex = 0
    for (let i = 0; i < searchChars.length; i++) {
        while (textIndex < textChars.length && textChars[textIndex] !== searchChars[i]) textIndex++
        if (textIndex < textChars.length) { matchCount++; textIndex++ }
    }
    return matchCount / searchChars.length >= threshold
}

// ============================================================================
// Provider route classification
// ============================================================================

export type RouteCategory = 'direct' | 'proxy' | 'cloud' | 'free' | 'china' | 'enterprise' | 'community'

export interface ProviderInfo {
    label: string
    category: RouteCategory
    /** Short tag shown in the dropdown, e.g. "Direct", "via OpenRouter" */
    badge: string
    /** Tailwind text/bg classes */
    badgeColor: string
    /** Approximate relative cost hint */
    costHint?: '$' | '$$' | '$$$' | 'free' | '~'
}

const ROUTE_CATEGORIES: Record<RouteCategory, { badgeColor: string }> = {
    direct: { badgeColor: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300' },
    proxy: { badgeColor: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300' },
    cloud: { badgeColor: 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300' },
    free: { badgeColor: 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300' },
    china: { badgeColor: 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300' },
    enterprise: { badgeColor: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300' },
    community: { badgeColor: 'bg-gray-100 text-gray-700 dark:bg-gray-700/40 dark:text-gray-300' },
}

// Maps provider slug → classification
const PROVIDER_MAP: Record<string, { label: string; category: RouteCategory; costHint?: ProviderInfo['costHint'] }> = {
    // Direct API providers
    'openai': { label: 'OpenAI', category: 'direct', costHint: '$$' },
    'anthropic': { label: 'Anthropic', category: 'direct', costHint: '$$' },
    'google': { label: 'Google', category: 'direct', costHint: '$$' },
    'mistral': { label: 'Mistral', category: 'direct', costHint: '$' },
    'xai': { label: 'xAI', category: 'direct', costHint: '$$' },
    'cohere': { label: 'Cohere', category: 'direct', costHint: '$' },
    'deepseek': { label: 'DeepSeek', category: 'direct', costHint: '$' },
    'perplexity': { label: 'Perplexity', category: 'direct', costHint: '$$' },

    // Proxy / aggregator routes
    'openrouter': { label: 'OpenRouter', category: 'proxy', costHint: '~' },
    'helicone': { label: 'Helicone', category: 'proxy', costHint: '~' },
    'requesty': { label: 'Requesty', category: 'proxy', costHint: '~' },
    'zenmux': { label: 'Zenmux', category: 'proxy', costHint: '~' },
    'fastrouter': { label: 'FastRouter', category: 'proxy', costHint: '~' },
    'aihubmix': { label: 'AI Hub Mix', category: 'proxy', costHint: '~' },

    // Cloud platform routes
    'azure': { label: 'Azure', category: 'cloud', costHint: '$$$' },
    'amazon-bedrock': { label: 'AWS Bedrock', category: 'cloud', costHint: '$$$' },
    'google-vertex': { label: 'Vertex AI', category: 'cloud', costHint: '$$$' },
    'google-vertex-anthropic': { label: 'Vertex (Anthropic)', category: 'cloud', costHint: '$$$' },
    'azure-anthropic': { label: 'Azure (Anthropic)', category: 'cloud', costHint: '$$$' },
    'azure-cognitive-services': { label: 'Azure Cognitive', category: 'cloud', costHint: '$$$' },
    'sap-ai-core': { label: 'SAP AI Core', category: 'cloud', costHint: '$$$' },
    'vercel': { label: 'Vercel AI', category: 'cloud', costHint: '$$' },
    'cloudflare-workers-ai': { label: 'CF Workers AI', category: 'cloud', costHint: '$' },
    'cloudflare-ai-gateway': { label: 'CF AI Gateway', category: 'cloud', costHint: '$' },

    // Free / low-cost tiers
    'github-copilot': { label: 'Copilot', category: 'free', costHint: 'free' },
    'github-models': { label: 'GitHub Models', category: 'free', costHint: 'free' },
    'ollama-cloud': { label: 'Ollama', category: 'free', costHint: 'free' },
    'lmstudio': { label: 'LM Studio', category: 'free', costHint: 'free' },
    'poe': { label: 'Poe', category: 'free', costHint: 'free' },

    // China-region providers
    'alibaba-cn': { label: 'Alibaba CN', category: 'china', costHint: '$' },
    'alibaba': { label: 'Alibaba', category: 'china', costHint: '$' },
    'siliconflow-cn': { label: 'SiliconFlow CN', category: 'china', costHint: '$' },
    'siliconflow': { label: 'SiliconFlow', category: 'china', costHint: '$' },
    'zhipuai': { label: 'ZhipuAI', category: 'china', costHint: '$' },
    'zhipuai-coding-plan': { label: 'ZhipuAI Coding', category: 'china', costHint: '$' },
    'moonshotai': { label: 'Moonshot', category: 'china', costHint: '$' },
    'moonshotai-cn': { label: 'Moonshot CN', category: 'china', costHint: '$' },
    'minimax': { label: 'MiniMax', category: 'china', costHint: '$' },
    'minimax-cn': { label: 'MiniMax CN', category: 'china', costHint: '$' },
    'minimax-m2': { label: 'MiniMax M2', category: 'china', costHint: '$' },
    'minimax-coding-plan': { label: 'MiniMax Coding', category: 'china', costHint: '$' },
    'minimax-cn-coding-plan': { label: 'MiniMax CN Coding', category: 'china', costHint: '$' },
    'stepfun': { label: 'StepFun', category: 'china', costHint: '$' },
    'iflowcn': { label: 'iFlow CN', category: 'china', costHint: '$' },
    'modelscope': { label: 'ModelScope', category: 'china', costHint: '$' },
    'bailing': { label: 'Bailing', category: 'china', costHint: '$' },
    'kimi-for-coding': { label: 'Kimi', category: 'china', costHint: '$' },
    'xiaomi': { label: 'Xiaomi', category: 'china', costHint: '$' },

    // Enterprise / specialty
    'nvidia': { label: 'NVIDIA', category: 'enterprise', costHint: '$$' },
    'fireworks-ai': { label: 'Fireworks', category: 'enterprise', costHint: '$' },
    'groq': { label: 'Groq', category: 'enterprise', costHint: '$' },
    'cerebras': { label: 'Cerebras', category: 'enterprise', costHint: '$' },
    'togetherai': { label: 'Together AI', category: 'enterprise', costHint: '$' },
    'deepinfra': { label: 'DeepInfra', category: 'enterprise', costHint: '$' },
    'novita-ai': { label: 'Novita AI', category: 'enterprise', costHint: '$' },
    'novita': { label: 'Novita', category: 'enterprise', costHint: '$' },
    'nebius': { label: 'Nebius', category: 'enterprise', costHint: '$' },
    'scaleway': { label: 'Scaleway', category: 'enterprise', costHint: '$' },
    'ovhcloud': { label: 'OVHcloud', category: 'enterprise', costHint: '$' },
    'vultr': { label: 'Vultr', category: 'enterprise', costHint: '$' },
    'baseten': { label: 'Baseten', category: 'enterprise', costHint: '$' },
    'inference': { label: 'Inference', category: 'enterprise', costHint: '$' },
    'upstage': { label: 'Upstage', category: 'enterprise', costHint: '$' },

    // Community / misc
    'huggingface': { label: 'HuggingFace', category: 'community', costHint: '~' },
    'chutes': { label: 'Chutes', category: 'community', costHint: '$' },
    'wandb': { label: 'W&B', category: 'community', costHint: '~' },
    'abacus': { label: 'Abacus', category: 'community', costHint: '$' },
    'io-net': { label: 'io.net', category: 'community', costHint: '$' },
    'cortecs': { label: 'Cortecs', category: 'community', costHint: '$' },
    'vivgrid': { label: 'VivGrid', category: 'community', costHint: '$' },
    'friendli': { label: 'Friendli', category: 'community', costHint: '$' },
    'submodel': { label: 'Submodel', category: 'community', costHint: '$' },
    'morph': { label: 'Morph', category: 'community', costHint: '$' },
    'inception': { label: 'Inception', category: 'community', costHint: '$' },
    'moark': { label: 'Moark', category: 'community', costHint: '$' },
    'lucidquery': { label: 'LucidQuery', category: 'community', costHint: '$' },
    'privatemode-ai': { label: 'PrivateMode', category: 'community', costHint: '$' },

    // Platform-specific
    'opencode': { label: 'OpenCode', category: 'direct', costHint: '~' },
    'gitlab': { label: 'GitLab', category: 'enterprise', costHint: '$$' },
    'v0': { label: 'v0', category: 'free', costHint: 'free' },
    'llama': { label: 'Llama', category: 'community', costHint: '$' },
    'synthetic': { label: 'Synthetic', category: 'community', costHint: '$' },
    'firmware': { label: 'Firmware', category: 'community', costHint: '$' },
    'nano-gpt': { label: 'NanoGPT', category: 'community', costHint: '$' },
    'venice': { label: 'Venice', category: 'community', costHint: '$' },
    'zai': { label: 'Zai', category: 'enterprise', costHint: '$' },
    'zai-coding-plan': { label: 'Zai Coding', category: 'enterprise', costHint: '$' },
}

const CATEGORY_LABELS: Record<RouteCategory, string> = {
    direct: 'Direct',
    proxy: 'Proxy',
    cloud: 'Cloud',
    free: 'Free',
    china: 'CN',
    enterprise: 'Infra',
    community: 'Community',
}

const COST_ICONS: Record<string, string> = {
    'free': '🆓',
    '$': '💲',
    '$$': '💲💲',
    '$$$': '💲💲💲',
    '~': '≈',
}

export function getProviderInfo(providerSlug: string): ProviderInfo {
    const entry = PROVIDER_MAP[providerSlug.toLowerCase()]
    if (entry) {
        const cat = ROUTE_CATEGORIES[entry.category]
        return {
            label: entry.label,
            category: entry.category,
            badge: CATEGORY_LABELS[entry.category],
            badgeColor: cat.badgeColor,
            costHint: entry.costHint,
        }
    }
    // Fallback: unknown provider
    return {
        label: providerSlug,
        category: 'community',
        badge: 'Other',
        badgeColor: ROUTE_CATEGORIES.community.badgeColor,
        costHint: '~',
    }
}

export function getCostIcon(costHint?: ProviderInfo['costHint']): string {
    return costHint ? (COST_ICONS[costHint] || '') : ''
}
