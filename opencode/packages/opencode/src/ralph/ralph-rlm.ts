import { Log } from "../util/log"
import { Token } from "../util/token"
import { RlmRouter } from "../tool/rlm-router"
import { RalphTypes } from "./types"

const log = Log.create({ service: "ralph-rlm" })

/**
 * Ralph RLM Integration
 *
 * Provides intelligent context compression for long-running Ralph sessions.
 * Uses the Recursive Language Model (RLM) approach to:
 *
 * 1. Compress progress.txt when it gets too large
 * 2. Summarize git history for cross-iteration context
 * 3. Maintain semantic understanding while reducing token count
 *
 * Key insight from RLM paper: Instead of losing context when it overflows,
 * we can use recursive sub-LM calls to compress and retain the important parts.
 */
export namespace RalphRlm {
  export interface CompressionResult {
    compressed: string
    originalTokens: number
    compressedTokens: number
    ratio: number
  }

  /**
   * Compress progress.txt using RLM
   *
   * The progress file accumulates learnings from each iteration.
   * When it grows too large, we compress it while preserving:
   * - Key patterns and gotchas discovered
   * - File paths and function names mentioned
   * - Error messages and their resolutions
   * - Decisions made and why
   */
  export async function compressProgress(
    progress: string,
    prd: RalphTypes.PRD,
    options: {
      targetTokens?: number
      sessionID: string
      abort: AbortSignal
    },
  ): Promise<CompressionResult> {
    const originalTokens = Token.estimate(progress)
    const targetTokens = options.targetTokens || Math.floor(originalTokens * 0.3)

    if (originalTokens < 10000) {
      // Not worth compressing
      return {
        compressed: progress,
        originalTokens,
        compressedTokens: originalTokens,
        ratio: 1,
      }
    }

    log.info("Compressing progress via RLM", {
      originalTokens,
      targetTokens,
      project: prd.project,
    })

    const completedStories = prd.userStories.filter((s) => s.passes).map((s) => `${s.id}: ${s.title}`)
    const remainingStories = prd.userStories.filter((s) => !s.passes).map((s) => `${s.id}: ${s.title}`)

    const query = `You are a MEMORY COMPRESSOR for an autonomous coding agent called Ralph.

Ralph is implementing user stories from a PRD. Each iteration is a fresh context, so the progress.txt file is the ONLY memory between iterations.

## Current Project State
- Project: ${prd.project}
- Branch: ${prd.branchName}
- Completed: ${completedStories.join(", ") || "none"}
- Remaining: ${remainingStories.join(", ") || "none (all done!)"}

## Your Task
Compress this progress log to ~${targetTokens} tokens while preserving:

1. **KEY PATTERNS** - What patterns work in this codebase?
2. **GOTCHAS** - What mistakes were made and how to avoid them?
3. **FILE PATHS** - Which files were modified and why?
4. **DECISIONS** - What architectural decisions were made?
5. **ERRORS** - What errors occurred and how were they resolved?

## Format
Output a compressed progress log that future Ralph iterations can use.
Be SPECIFIC - include actual file paths, function names, error messages.
Generic summaries are useless.

## Original Progress Log
${progress}`

    try {
      const result = await RlmRouter.autoProcess(progress, {
        toolId: "ralph_progress",
        toolArgs: {
          project: prd.project,
          completedStories: completedStories.length,
          remainingStories: remainingStories.length,
        },
        sessionID: options.sessionID,
        abort: options.abort,
      })

      const compressedTokens = Token.estimate(result.processed)

      log.info("Progress compression complete", {
        originalTokens,
        compressedTokens,
        ratio: (originalTokens / compressedTokens).toFixed(1),
      })

      return {
        compressed: result.processed,
        originalTokens,
        compressedTokens,
        ratio: originalTokens / compressedTokens,
      }
    } catch (e: any) {
      log.error("Progress compression failed", { error: e.message })
      // Fallback: simple truncation keeping recent entries
      return {
        compressed: simpleCompress(progress, targetTokens),
        originalTokens,
        compressedTokens: targetTokens,
        ratio: originalTokens / targetTokens,
      }
    }
  }

  /**
   * Simple fallback compression - keep header and recent entries
   */
  function simpleCompress(progress: string, targetTokens: number): string {
    const lines = progress.split("\n")
    const header = lines.slice(0, 5).join("\n")
    const entries = progress.split("---")

    // Keep header + last N entries that fit in target
    const result = [header, "", "[... earlier entries compressed ...]", ""]
    let currentTokens = Token.estimate(result.join("\n"))

    for (let i = entries.length - 1; i >= 0 && currentTokens < targetTokens; i--) {
      const entry = entries[i]
      const entryTokens = Token.estimate(entry)
      if (currentTokens + entryTokens < targetTokens) {
        result.push("---")
        result.push(entry)
        currentTokens += entryTokens
      }
    }

    return result.join("\n")
  }

  /**
   * Summarize git history for context
   *
   * When starting a new iteration, provide context about recent commits
   * without including the full diff (which would be too large).
   */
  export async function summarizeGitHistory(
    commits: Array<{ hash: string; message: string; files: string[] }>,
    options: {
      sessionID: string
      abort: AbortSignal
    },
  ): Promise<string> {
    if (commits.length === 0) {
      return "No previous commits in this branch."
    }

    const context = commits
      .map((c) => `Commit ${c.hash}: ${c.message}\n  Files: ${c.files.slice(0, 10).join(", ")}`)
      .join("\n\n")

    if (Token.estimate(context) < 5000) {
      return context
    }

    // Use RLM to compress
    const result = await RlmRouter.autoProcess(context, {
      toolId: "ralph_git_history",
      toolArgs: { commits: commits.length },
      sessionID: options.sessionID,
      abort: options.abort,
    })

    return result.processed
  }

  /**
   * Build iteration context with RLM compression if needed
   *
   * This is the main entry point for preparing context for a Ralph iteration.
   */
  export async function buildIterationContext(
    prd: RalphTypes.PRD,
    progress: string,
    gitCommits: Array<{ hash: string; message: string; files: string[] }>,
    options: {
      maxTokens?: number
      sessionID: string
      abort: AbortSignal
    },
  ): Promise<{
    progress: string
    gitSummary: string
    wasCompressed: boolean
  }> {
    const maxTokens = options.maxTokens || 50000
    let wasCompressed = false

    // Check if progress needs compression
    const progressTokens = Token.estimate(progress)
    let finalProgress = progress

    if (progressTokens > maxTokens * 0.6) {
      const compressed = await compressProgress(progress, prd, {
        targetTokens: Math.floor(maxTokens * 0.3),
        sessionID: options.sessionID,
        abort: options.abort,
      })
      finalProgress = compressed.compressed
      wasCompressed = compressed.ratio > 1.5
    }

    // Summarize git history
    const gitSummary = await summarizeGitHistory(gitCommits, {
      sessionID: options.sessionID,
      abort: options.abort,
    })

    return {
      progress: finalProgress,
      gitSummary,
      wasCompressed,
    }
  }
}
