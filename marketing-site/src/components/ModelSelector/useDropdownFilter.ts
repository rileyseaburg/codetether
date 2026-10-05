import { useMemo } from 'react'

export const useDropdownFilter = (options: string[], search: string) => {
  // Keep the visible options and keyboard selection in the same render.
  // Debouncing only the results lets Enter commit a stale, unrelated model.
  return useMemo(() => {
    if (!search?.trim()) return options

    const s = search.toLowerCase().trim()
    if (!s) return options

    // Extract search terms: handle "provider/model", "provider:model", or free text
    const sepMatch = s.match(/[\/:]/)
    const sep = sepMatch ? sepMatch[0] : '/'
    const [searchProvider, ...searchModelParts] = s.split(sep)
    const searchModel = searchModelParts.join(sep)
    const searchWords = new Set(s.split(/[\/:\s]+/).filter((w) => w.length > 0))

    return options.filter((opt) => {
      const optSep = opt.includes('/') ? '/' : ':'
      const parts = opt.split(optSep)
      const provider = (parts[0] || '').toLowerCase()
      const model = parts.slice(1).join(optSep).toLowerCase()
      const full = opt.toLowerCase()

      // Exact or prefix match
      if (full.startsWith(s) || provider.startsWith(s) || model.startsWith(s))
        return true

      // Handle "provider/model" or "provider:model" format search
      if (searchProvider && searchModel) {
        const providerMatch =
          searchProvider.length <= 2 || provider.includes(searchProvider)
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
  }, [options, search])
}
