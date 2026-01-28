import { Log } from "../util/log"
import { MessageV2 } from "./message-v2"
import { Session } from "."
import { Identifier } from "../id/id"
import { RlmRouter } from "../tool/rlm-router"
import type { Provider } from "../provider/provider"
import { Config } from "../config/config"
import { Instance } from "../project/instance"
import { ulid } from "ulid"
import { Bus } from "../bus"
import { BusEvent } from "../bus/bus-event"
import { SessionStatus } from "./status"
import z from "zod"

const log = Log.create({ service: "session.rlm" })

export namespace SessionRlm {
  // Default RLM model
  const DEFAULT_RLM_MODEL = "zai-coding-plan:glm-4.7"

  // Events for UI feedback
  export const Event = {
    Started: BusEvent.define(
      "rlm.started",
      z.object({
        sessionID: z.string(),
        contextLength: z.number(),
        reason: z.enum(["overflow", "validation"]),
      }),
    ),
    Progress: BusEvent.define(
      "rlm.progress",
      z.object({
        sessionID: z.string(),
        phase: z.enum(["analyzing", "summarizing", "completing"]),
        detail: z.string().optional(),
      }),
    ),
    Completed: BusEvent.define(
      "rlm.completed",
      z.object({
        sessionID: z.string(),
        inputTokens: z.number(),
        outputTokens: z.number(),
        compressionRatio: z.number(),
      }),
    ),
    Failed: BusEvent.define(
      "rlm.failed",
      z.object({
        sessionID: z.string(),
        error: z.string(),
      }),
    ),
  }

  function parseModelRef(ref: string): { providerID: string; modelID: string } {
    const idx = ref.indexOf(":")
    if (idx === -1) return { providerID: ref, modelID: ref }
    return { providerID: ref.slice(0, idx), modelID: ref.slice(idx + 1) }
  }

  /**
   * Process a session through RLM when context overflows.
   * Uses RlmRouter.autoProcess which properly puts context in a Python REPL
   * instead of the LLM's context window, avoiding the overflow loop.
   */
  export async function process(input: {
    sessionID: string
    messages: MessageV2.WithParts[]
    abort: AbortSignal
    model: Provider.Model
    reason?: "overflow" | "validation"
  }) {
    const contextInfo = analyzeContext(input.messages)
    log.info("Processing session through RLM", {
      sessionID: input.sessionID,
      ...contextInfo.stats,
    })

    Bus.publish(Event.Started, {
      sessionID: input.sessionID,
      contextLength: contextInfo.context.length,
      reason: input.reason ?? "overflow",
    })

    SessionStatus.set(input.sessionID, {
      type: "rlm",
      phase: "started",
      detail: `Compressing ${contextInfo.stats.messageCount} messages...`,
    })

    // Get RLM model from config or use default
    const config = await Config.get()
    const rlmModelRef = config.rlm?.subcall_model || DEFAULT_RLM_MODEL
    const rlmModel = parseModelRef(rlmModelRef)

    // Find the last user message to get their query
    const lastUserMsg = input.messages.findLast((m) => m.info.role === "user")
    const lastUserText = lastUserMsg?.parts.find((p) => p.type === "text")
    const query = lastUserText && "text" in lastUserText ? lastUserText.text : "Continue the conversation"

    // Create an assistant message for the RLM response
    const assistantMsg = (await Session.updateMessage({
      id: Identifier.ascending("message"),
      role: "assistant",
      parentID: lastUserMsg?.info.id ?? input.messages[input.messages.length - 1].info.id,
      sessionID: input.sessionID,
      mode: "rlm",
      agent: "code",
      path: {
        cwd: Instance.directory,
        root: Instance.worktree,
      },
      cost: 0,
      tokens: {
        input: 0,
        output: 0,
        reasoning: 0,
        cache: { read: 0, write: 0 },
      },
      modelID: rlmModel.modelID,
      providerID: rlmModel.providerID,
      time: {
        created: Date.now(),
      },
    })) as MessageV2.Assistant

    // Create a tool part for the RLM execution
    const toolPart = (await Session.updatePart({
      id: Identifier.ascending("part"),
      messageID: assistantMsg.id,
      sessionID: input.sessionID,
      type: "tool",
      tool: "rlm",
      callID: ulid(),
      state: {
        status: "running",
        input: {
          reason: input.reason ?? "overflow",
          stats: contextInfo.stats,
        },
        time: { start: Date.now() },
      },
    })) as MessageV2.ToolPart

    try {
      Bus.publish(Event.Progress, {
        sessionID: input.sessionID,
        phase: "analyzing",
        detail: `${contextInfo.stats.messageCount} messages, ${contextInfo.stats.toolCalls} tool calls`,
      })

      SessionStatus.set(input.sessionID, {
        type: "rlm",
        phase: "analyzing",
        detail: `${contextInfo.stats.toolCalls} tool calls`,
      })

      // Use RlmRouter.autoProcess to create a summary of the conversation
      const result = await RlmRouter.autoProcess(contextInfo.context, {
        toolId: "session_context",
        toolArgs: {
          query,
          metadata: contextInfo.metadata,
        },
        sessionID: input.sessionID,
        abort: input.abort,
        onProgress: (progress) => {
          const phase = progress.status === "completed" ? "completing" : "summarizing"
          Bus.publish(Event.Progress, {
            sessionID: input.sessionID,
            phase,
            detail: `Iteration ${progress.iteration}/${progress.maxIterations}`,
          })
          SessionStatus.set(input.sessionID, {
            type: "rlm",
            phase,
            detail: `Step ${progress.iteration}/${progress.maxIterations}`,
          })
        },
      })

      // Update the tool part with the result
      const startTime = "time" in toolPart.state ? toolPart.state.time.start : Date.now()
      await Session.updatePart({
        ...toolPart,
        state: {
          status: "completed",
          input: toolPart.state.input,
          output: result.processed,
          title: "Context Compressed",
          metadata: {
            stats: result.stats,
            filesModified: contextInfo.metadata.filesModified,
            pendingTasks: contextInfo.metadata.pendingTasks,
          },
          time: {
            start: startTime,
            end: Date.now(),
          },
        },
      })

      // Mark this message as a SUMMARY so it replaces old context
      assistantMsg.summary = true
      assistantMsg.time.completed = Date.now()
      assistantMsg.finish = "stop"
      assistantMsg.tokens = {
        input: result.stats.inputTokens,
        output: result.stats.outputTokens,
        reasoning: 0,
        cache: { read: 0, write: 0 },
      }

      // Build enhanced summary text
      const summaryText = buildSummaryText(result.processed, contextInfo, result.stats)

      await Session.updatePart({
        id: Identifier.ascending("part"),
        messageID: assistantMsg.id,
        sessionID: input.sessionID,
        type: "text",
        text: summaryText,
        time: { start: Date.now(), end: Date.now() },
      })

      await Session.updateMessage(assistantMsg)

      // Add compaction part to parent user message
      const parentUserMsg = input.messages.find((m) => m.info.id === assistantMsg.parentID)
      if (parentUserMsg) {
        await Session.updatePart({
          id: Identifier.ascending("part"),
          messageID: parentUserMsg.info.id,
          sessionID: input.sessionID,
          type: "compaction",
          auto: true,
        })
      }

      // Create synthetic user message to trigger parent model
      const continueMsg = await Session.updateMessage({
        id: Identifier.ascending("message"),
        role: "user",
        sessionID: input.sessionID,
        time: { created: Date.now() },
        model: {
          providerID: input.model.providerID,
          modelID: input.model.id,
        },
        agent: "code",
      })

      // Build continuation prompt with context
      const continuationPrompt = buildContinuationPrompt(query, contextInfo.metadata)
      await Session.updatePart({
        id: Identifier.ascending("part"),
        messageID: continueMsg.id,
        sessionID: input.sessionID,
        type: "text",
        text: continuationPrompt,
        time: { start: Date.now(), end: Date.now() },
      })

      const compressionRatio = result.stats.inputTokens / Math.max(1, result.stats.outputTokens)
      Bus.publish(Event.Completed, {
        sessionID: input.sessionID,
        inputTokens: result.stats.inputTokens,
        outputTokens: result.stats.outputTokens,
        compressionRatio,
      })

      log.info("RLM summary completed", {
        sessionID: input.sessionID,
        rlmAssistantId: assistantMsg.id,
        syntheticUserId: continueMsg.id,
        compressionRatio: compressionRatio.toFixed(1),
        ...result.stats,
      })
    } catch (e: any) {
      log.error("RLM processing failed", { error: e, sessionID: input.sessionID })

      Bus.publish(Event.Failed, {
        sessionID: input.sessionID,
        error: e?.message || "Unknown error",
      })

      // Update tool part with error
      const errorStartTime = "time" in toolPart.state ? toolPart.state.time.start : Date.now()
      await Session.updatePart({
        ...toolPart,
        state: {
          status: "error",
          input: toolPart.state.input,
          error: e?.message || "RLM processing failed",
          time: {
            start: errorStartTime,
            end: Date.now(),
          },
        },
      })

      await Session.updatePart({
        id: Identifier.ascending("part"),
        messageID: assistantMsg.id,
        sessionID: input.sessionID,
        type: "text",
        text: `⚠️ Context compression failed: ${e?.message || "Unknown error"}

Try:
- Using /compact to manually compress context
- Starting a new session with /new
- Breaking your task into smaller pieces`,
        time: { start: Date.now(), end: Date.now() },
      })

      assistantMsg.time.completed = Date.now()
      assistantMsg.finish = "error"
      await Session.updateMessage(assistantMsg)
    }
  }

  interface ContextMetadata {
    filesModified: string[]
    filesRead: string[]
    pendingTasks: string[]
    errors: string[]
    keyDecisions: string[]
  }

  interface ContextAnalysis {
    context: string
    metadata: ContextMetadata
    stats: {
      messageCount: number
      toolCalls: number
      userMessages: number
      assistantMessages: number
    }
  }

  /**
   * Analyze conversation and extract structured metadata alongside plain text.
   */
  function analyzeContext(messages: MessageV2.WithParts[]): ContextAnalysis {
    const parts: string[] = []
    const metadata: ContextMetadata = {
      filesModified: [],
      filesRead: [],
      pendingTasks: [],
      errors: [],
      keyDecisions: [],
    }
    let toolCalls = 0
    let userMessages = 0
    let assistantMessages = 0

    for (const msg of messages) {
      const role = msg.info.role === "user" ? "User" : "Assistant"
      if (msg.info.role === "user") userMessages++
      else assistantMessages++

      for (const part of msg.parts) {
        if (part.type === "text" && "text" in part) {
          const sanitized = sanitizeForContext(part.text)
          parts.push(`[${role}]: ${sanitized}`)

          // Extract pending tasks from todo-like patterns
          extractTasks(part.text, metadata.pendingTasks)
        } else if (part.type === "tool") {
          toolCalls++
          const toolName = part.tool
          const status = part.state.status

          // Track file operations
          if (toolName === "edit" || toolName === "write") {
            const path = part.state.input?.filePath || part.state.input?.path
            if (path && !metadata.filesModified.includes(path)) {
              metadata.filesModified.push(path)
            }
          } else if (toolName === "read") {
            const path = part.state.input?.filePath || part.state.input?.path
            if (path && !metadata.filesRead.includes(path)) {
              metadata.filesRead.push(path)
            }
          }

          if (status === "completed") {
            const output = part.state.output || "[no output]"
            // More aggressive truncation for tool outputs in context
            const maxLen = toolName === "read" ? 300 : 500
            const truncated = output.length > maxLen ? output.slice(0, maxLen) + "..." : output
            parts.push(`[Tool ${toolName}]: ${sanitizeForContext(truncated)}`)
          } else if (status === "error") {
            const error = part.state.error || "[unknown error]"
            metadata.errors.push(`${toolName}: ${error.slice(0, 100)}`)
            parts.push(`[Tool ${toolName} FAILED]: ${sanitizeForContext(error)}`)
          } else if (status === "running" || status === "pending") {
            parts.push(`[Tool ${toolName} ${status.toUpperCase()}]`)
          }
        }
      }
    }

    // Dedupe and limit lists
    metadata.filesModified = [...new Set(metadata.filesModified)].slice(-10)
    metadata.filesRead = [...new Set(metadata.filesRead)].slice(-15)
    metadata.pendingTasks = [...new Set(metadata.pendingTasks)].slice(-5)
    metadata.errors = [...new Set(metadata.errors)].slice(-5)

    return {
      context: parts.join("\n\n"),
      metadata,
      stats: {
        messageCount: messages.length,
        toolCalls,
        userMessages,
        assistantMessages,
      },
    }
  }

  /**
   * Extract task-like patterns from text.
   */
  function extractTasks(text: string, tasks: string[]) {
    // Look for common task patterns
    const patterns = [
      /TODO:\s*(.+?)(?:\n|$)/gi,
      /NEXT:\s*(.+?)(?:\n|$)/gi,
      /\[ \]\s*(.+?)(?:\n|$)/g, // Unchecked markdown checkboxes
      /(?:need to|should|must|will)\s+(.+?)(?:\.|$)/gi,
    ]

    for (const pattern of patterns) {
      const matches = text.matchAll(pattern)
      for (const match of matches) {
        const task = match[1].trim()
        if (task.length > 10 && task.length < 200) {
          tasks.push(task)
        }
      }
    }
  }

  /**
   * Build enhanced summary text with metadata.
   */
  function buildSummaryText(
    processed: string,
    contextInfo: ContextAnalysis,
    stats: { inputTokens: number; outputTokens: number; iterations?: number; subcalls?: number },
  ): string {
    const compressionRatio = (stats.inputTokens / Math.max(1, stats.outputTokens)).toFixed(1)
    const rlmDetails = stats.iterations ? ` | ${stats.iterations} iterations` : ""
    const subcallDetails = stats.subcalls ? ` | ${stats.subcalls} sub-calls` : ""

    const lines = [
      `## Context Summary`,
      `*Compressed ${stats.inputTokens.toLocaleString()} → ${stats.outputTokens.toLocaleString()} tokens (${compressionRatio}x${rlmDetails}${subcallDetails})*`,
      "",
    ]

    // Add file tracking
    if (contextInfo.metadata.filesModified.length > 0) {
      lines.push(`**Files Modified:** ${contextInfo.metadata.filesModified.slice(-5).join(", ")}`)
    }

    // Add errors if any
    if (contextInfo.metadata.errors.length > 0) {
      lines.push(`**Recent Errors:** ${contextInfo.metadata.errors.slice(-2).join("; ")}`)
    }

    // Add pending tasks
    if (contextInfo.metadata.pendingTasks.length > 0) {
      lines.push(`**Pending:** ${contextInfo.metadata.pendingTasks.slice(-3).join("; ")}`)
    }

    lines.push("", "---", "", processed)

    return lines.join("\n")
  }

  /**
   * Build continuation prompt for parent model.
   */
  function buildContinuationPrompt(query: string, metadata: ContextMetadata): string {
    const queryPreview = query.length > 300 ? query.slice(0, 300) + "..." : query

    const lines = [
      "<system-reminder>",
      "Context was compressed. The summary above contains key conversation history.",
      "",
    ]

    if (metadata.filesModified.length > 0) {
      lines.push(`Files you modified: ${metadata.filesModified.slice(-5).join(", ")}`)
    }

    if (metadata.pendingTasks.length > 0) {
      lines.push(`Pending tasks: ${metadata.pendingTasks.slice(-3).join("; ")}`)
    }

    lines.push("", `Continue with: ${queryPreview}`, "</system-reminder>")

    return lines.join("\n")
  }

  /**
   * Sanitize text to prevent API parsing issues.
   */
  function sanitizeForContext(text: string): string {
    return text
      .replace(/"type"\s*:\s*"tool_use"/g, '"type": "tool-use-ref"')
      .replace(/"type"\s*:\s*"tool_result"/g, '"type": "tool-result-ref"')
      .replace(/'type'\s*:\s*'tool_use'/g, "'type': 'tool-use-ref'")
      .replace(/'type'\s*:\s*'tool_result'/g, "'type': 'tool-result-ref'")
  }
}
