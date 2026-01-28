import { Bus } from "../bus"
import { BusEvent } from "../bus/bus-event"
import z from "zod"
import { Log } from "../util/log"

const log = Log.create({ service: "rlm-trace" })

/**
 * RLM execution trace for debugging and visualization.
 * Records all events during RLM processing for later analysis.
 */
export namespace RlmTrace {
  export const Event = {
    TraceStart: BusEvent.define(
      "rlm.trace.start",
      z.object({
        traceId: z.string(),
        sessionID: z.string(),
        toolId: z.string(),
        inputTokens: z.number(),
        contentType: z.string(),
        timestamp: z.number(),
      }),
    ),
    TraceStep: BusEvent.define(
      "rlm.trace.step",
      z.object({
        traceId: z.string(),
        stepType: z.enum(["exploration", "iteration", "code_exec", "subcall", "final"]),
        iteration: z.number().optional(),
        data: z.record(z.string(), z.any()),
        timestamp: z.number(),
      }),
    ),
    TraceEnd: BusEvent.define(
      "rlm.trace.end",
      z.object({
        traceId: z.string(),
        success: z.boolean(),
        outputTokens: z.number(),
        totalIterations: z.number(),
        totalSubcalls: z.number(),
        elapsed: z.number(),
        timestamp: z.number(),
      }),
    ),
  }

  export interface TraceStep {
    type: "exploration" | "iteration" | "code_exec" | "subcall" | "final" | "error"
    iteration?: number
    timestamp: number
    elapsed: number
    data: Record<string, any>
  }

  export interface Trace {
    id: string
    sessionID: string
    toolId: string
    inputTokens: number
    contentType: string
    startTime: number
    endTime?: number
    steps: TraceStep[]
    finalAnswer?: string
    error?: string
  }

  // In-memory trace storage (limited size)
  const traces = new Map<string, Trace>()
  const MAX_TRACES = 20

  /**
   * Start a new trace.
   */
  export function start(input: {
    traceId: string
    sessionID: string
    toolId: string
    inputTokens: number
    contentType: string
  }): Trace {
    const trace: Trace = {
      id: input.traceId,
      sessionID: input.sessionID,
      toolId: input.toolId,
      inputTokens: input.inputTokens,
      contentType: input.contentType,
      startTime: Date.now(),
      steps: [],
    }

    // Evict old traces if at capacity
    if (traces.size >= MAX_TRACES) {
      const oldest = Array.from(traces.entries()).sort((a, b) => a[1].startTime - b[1].startTime)[0]
      if (oldest) traces.delete(oldest[0])
    }

    traces.set(trace.id, trace)

    Bus.publish(Event.TraceStart, {
      traceId: trace.id,
      sessionID: trace.sessionID,
      toolId: trace.toolId,
      inputTokens: trace.inputTokens,
      contentType: trace.contentType,
      timestamp: trace.startTime,
    })

    log.info("RLM trace started", { traceId: trace.id, toolId: trace.toolId })
    return trace
  }

  /**
   * Add a step to a trace.
   */
  export function step(traceId: string, type: TraceStep["type"], data: Record<string, any>, iteration?: number): void {
    const trace = traces.get(traceId)
    if (!trace) return

    const now = Date.now()
    const step: TraceStep = {
      type,
      iteration,
      timestamp: now,
      elapsed: now - trace.startTime,
      data,
    }

    trace.steps.push(step)

    Bus.publish(Event.TraceStep, {
      traceId,
      stepType: type === "error" ? "final" : type,
      iteration,
      data,
      timestamp: now,
    })
  }

  /**
   * End a trace.
   */
  export function end(
    traceId: string,
    result: {
      success: boolean
      outputTokens: number
      totalIterations: number
      totalSubcalls: number
      finalAnswer?: string
      error?: string
    },
  ): void {
    const trace = traces.get(traceId)
    if (!trace) return

    trace.endTime = Date.now()
    trace.finalAnswer = result.finalAnswer
    trace.error = result.error

    const elapsed = trace.endTime - trace.startTime

    Bus.publish(Event.TraceEnd, {
      traceId,
      success: result.success,
      outputTokens: result.outputTokens,
      totalIterations: result.totalIterations,
      totalSubcalls: result.totalSubcalls,
      elapsed,
      timestamp: trace.endTime,
    })

    log.info("RLM trace ended", {
      traceId,
      success: result.success,
      elapsed,
      iterations: result.totalIterations,
      subcalls: result.totalSubcalls,
    })
  }

  /**
   * Get a trace by ID.
   */
  export function get(traceId: string): Trace | undefined {
    return traces.get(traceId)
  }

  /**
   * Get recent traces for a session.
   */
  export function forSession(sessionID: string, limit = 5): Trace[] {
    return Array.from(traces.values())
      .filter((t) => t.sessionID === sessionID)
      .sort((a, b) => b.startTime - a.startTime)
      .slice(0, limit)
  }

  /**
   * Format a trace for display.
   */
  export function format(trace: Trace): string {
    const lines: string[] = []
    const elapsed = (trace.endTime ?? Date.now()) - trace.startTime

    lines.push(`## RLM Trace: ${trace.id}`)
    lines.push(`- Tool: ${trace.toolId}`)
    lines.push(`- Content: ${trace.contentType} (${trace.inputTokens.toLocaleString()} tokens)`)
    lines.push(`- Duration: ${elapsed}ms`)
    lines.push(`- Steps: ${trace.steps.length}`)
    lines.push("")

    for (const step of trace.steps) {
      const stepTime = `+${step.elapsed}ms`
      switch (step.type) {
        case "exploration":
          lines.push(`[${stepTime}] 🔍 Exploration: ${step.data.linesFound ?? "?"} lines found`)
          break
        case "iteration":
          lines.push(`[${stepTime}] 🔄 Iteration ${step.iteration}: ${step.data.codeBlocks ?? 0} code blocks`)
          break
        case "code_exec":
          const status = step.data.error ? "❌" : "✓"
          lines.push(`[${stepTime}]   ${status} Code: ${step.data.codePreview ?? "..."}`)
          if (step.data.error) lines.push(`       Error: ${step.data.error}`)
          break
        case "subcall":
          lines.push(
            `[${stepTime}]   📤 Sub-LM #${step.data.subcallNumber}: ${step.data.promptTokens} → ${step.data.responseTokens} tokens`,
          )
          break
        case "final":
          lines.push(`[${stepTime}] ✅ Final: ${step.data.answerTokens ?? "?"} tokens`)
          break
        case "error":
          lines.push(`[${stepTime}] ❌ Error: ${step.data.error}`)
          break
      }
    }

    if (trace.error) {
      lines.push("")
      lines.push(`**Error:** ${trace.error}`)
    }

    return lines.join("\n")
  }

  /**
   * Clear all traces.
   */
  export function clear(): void {
    traces.clear()
  }
}
