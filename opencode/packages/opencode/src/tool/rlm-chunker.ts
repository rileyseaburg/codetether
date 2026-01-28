import { Token } from "../util/token"

/**
 * Semantic chunking for large contexts.
 * Splits content intelligently at natural boundaries.
 */
export namespace RlmChunker {
  export type ContentType = "code" | "documents" | "logs" | "conversation" | "mixed"

  export interface Chunk {
    content: string
    type: "code" | "text" | "tool_output" | "conversation"
    startLine: number
    endLine: number
    tokens: number
    priority: number // Higher = more important to keep
  }

  /**
   * Detect the primary type of content for optimized processing.
   */
  export function detectContentType(content: string): ContentType {
    const lines = content.split("\n")
    const sampleSize = Math.min(lines.length, 200)
    const sample = lines.slice(0, sampleSize / 2).concat(lines.slice(-sampleSize / 2))

    let codeIndicators = 0
    let logIndicators = 0
    let conversationIndicators = 0
    let documentIndicators = 0

    for (const line of sample) {
      const trimmed = line.trim()

      // Code indicators
      if (
        trimmed.match(/^(function|class|def |const |let |var |import |export |async |fn |impl |struct |enum |pub )/) ||
        trimmed.match(/^[{}();]$/) ||
        trimmed.match(/^\s*\/\/|^\s*#|^\s*\*|^\s*\/\*/)
      ) {
        codeIndicators++
      }

      // Log indicators
      if (
        trimmed.match(/^\d{4}-\d{2}-\d{2}/) || // ISO date
        trimmed.match(/^\[\d{2}:\d{2}/) || // Time prefix
        trimmed.match(/^(INFO|DEBUG|WARN|ERROR|FATAL)\s*[:\[]/) ||
        trimmed.match(/^\[.*\]\s+(INFO|DEBUG|WARN|ERROR)/)
      ) {
        logIndicators++
      }

      // Conversation indicators
      if (
        trimmed.match(/^\[(User|Assistant|Human|AI)\]:/) ||
        trimmed.match(/^(User|Assistant|Human|AI):/) ||
        trimmed.match(/^\[Tool \w+/) ||
        trimmed.match(/^<(user|assistant|system)>/)
      ) {
        conversationIndicators++
      }

      // Document indicators (markdown, prose)
      if (
        trimmed.match(/^#{1,6}\s/) || // Markdown headers
        trimmed.match(/^\*\*.*\*\*/) || // Bold text
        trimmed.match(/^>\s/) || // Blockquotes
        trimmed.match(/^-\s+\w/) || // List items
        (trimmed.length > 80 && !trimmed.match(/[{}();=]$/)) // Long prose lines
      ) {
        documentIndicators++
      }
    }

    const total = codeIndicators + logIndicators + conversationIndicators + documentIndicators
    if (total === 0) return "mixed"

    const threshold = total * 0.3 // 30% threshold for classification

    if (conversationIndicators > threshold) return "conversation"
    if (logIndicators > threshold) return "logs"
    if (codeIndicators > threshold) return "code"
    if (documentIndicators > threshold) return "documents"

    return "mixed"
  }

  /**
   * Get processing hints based on content type.
   */
  export function getProcessingHints(type: ContentType): string {
    switch (type) {
      case "code":
        return `This appears to be source code. Focus on:
- Function/class definitions and their purposes
- Import statements and dependencies
- Error handling patterns
- Key algorithms and logic flow`

      case "logs":
        return `This appears to be log output. Focus on:
- Error and warning messages
- Timestamps and event sequences
- Stack traces and exceptions
- Key events and state changes`

      case "conversation":
        return `This appears to be conversation history. Focus on:
- User's original request/goal
- Key decisions made
- Tool calls and their results
- Current state and pending tasks`

      case "documents":
        return `This appears to be documentation or prose. Focus on:
- Main topics and structure
- Key information and facts
- Actionable items
- References and links`

      default:
        return `Mixed content detected. Analyze the structure first, then extract key information.`
    }
  }

  export interface ChunkOptions {
    maxChunkTokens?: number
    preserveRecent?: number // Number of recent lines to always preserve
  }

  const DEFAULT_MAX_CHUNK = 4000
  const DEFAULT_PRESERVE_RECENT = 100

  /**
   * Split content into semantic chunks.
   */
  export function chunk(content: string, options?: ChunkOptions): Chunk[] {
    const maxTokens = options?.maxChunkTokens ?? DEFAULT_MAX_CHUNK
    const preserveRecent = options?.preserveRecent ?? DEFAULT_PRESERVE_RECENT

    const lines = content.split("\n")
    const chunks: Chunk[] = []

    // Identify boundaries
    const boundaries = findBoundaries(lines)

    let currentChunk: string[] = []
    let currentType: Chunk["type"] = "text"
    let currentStart = 0
    let currentPriority = 1

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]
      const boundary = boundaries.get(i)

      // Check if we hit a boundary
      if (boundary && currentChunk.length > 0) {
        const content = currentChunk.join("\n")
        const tokens = Token.estimate(content)

        // If chunk is too big, split it
        if (tokens > maxTokens) {
          const subChunks = splitLargeChunk(currentChunk, currentStart, currentType, maxTokens)
          chunks.push(...subChunks)
        } else {
          chunks.push({
            content,
            type: currentType,
            startLine: currentStart,
            endLine: i - 1,
            tokens,
            priority: currentPriority,
          })
        }

        currentChunk = []
        currentStart = i
        currentType = boundary.type
        currentPriority = boundary.priority
      }

      currentChunk.push(line)

      // Boost priority for recent lines
      if (i >= lines.length - preserveRecent) {
        currentPriority = Math.max(currentPriority, 8)
      }
    }

    // Don't forget the last chunk
    if (currentChunk.length > 0) {
      const content = currentChunk.join("\n")
      const tokens = Token.estimate(content)

      if (tokens > maxTokens) {
        const subChunks = splitLargeChunk(currentChunk, currentStart, currentType, maxTokens)
        chunks.push(...subChunks)
      } else {
        chunks.push({
          content,
          type: currentType,
          startLine: currentStart,
          endLine: lines.length - 1,
          tokens,
          priority: currentPriority,
        })
      }
    }

    return chunks
  }

  /**
   * Find semantic boundaries in content.
   */
  function findBoundaries(lines: string[]): Map<number, { type: Chunk["type"]; priority: number }> {
    const boundaries = new Map<number, { type: Chunk["type"]; priority: number }>()

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]
      const trimmed = line.trim()

      // User/Assistant message markers
      if (trimmed.startsWith("[User]:") || trimmed.startsWith("[Assistant]:")) {
        boundaries.set(i, { type: "conversation", priority: 5 })
        continue
      }

      // Tool output markers
      if (trimmed.startsWith("[Tool ")) {
        const isError = trimmed.includes("FAILED") || trimmed.includes("error")
        boundaries.set(i, { type: "tool_output", priority: isError ? 7 : 3 })
        continue
      }

      // Code block markers
      if (trimmed.startsWith("```")) {
        boundaries.set(i, { type: "code", priority: 4 })
        continue
      }

      // File path markers (likely file contents)
      if (trimmed.match(/^(\/|\.\/|~\/|[A-Z]:)/)) {
        boundaries.set(i, { type: "code", priority: 4 })
        continue
      }

      // Function/class definitions
      if (trimmed.match(/^(function|class|def |async function|export|const \w+ = \(|fn |impl |struct |enum )/)) {
        boundaries.set(i, { type: "code", priority: 5 })
        continue
      }

      // Error markers
      if (trimmed.match(/^(Error|error:|ERROR|Exception|FAILED|failed:)/i)) {
        boundaries.set(i, { type: "text", priority: 8 })
        continue
      }

      // Section headers (markdown)
      if (trimmed.match(/^#{1,3}\s/)) {
        boundaries.set(i, { type: "text", priority: 6 })
        continue
      }
    }

    return boundaries
  }

  /**
   * Split a large chunk into smaller pieces.
   */
  function splitLargeChunk(lines: string[], startLine: number, type: Chunk["type"], maxTokens: number): Chunk[] {
    const chunks: Chunk[] = []
    let current: string[] = []
    let currentTokens = 0
    let currentStart = startLine

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]
      const lineTokens = Token.estimate(line)

      if (currentTokens + lineTokens > maxTokens && current.length > 0) {
        chunks.push({
          content: current.join("\n"),
          type,
          startLine: currentStart,
          endLine: startLine + i - 1,
          tokens: currentTokens,
          priority: 3,
        })
        current = []
        currentTokens = 0
        currentStart = startLine + i
      }

      current.push(line)
      currentTokens += lineTokens
    }

    if (current.length > 0) {
      chunks.push({
        content: current.join("\n"),
        type,
        startLine: currentStart,
        endLine: startLine + lines.length - 1,
        tokens: currentTokens,
        priority: 3,
      })
    }

    return chunks
  }

  /**
   * Select chunks to fit within a token budget.
   * Prioritizes high-priority chunks and recent content.
   */
  export function selectChunks(chunks: Chunk[], maxTokens: number): Chunk[] {
    // Sort by priority (descending), then by line number (descending for recent)
    const sorted = [...chunks].sort((a, b) => {
      if (b.priority !== a.priority) return b.priority - a.priority
      return b.startLine - a.startLine
    })

    const selected: Chunk[] = []
    let totalTokens = 0

    for (const chunk of sorted) {
      if (totalTokens + chunk.tokens <= maxTokens) {
        selected.push(chunk)
        totalTokens += chunk.tokens
      }
    }

    // Re-sort by line number for coherent output
    selected.sort((a, b) => a.startLine - b.startLine)

    return selected
  }

  /**
   * Reassemble selected chunks into a single string.
   */
  export function reassemble(chunks: Chunk[]): string {
    if (chunks.length === 0) return ""

    const parts: string[] = []
    let lastEnd = -1

    for (const chunk of chunks) {
      // Add separator if there's a gap
      if (lastEnd !== -1 && chunk.startLine > lastEnd + 1) {
        parts.push(`\n[... ${chunk.startLine - lastEnd - 1} lines omitted ...]\n`)
      }
      parts.push(chunk.content)
      lastEnd = chunk.endLine
    }

    return parts.join("\n")
  }

  /**
   * Intelligently compress content to fit within token budget.
   */
  export function compress(content: string, maxTokens: number, options?: ChunkOptions): string {
    const chunks = chunk(content, options)
    const selected = selectChunks(chunks, maxTokens)
    return reassemble(selected)
  }
}
