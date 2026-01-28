import z from "zod"
import { Tool } from "./tool"
import { RlmRouter } from "./rlm-router"
import { Log } from "../util/log"
import { Token } from "../util/token"
import fs from "fs/promises"
import path from "path"
import { Instance } from "../project/instance"

const log = Log.create({ service: "rlm-tool" })

const DESCRIPTION = `Analyze large content using Recursive Language Model (RLM) processing.

Use this tool when you need to:
- Process content that exceeds your context window
- Analyze very large files (>50K tokens)
- Aggregate information across many documents or search results
- Perform semantic analysis that requires examining all parts of large data

The RLM loads content into a REPL environment and uses recursive sub-LM calls
to analyze it systematically, avoiding context overflow.

Examples:
- Analyzing a large codebase for patterns
- Summarizing hundreds of search results
- Processing massive log files
- Aggregating data from many sources

Note: This tool has higher latency and cost than direct processing.
Only use it when content is too large for normal analysis.`

export const RlmTool = Tool.define("rlm", async () => {
  return {
    description: DESCRIPTION,
    parameters: z.object({
      query: z.string().describe("The analysis query or question to answer about the content"),
      content: z.string().optional().describe("Direct content to analyze. Use this OR content_paths, not both."),
      content_paths: z
        .array(z.string())
        .optional()
        .describe("File paths to read and analyze. Content will be concatenated."),
      context_type: z
        .enum(["code", "documents", "logs", "conversation", "auto"])
        .optional()
        .default("auto")
        .describe("Type of content for optimized analysis. Default: auto-detect"),
    }),
    async execute(params, ctx) {
      const startTime = Date.now()
      let content = ""
      let sources: string[] = []

      // Gather content from paths or direct input
      if (params.content_paths && params.content_paths.length > 0) {
        const parts: string[] = []
        for (const p of params.content_paths) {
          const resolved = path.isAbsolute(p) ? p : path.join(Instance.directory, p)
          try {
            const fileContent = await fs.readFile(resolved, "utf-8")
            parts.push(`=== FILE: ${p} ===\n${fileContent}\n=== END FILE ===\n`)
            sources.push(p)
          } catch (e: any) {
            parts.push(`=== FILE: ${p} ===\nError reading file: ${e?.message}\n=== END FILE ===\n`)
          }
        }
        content = parts.join("\n")
      } else if (params.content) {
        content = params.content
        sources.push("direct_input")
      } else {
        throw new Error("Either 'content' or 'content_paths' must be provided")
      }

      const inputTokens = Token.estimate(content)
      log.info("RLM tool invoked", {
        query: params.query.slice(0, 100),
        inputTokens,
        sources: sources.length,
        contextType: params.context_type,
      })

      // If content is small enough, just return it with a note
      if (inputTokens < 10000) {
        return {
          title: "RLM Analysis (small input)",
          metadata: {
            inputTokens,
            outputTokens: inputTokens,
            iterations: 0,
            subcalls: 0,
            elapsed: 0,
            sources,
            truncated: false,
          },
          output: `Note: Content is only ${inputTokens.toLocaleString()} tokens - direct analysis would be more efficient.\n\n${content}`,
        }
      }

      ctx.metadata({
        title: "RLM Processing...",
        metadata: {
          inputTokens,
          status: "processing",
          sources,
        },
      })

      // Build context-aware query
      const contextHint = params.context_type !== "auto" ? `\n\nContext type: ${params.context_type}` : ""
      const fullQuery = params.query + contextHint

      try {
        const result = await RlmRouter.autoProcess(content, {
          toolId: "rlm_manual",
          toolArgs: {
            query: fullQuery,
            sources,
            contextType: params.context_type,
          },
          sessionID: ctx.sessionID,
          abort: ctx.abort,
          onProgress: (progress) => {
            ctx.metadata({
              title: `RLM: Step ${progress.iteration}/${progress.maxIterations}`,
              metadata: {
                inputTokens,
                iteration: progress.iteration,
                maxIterations: progress.maxIterations,
                status: progress.status,
                sources,
              },
            })
          },
        })

        const elapsed = Date.now() - startTime
        log.info("RLM tool completed", {
          inputTokens: result.stats.inputTokens,
          outputTokens: result.stats.outputTokens,
          iterations: result.stats.iterations,
          subcalls: result.stats.subcalls,
          elapsed,
        })

        return {
          title: `RLM Analysis (${result.stats.iterations} iterations)`,
          metadata: {
            inputTokens: result.stats.inputTokens,
            outputTokens: result.stats.outputTokens,
            iterations: result.stats.iterations,
            subcalls: result.stats.subcalls,
            elapsed,
            sources,
            truncated: false, // RLM handles its own truncation
          },
          output: result.processed,
        }
      } catch (e: any) {
        log.error("RLM tool failed", { error: e })
        const elapsed = Date.now() - startTime
        return {
          title: "RLM Analysis Failed",
          metadata: {
            inputTokens,
            outputTokens: 0,
            iterations: 0,
            subcalls: 0,
            elapsed,
            sources,
            truncated: true,
            error: e?.message,
          },
          output: `RLM processing failed: ${e?.message}\n\nFallback: Showing first 5000 characters of content:\n\n${content.slice(0, 5000)}...`,
        }
      }
    },
  }
})
