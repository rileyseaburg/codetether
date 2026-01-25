import { useState, useEffect, useMemo, useRef } from 'react'

const debounce = <T extends (...args: any[]) => any>(fn: T, ms: number): ((...args: Parameters<T>) => void) => {
    const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
    return (...args: Parameters<T>) => {
        clearTimeout(timer.current)
        timer.current = setTimeout(() => fn(...args), ms)
    }
}

export const useDropdownFilter = (options: string[], search: string) => {
    const [debouncedSearch, setDebouncedSearch] = useState(search)
    
    const debouncedSetSearch = useRef(debounce((s: string) => setDebouncedSearch(s), 100))
    
    useEffect(() => {
        debouncedSetSearch.current(search)
    }, [search])
    
    return useMemo(() => {
        if (!debouncedSearch?.trim()) return options
        
        const s = debouncedSearch.toLowerCase().trim()
        if (!s) return options
        
        // Extract search terms: handle "provider:model" or just free text
        const [searchProvider, ...searchModelParts] = s.split(':')
        const searchModel = searchModelParts.join(':')
        const searchWords = new Set(s.split(/[:\s]+/).filter(w => w.length > 0))
        
        return options.filter(opt => {
            const parts = opt.split(':')
            const provider = (parts[0] || '').toLowerCase()
            const model = parts.slice(1).join(':').toLowerCase()
            const full = opt.toLowerCase()
            
            // Exact or prefix match
            if (full.startsWith(s) || provider.startsWith(s) || model.startsWith(s)) return true
            
            // Handle "provider:model" format search
            if (searchProvider && searchModel) {
                const providerMatch = searchProvider.length <= 2 || provider.includes(searchProvider)
                const modelMatch = !searchModel || model.includes(searchModel)
                if (providerMatch && modelMatch) return true
            }
            
            // Word-based matching
            let score = 0
            for (const word of searchWords) {
                if (provider.includes(word) || model.includes(word)) {
                    score += 1
                } else {
                    // Fuzzy match for this word
                    let matches = 0
                    let searchFull = full
                    for (let i = 0; i < word.length; i++) {
                        const idx = searchFull.indexOf(word[i])
                        if (idx === -1) break
                        searchFull = searchFull.slice(idx + 1)
                        matches++
                    }
                    if (matches / word.length >= 0.6) score += 0.5
                }
            }
            
            return score >= searchWords.size * 0.5
        })
    }, [options, debouncedSearch])
}
