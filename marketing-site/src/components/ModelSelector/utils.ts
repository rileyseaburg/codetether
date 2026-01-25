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
