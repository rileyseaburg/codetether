import { Config } from "../config/config"
import { Token } from "../util/token"
import { Log } from "../util/log"
import { Bus } from "../bus"
import { BusEvent } from "../bus/bus-event"
import { RlmRepl } from "./rlm-repl"
import { RlmReplBun } from "./rlm-repl-bun"
import { RlmReplRust } from "./rlm-repl-rust"
import { RlmChunker } from "./rlm-chunker"
import { RlmTrace } from "./rlm-trace"
import { Provider } from "../provider/provider"
import { generateText } from "ai"
import z from "zod"
import { ulid } from "ulid"

type RlmRuntime = "python" | "rust" | "bun"

const log = Log.create({ service: "rlm-router" })

// Default threshold: 35% of model context window
const DEFAULT_THRESHOLD = 0.35

// Tools that can produce large context and should be RLM-routed
const RLM_ELIGIBLE_TOOLS = new Set(["read", "glob", "grep", "bash"])

export namespace RlmRouter {
  export const Event = {
    Decision: BusEvent.define(
      "rlm.routing.decision",
      z.object({
        tool: z.string(),
        sessionID: z.string(),
        callID: z.string().optional(),
        decision: z.enum(["routed", "passthrough"]),
        reason: z.string(),
        estimatedTokens: z.number(),
        contextLimit: z.number(),
        threshold: z.number(),
        mode: z.enum(["auto", "off", "always"]),
      }),
    ),
    Subcall: BusEvent.define(
      "rlm.subcall",
      z.object({
        sessionID: z.string(),
        subcallNumber: z.number(),
        promptTokens: z.number(),
        responseTokens: z.number(),
      }),
    ),
    Iteration: BusEvent.define(
      "rlm.iteration",
      z.object({
        sessionID: z.string(),
        iteration: z.number(),
        maxIterations: z.number(),
        codeBlocksFound: z.number(),
        hasFinal: z.boolean(),
      }),
    ),
    Complete: BusEvent.define(
      "rlm.complete",
      z.object({
        sessionID: z.string(),
        inputTokens: z.number(),
        outputTokens: z.number(),
        iterations: z.number(),
        subcalls: z.number(),
        elapsed: z.number(),
        compressionRatio: z.number(),
      }),
    ),
  }

  export interface RoutingContext {
    toolId: string
    sessionID: string
    callID?: string
    modelContextLimit: number
    currentContextTokens?: number
  }

  export interface RoutingResult {
    shouldRoute: boolean
    reason: string
    estimatedTokens: number
  }

  /**
   * Check if a tool output should be routed through RLM.
   */
  export async function shouldRoute(output: string, ctx: RoutingContext): Promise<RoutingResult> {
    const config = await Config.get()
    const mode = config.rlm?.mode ?? "auto"
    const threshold = config.rlm?.threshold ?? DEFAULT_THRESHOLD

    const estimatedTokens = Token.estimate(output)

    // Mode: off - never route
    if (mode === "off") {
      return {
        shouldRoute: false,
        reason: "rlm_mode_off",
        estimatedTokens,
      }
    }

    // Mode: always - always route for eligible tools
    if (mode === "always") {
      if (!RLM_ELIGIBLE_TOOLS.has(ctx.toolId)) {
        return {
          shouldRoute: false,
          reason: "tool_not_eligible",
          estimatedTokens,
        }
      }
      return {
        shouldRoute: true,
        reason: "rlm_mode_always",
        estimatedTokens,
      }
    }

    // Mode: auto - route based on threshold
    if (!RLM_ELIGIBLE_TOOLS.has(ctx.toolId)) {
      return {
        shouldRoute: false,
        reason: "tool_not_eligible",
        estimatedTokens,
      }
    }

    // Check if output exceeds threshold relative to context window
    const thresholdTokens = Math.floor(ctx.modelContextLimit * threshold)
    if (estimatedTokens > thresholdTokens) {
      return {
        shouldRoute: true,
        reason: "exceeds_threshold",
        estimatedTokens,
      }
    }

    // Check if adding this output would cause overflow
    if (ctx.currentContextTokens !== undefined) {
      const projectedTotal = ctx.currentContextTokens + estimatedTokens
      if (projectedTotal > ctx.modelContextLimit * 0.8) {
        return {
          shouldRoute: true,
          reason: "would_overflow",
          estimatedTokens,
        }
      }
    }

    return {
      shouldRoute: false,
      reason: "within_threshold",
      estimatedTokens,
    }
  }

  /**
   * Emit a routing decision event for the pane-of-glass.
   */
  export async function emitDecision(ctx: RoutingContext, result: RoutingResult): Promise<void> {
    const config = await Config.get()
    const mode = config.rlm?.mode ?? "auto"
    const threshold = config.rlm?.threshold ?? DEFAULT_THRESHOLD

    Bus.publish(Event.Decision, {
      tool: ctx.toolId,
      sessionID: ctx.sessionID,
      callID: ctx.callID,
      decision: result.shouldRoute ? "routed" : "passthrough",
      reason: result.reason,
      estimatedTokens: result.estimatedTokens,
      contextLimit: ctx.modelContextLimit,
      threshold,
      mode,
    })

    log.info("RLM routing decision", {
      tool: ctx.toolId,
      decision: result.shouldRoute ? "routed" : "passthrough",
      reason: result.reason,
      tokens: result.estimatedTokens,
      limit: ctx.modelContextLimit,
    })
  }

  /**
   * Smart truncate large output with RLM hint.
   * Keeps head + tail and tells the agent to use RLM for full analysis.
   */
  export function smartTruncate(
    output: string,
    toolId: string,
    toolArgs: Record<string, any>,
    maxTokens: number = 8000,
  ): { content: string; wasTruncated: boolean; originalTokens: number } {
    const estimatedTokens = Token.estimate(output)

    if (estimatedTokens <= maxTokens) {
      return { content: output, wasTruncated: false, originalTokens: estimatedTokens }
    }

    log.info("Smart truncating large output", {
      tool: toolId,
      originalTokens: estimatedTokens,
      maxTokens,
    })

    // Calculate how much to keep (in characters, roughly 4 chars per token)
    const maxChars = maxTokens * 4
    const headChars = Math.floor(maxChars * 0.6) // 60% from head
    const tailChars = Math.floor(maxChars * 0.3) // 30% from tail

    const head = output.slice(0, headChars)
    const tail = output.slice(-tailChars)

    // Build the RLM hint based on tool
    const rlmHint = buildRlmHint(toolId, toolArgs, estimatedTokens)

    const truncated = [
      head,
      "",
      `[... ${(estimatedTokens - Token.estimate(head) - Token.estimate(tail)).toLocaleString()} tokens truncated ...]`,
      "",
      rlmHint,
      "",
      tail,
    ].join("\n")

    return {
      content: truncated,
      wasTruncated: true,
      originalTokens: estimatedTokens,
    }
  }

  function buildRlmHint(toolId: string, args: Record<string, any>, tokens: number): string {
    const base = `⚠️ OUTPUT TOO LARGE (${tokens.toLocaleString()} tokens). Use RLM for full analysis:`

    switch (toolId) {
      case "read":
        return `${base}\n\`\`\`\nrlm({ query: "Analyze this file", context_paths: ["${args.filePath || "..."}"] })\n\`\`\``
      case "bash":
        return `${base}\n\`\`\`\nrlm({ query: "Analyze this command output", context: "<paste output or use context_paths>" })\n\`\`\``
      case "grep":
        return `${base}\n\`\`\`\nrlm({ query: "Summarize search results for ${args.pattern || "..."}", context_glob: "${args.include || "*"}" })\n\`\`\``
      default:
        return `${base}\n\`\`\`\nrlm({ query: "Summarize this output", context: "..." })\n\`\`\``
    }
  }

  // Parse provider:model format
  function parseModelRef(ref: string): { provider: string; model: string } {
    const [provider, ...rest] = ref.split(":")
    return { provider, model: rest.join(":") }
  }

  export interface AutoProcessContext {
    toolId: string
    toolArgs: Record<string, any>
    sessionID: string
    abort: AbortSignal
    onProgress?: (data: { iteration: number; maxIterations: number; status: string }) => void
  }

  /**
   * Determine which runtime to use (with fallback logic).
   */
  async function getRuntime(): Promise<RlmRuntime> {
    const config = await Config.get()
    const preferred = config.rlm?.runtime ?? "bun" // Default to bun (fastest)

    if (preferred === "rust") {
      const available = await RlmReplRust.isAvailable()
      if (!available) {
        log.warn("Rust runtime requested but evcxr not available, falling back to bun")
        return "bun"
      }
      return "rust"
    }

    if (preferred === "bun") {
      return "bun"
    }

    return "python"
  }

  type AnyRepl = RlmRepl.Repl | RlmReplBun.Repl | RlmReplRust.Repl

  /**
   * Create a REPL with the specified runtime.
   */
  async function createRepl(runtime: RlmRuntime, context: string): Promise<AnyRepl> {
    switch (runtime) {
      case "rust":
        return RlmReplRust.create(context)
      case "bun":
        return RlmReplBun.create(context)
      case "python":
      default:
        return RlmRepl.create(context, { disableNetwork: true })
    }
  }

  /**
   * Execute code on a REPL.
   */
  async function executeOnRepl(
    repl: AnyRepl,
    runtime: RlmRuntime,
    code: string,
    onLlmQuery: (prompt: string) => Promise<string>,
  ): Promise<{ stdout: string; stderr: string; final?: string }> {
    switch (runtime) {
      case "rust":
        return RlmReplRust.execute(repl as RlmReplRust.Repl, code, onLlmQuery)
      case "bun":
        return RlmReplBun.execute(repl as RlmReplBun.Repl, code, onLlmQuery)
      case "python":
      default:
        const result = await RlmRepl.execute(repl as RlmRepl.Repl, code, onLlmQuery)
        return { ...result, final: undefined }
    }
  }

  /**
   * Build the prompt for the LLM based on runtime.
   */
  function buildPrompt(
    runtime: RlmRuntime,
    inputTokens: number,
    toolId: string,
    query: string,
    isFirst: boolean,
  ): string {
    if (!isFirst) {
      return `Continue analysis. Call FINAL("your answer") when ready.`
    }

    // For session_context, the query already contains full instructions
    // Don't wrap it in additional boilerplate
    if (toolId === "session_context") {
      return query
    }

    if (runtime === "rust") {
      return `You are analyzing large output (${inputTokens.toLocaleString()} tokens) from the "${toolId}" tool.

Task: ${query}

The output is loaded as \`context: &str\` variable. Write Rust code to analyze it.
Use println!() for progress. Call FINAL!(format!("your answer")) when done.

Available: regex crate, serde_json crate, standard library.
Common patterns:
- context.lines() for line iteration
- context.contains("pattern") for simple search
- regex::Regex::new(r"pattern")?.find_iter(context) for regex

Keep your answer concise (under 2000 tokens).`
    }

    if (runtime === "bun") {
      return `JavaScript REPL ready. Variable \`context\` contains ${inputTokens.toLocaleString()} tokens of data.

YOUR TASK: ${query}

Built-in helpers:
- lines() - returns array of lines
- head(n) - first n lines
- tail(n) - last n lines  
- grep(pattern) - filter lines matching pattern
- count(pattern) - count matches

Write JavaScript code to analyze and call FINAL("your findings") when done.

\`\`\`javascript
// Explore
console.log(\`Total: \${context.length} chars, \${lines().length} lines\`);
console.log("=== LAST 2000 CHARS ===");
console.log(context.slice(-2000));

// Your analysis here, then:
FINAL("your detailed findings")
\`\`\``
    }

    return `Python REPL ready. Variable \`context\` contains ${inputTokens.toLocaleString()} tokens of conversation/data.

YOUR TASK: ${query}

Write Python code to:
1. Explore context (print first 2000 chars, count lines, search for keywords)
2. Find information relevant to the task
3. Call FINAL("your detailed findings") with ACTUAL results from your analysis

\`\`\`python
# Explore the data
print(f"Length: {len(context)} chars, {context.count(chr(10))} lines")
print("=== FIRST 2000 CHARS ===")
print(context[:2000])
print("=== END PREVIEW ===")

# TODO: Add your analysis here based on what you see
# Then call FINAL() with your real findings
\`\`\``
  }

  /**
   * Automatically process large output through RLM.
   * This is called when routing decides output is too large.
   *
   * Based on "Recursive Language Models" (Zhang et al. 2025):
   * - Context is loaded as a variable in a REPL environment
   * - LLM writes code to analyze, decompose, and recursively sub-call itself
   * - Sub-LM calls handle semantic analysis the root model offloads
   */
  export async function autoProcess(
    output: string,
    ctx: AutoProcessContext,
  ): Promise<{
    processed: string
    stats: { inputTokens: number; outputTokens: number; iterations: number; subcalls: number }
  }> {
    const config = await Config.get()
    const rootModelRef = config.rlm?.root_model || config.rlm?.subcall_model || "zai-coding-plan:glm-4.7"
    const subcallModelRef = config.rlm?.subcall_model || "zai-coding-plan:glm-4.7"
    const inputTokens = Token.estimate(output)
    const runtime = await getRuntime()

    log.info("RLM: Starting auto-processing", {
      tool: ctx.toolId,
      inputTokens,
      rootModel: rootModelRef,
      subcallModel: subcallModelRef,
      runtime,
    })

    // Get both root and subcall models
    let rootModel: Awaited<ReturnType<typeof Provider.getLanguage>>
    let subcallModel: Awaited<ReturnType<typeof Provider.getLanguage>>
    try {
      const rootParsed = parseModelRef(rootModelRef)
      const rootFull = await Provider.getModel(rootParsed.provider, rootParsed.model)
      rootModel = await Provider.getLanguage(rootFull)

      const subcallParsed = parseModelRef(subcallModelRef)
      const subcallFull = await Provider.getModel(subcallParsed.provider, subcallParsed.model)
      subcallModel = await Provider.getLanguage(subcallFull)
    } catch (e) {
      log.error("RLM: Failed to load models, falling back to truncation", {
        rootModel: rootModelRef,
        subcallModel: subcallModelRef,
        error: e,
      })
      const truncated = smartTruncate(output, ctx.toolId, ctx.toolArgs)
      return {
        processed: truncated.content,
        stats: { inputTokens, outputTokens: Token.estimate(truncated.content), iterations: 0, subcalls: 0 },
      }
    }

    // Detect content type for smarter processing
    const contentType = RlmChunker.detectContentType(output)
    const contentHints = RlmChunker.getProcessingHints(contentType)
    log.info("RLM: Content type detected", { contentType, toolId: ctx.toolId })

    // Build query based on tool type, including content type hints
    const baseQuery = buildQueryForTool(ctx.toolId, ctx.toolArgs, runtime)
    const query = `${baseQuery}\n\n## Content Analysis Hints\n${contentHints}`

    // For very large contexts, use semantic chunking to preserve important parts
    const processedOutput = inputTokens > 50000 ? RlmChunker.compress(output, 40000, { preserveRecent: 200 }) : output

    // Create REPL with context based on runtime
    const repl = await createRepl(runtime, processedOutput)

    const codeBlockPattern =
      runtime === "rust" ? /```(?:rust)?\n([\s\S]*?)```/g : /```(?:python|javascript|js|repl)?\n([\s\S]*?)```/g

    const MAX_ITERATIONS = config.rlm?.max_iterations ?? 15
    const MAX_SUBCALLS = config.rlm?.max_subcalls ?? 50 // Per paper: batch info to reduce calls
    let iterations = 0
    let subcalls = 0
    let finalAnswer: string | null = null
    let conversationHistory: Array<{ role: "user" | "assistant"; content: string }> = []

    const startTime = Date.now()
    const traceId = ulid()

    // Start execution trace
    RlmTrace.start({
      traceId,
      sessionID: ctx.sessionID,
      toolId: ctx.toolId,
      inputTokens,
      contentType,
    })

    // Track subcall handler for recursive LLM queries
    const handleSubcall = async (prompt: string): Promise<string> => {
      if (subcalls >= MAX_SUBCALLS) {
        log.warn("RLM: Max subcalls reached", { subcalls, max: MAX_SUBCALLS })
        return "[Max subcalls reached - batch more context into each call]"
      }
      subcalls++
      const promptTokens = Token.estimate(prompt)
      log.info("RLM: Sub-LM call", {
        subcall: subcalls,
        promptTokens,
        promptPreview: prompt.slice(0, 100),
      })

      try {
        const response = await generateText({
          model: subcallModel,
          prompt,
          maxOutputTokens: 4000,
          abortSignal: ctx.abort,
        })
        const responseTokens = Token.estimate(response.text)
        log.info("RLM: Sub-LM response", { subcall: subcalls, responseTokens })

        // Emit subcall event for UI tracking
        Bus.publish(Event.Subcall, {
          sessionID: ctx.sessionID,
          subcallNumber: subcalls,
          promptTokens,
          responseTokens,
        })

        // Add to trace
        RlmTrace.step(traceId, "subcall", {
          subcallNumber: subcalls,
          promptTokens,
          responseTokens,
          promptPreview: prompt.slice(0, 100),
        })

        return response.text
      } catch (e: any) {
        log.error("RLM: Sub-LM call failed", { error: e?.message, subcall: subcalls })
        return `[Sub-LM error: ${e?.message || "unknown"}]`
      }
    }

    try {
      // Initial exploration to show the model what's in context
      const explorationCode = buildExplorationCode(runtime, inputTokens)
      log.info("RLM: Running initial exploration", { runtime })
      const explorationResult = await executeOnRepl(repl, runtime, explorationCode, handleSubcall)
      log.info("RLM: Exploration complete", { stdoutLength: explorationResult.stdout.length })

      // Trace exploration
      RlmTrace.step(traceId, "exploration", {
        runtime,
        linesFound: explorationResult.stdout.split("\n").length,
        outputLength: explorationResult.stdout.length,
      })

      // Build the system prompt based on the paper's Appendix D
      const systemPrompt = buildRlmSystemPrompt(runtime, inputTokens, ctx.toolId, query)

      for (let i = 0; i < MAX_ITERATIONS && !finalAnswer; i++) {
        iterations = i + 1
        ctx.onProgress?.({ iteration: iterations, maxIterations: MAX_ITERATIONS, status: "running" })

        // Build the prompt for this iteration
        const iterationPrompt =
          i === 0
            ? `${systemPrompt}

Here is the initial exploration of the context variable:
\`\`\`
${explorationResult.stdout.slice(0, 4000)}
\`\`\`

Now write code to analyze the context and answer the query. Use llm_query() for semantic analysis.`
            : `Continue. The code executed. Write more code or call FINAL() with your answer.

Previous output:
\`\`\`
${conversationHistory[conversationHistory.length - 1]?.content.slice(0, 2000) || ""}
\`\`\``

        conversationHistory.push({ role: "user", content: iterationPrompt })

        // Call the root model
        let response: Awaited<ReturnType<typeof generateText>>
        let retries = 0
        const maxRetries = 2

        while (true) {
          try {
            response = await generateText({
              model: rootModel,
              messages: conversationHistory.map((m) => ({ role: m.role, content: m.content })),
              maxOutputTokens: 4000,
              abortSignal: ctx.abort,
            })
            break
          } catch (e: any) {
            retries++
            if (retries > maxRetries || ctx.abort.aborted) {
              log.error("RLM: Root model failed after retries", { error: e, retries })
              throw e
            }
            log.warn("RLM: Root model failed, retrying", { error: e?.message, retry: retries })
            await new Promise((r) => setTimeout(r, 1000 * retries))
          }
        }

        const text = response.text
        conversationHistory.push({ role: "assistant", content: text })
        log.info("RLM: Root model response", {
          iteration: iterations,
          textLength: text.length,
          preview: text.slice(0, 200),
        })

        // Extract and execute code blocks
        const codeBlocks = Array.from(text.matchAll(codeBlockPattern))
        log.info("RLM: Code blocks found", { count: codeBlocks.length })

        // Emit iteration event for UI tracking
        Bus.publish(Event.Iteration, {
          sessionID: ctx.sessionID,
          iteration: iterations,
          maxIterations: MAX_ITERATIONS,
          codeBlocksFound: codeBlocks.length,
          hasFinal: false, // Will be updated if we find FINAL
        })

        // Add iteration to trace
        RlmTrace.step(
          traceId,
          "iteration",
          {
            iteration: iterations,
            codeBlocks: codeBlocks.length,
            responseTokens: Token.estimate(text),
          },
          iterations,
        )

        let executionOutput = ""
        if (codeBlocks.length > 0) {
          for (const match of codeBlocks) {
            const code = match[1].trim()
            if (code) {
              log.info("RLM: Executing code", { runtime, codeLength: code.length, preview: code.slice(0, 100) })
              try {
                const result = await executeOnRepl(repl, runtime, code, handleSubcall)
                executionOutput += result.stdout + (result.stderr ? `\nSTDERR: ${result.stderr}` : "")

                log.info("RLM: Code execution result", {
                  stdoutLength: result.stdout.length,
                  stderrLength: result.stderr?.length || 0,
                  hasFinal: !!result.final,
                })

                // Add code execution to trace
                RlmTrace.step(
                  traceId,
                  "code_exec",
                  {
                    codePreview: code.slice(0, 50),
                    codeLength: code.length,
                    outputLength: result.stdout.length,
                    hasFinal: !!result.final,
                  },
                  iterations,
                )

                // Check if execution produced a FINAL answer
                if (result.final) {
                  finalAnswer = result.final
                  break
                }

                // Also check stdout for FINAL pattern (Python prints it)
                const stdoutFinal = result.stdout.match(/__FINAL__([\s\S]*?)__FINAL_END__/)
                if (stdoutFinal) {
                  finalAnswer = stdoutFinal[1]
                  break
                }
              } catch (e: any) {
                log.warn("RLM: Code execution error", { error: e?.message, runtime })
                executionOutput += `\nError: ${e?.message || "unknown"}`

                // Add error to trace
                RlmTrace.step(
                  traceId,
                  "error",
                  {
                    error: e?.message || "unknown",
                    codePreview: code.slice(0, 50),
                  },
                  iterations,
                )
              }
            }
          }

          // Add execution output to conversation for next iteration
          if (executionOutput && !finalAnswer) {
            conversationHistory.push({
              role: "user",
              content: `Code output:\n\`\`\`\n${executionOutput.slice(0, 3000)}\n\`\`\``,
            })
          }
        }

        // Check for raw FINAL in LLM response if no code was found
        if (!finalAnswer && codeBlocks.length === 0) {
          const finalMatch = text.match(/FINAL\s*[!(]\s*["'`]?([\s\S]*?)["'`]?\s*\)/s)
          if (finalMatch) {
            log.info("RLM: Raw FINAL found (no code)", { answerLength: finalMatch[1].length })
            finalAnswer = finalMatch[1]
            break
          }

          const finalVarMatch = text.match(/FINAL_VAR\s*[!(]\s*["'`]?(\w+)["'`]?\s*\)/)
          if (finalVarMatch) {
            const varName = finalVarMatch[1]
            const printCode =
              runtime === "rust"
                ? `println!("{:?}", ${varName});`
                : runtime === "bun"
                  ? `console.log(JSON.stringify(${varName}, null, 2))`
                  : `print(${varName})`
            const result = await executeOnRepl(repl, runtime, printCode, handleSubcall)
            finalAnswer = result.stdout.trim() || `[Variable ${varName} retrieved]`
            break
          }
        }
      }

      ctx.onProgress?.({ iteration: iterations, maxIterations: MAX_ITERATIONS, status: "completed" })

      // Fallback if no FINAL was called
      if (!finalAnswer) {
        log.warn("RLM: No FINAL produced, using fallback", { iterations, subcalls })
        finalAnswer =
          `[RLM processed ${ctx.toolId} output in ${iterations} iterations with ${subcalls} sub-calls but no final answer produced]\n\n` +
          smartTruncate(output, ctx.toolId, ctx.toolArgs, 4000).content
      }

      // Validate answer quality - check for suspiciously short or generic responses
      const answerTokens = Token.estimate(finalAnswer ?? "")
      const isShortAnswer = answerTokens < 100 && inputTokens > 5000
      const isTooAggressive = inputTokens / Math.max(1, answerTokens) > 100 // More than 100:1 compression is suspect

      // Check for common failure patterns
      const failurePatterns = [
        /I (?:do not|don't) have (?:the |any )?(?:previous )?context/i,
        /I (?:cannot|can't) (?:access|see|find) the (?:previous )?(?:context|conversation)/i,
        /(?:no|without) (?:additional )?context (?:provided|available)/i,
        /context.*(?:not |un)available/i,
        /unable to (?:access|retrieve|find)/i,
      ]
      const hasFailurePattern = failurePatterns.some((p) => p.test(finalAnswer ?? ""))

      // If answer quality is poor, use a smarter fallback that preserves key information
      if ((isShortAnswer || isTooAggressive || hasFailurePattern) && !ctx.abort.aborted) {
        log.warn("RLM: Poor quality answer detected, building enhanced fallback", {
          answerTokens,
          inputTokens,
          compressionRatio: (inputTokens / Math.max(1, answerTokens)).toFixed(1),
          isShortAnswer,
          isTooAggressive,
          hasFailurePattern,
        })

        // Build a more useful fallback using structural extraction
        finalAnswer = buildEnhancedFallback(output, ctx.toolId, ctx.toolArgs, inputTokens)
      }

      // Ensure we always have an answer at this point
      const answer = finalAnswer ?? buildEnhancedFallback(output, ctx.toolId, ctx.toolArgs, inputTokens)
      const outputTokens = Token.estimate(answer)
      const elapsed = Date.now() - startTime
      const compressionRatio = inputTokens / Math.max(1, outputTokens)
      const result = `[RLM: ${inputTokens.toLocaleString()} → ${outputTokens.toLocaleString()} tokens | ${iterations} iterations | ${subcalls} sub-calls]\n\n${answer}`

      log.info("RLM: Processing complete", {
        inputTokens,
        outputTokens,
        iterations,
        subcalls,
        elapsed,
        compressionRatio: compressionRatio.toFixed(1),
      })

      // Emit complete event for UI/cost tracking
      Bus.publish(Event.Complete, {
        sessionID: ctx.sessionID,
        inputTokens,
        outputTokens,
        iterations,
        subcalls,
        elapsed,
        compressionRatio,
      })

      // Record final step in trace
      RlmTrace.step(traceId, "final", {
        answerTokens: outputTokens,
        compressionRatio,
      })

      // End trace
      RlmTrace.end(traceId, {
        success: true,
        outputTokens,
        totalIterations: iterations,
        totalSubcalls: subcalls,
        finalAnswer: answer.slice(0, 500),
      })

      return {
        processed: result,
        stats: { inputTokens, outputTokens: Token.estimate(result), iterations, subcalls },
      }
    } catch (e: any) {
      log.error("RLM: Processing failed", { error: e, runtime, iterations, subcalls })
      ctx.onProgress?.({ iteration: iterations, maxIterations: MAX_ITERATIONS, status: "error" })

      // End trace with error
      RlmTrace.end(traceId, {
        success: false,
        outputTokens: 0,
        totalIterations: iterations,
        totalSubcalls: subcalls,
        error: e?.message || "Unknown error",
      })

      const truncated = smartTruncate(output, ctx.toolId, ctx.toolArgs)
      return {
        processed: `[RLM processing failed, showing truncated output]\n\n${truncated.content}`,
        stats: { inputTokens, outputTokens: Token.estimate(truncated.content), iterations, subcalls },
      }
    } finally {
      repl.proc.kill()
    }
  }

  /**
   * Build exploration code that shows head + tail of context.
   * Per the paper, we need to see the beginning (user's initial request)
   * and the end (most recent activity).
   */
  function buildExplorationCode(runtime: RlmRuntime, inputTokens: number): string {
    if (runtime === "bun") {
      return `
console.log("=== CONTEXT EXPLORATION ===");
console.log(\`Total: \${context.length} chars, \${lines().length} lines\`);
console.log();
console.log("=== FIRST 1500 CHARS (initial request/context) ===");
console.log(context.slice(0, 1500));
console.log();
console.log("=== LAST 1500 CHARS (most recent activity) ===");
console.log(context.slice(-1500));
console.log("=== END EXPLORATION ===");
`
    }

    return `
print("=== CONTEXT EXPLORATION ===")
print(f"Total: {len(context)} chars, {context.count(chr(10))+1} lines")
print()
print("=== FIRST 1500 CHARS (initial request/context) ===")
print(context[:1500])
print()
print("=== LAST 1500 CHARS (most recent activity) ===")
print(context[-1500:] if len(context) > 1500 else "")
print("=== END EXPLORATION ===")
`
  }

  /**
   * Build the RLM system prompt based on the paper's Appendix D.
   * This is the key prompt that teaches the model how to use the REPL.
   */
  function buildRlmSystemPrompt(runtime: RlmRuntime, inputTokens: number, toolId: string, query: string): string {
    const lang = runtime === "bun" ? "JavaScript" : runtime === "rust" ? "Rust" : "Python"
    const contextType = toolId === "session_context" ? "conversation history" : "tool output"

    const base = `You are tasked with answering a query with associated context. You can access, transform, and analyze this context interactively in a REPL environment that can recursively query sub-LLMs.

Your context is a ${contextType} with ${inputTokens.toLocaleString()} total tokens.

The REPL environment is initialized with:
1. A 'context' variable containing the full ${contextType}
2. A 'llm_query' function that allows you to query a sub-LLM (handles ~500K chars)
3. 'print()' / 'console.log()' to view outputs and continue reasoning
4. 'FINAL(answer)' to provide your final answer
5. 'FINAL_VAR(varName)' to return a variable as your answer

IMPORTANT: Be careful about using 'llm_query' as it incurs cost. Batch as much information as possible into each call (aim for ~100-200k chars per call). For example, if processing 1000 lines, split into chunks of 100-200 and call llm_query per chunk (5-10 calls) rather than 1000 individual calls.

YOUR TASK: ${query}

`

    if (runtime === "bun") {
      return (
        base +
        `
Write JavaScript code to analyze the context. Example strategies:

\`\`\`javascript
// Strategy 1: Chunk and query sub-LLM for semantic analysis
const chunkSize = Math.ceil(lines().length / 5);
const summaries = [];
for (let i = 0; i < 5; i++) {
  const chunk = lines().slice(i * chunkSize, (i + 1) * chunkSize).join("\\n");
  const summary = await llm_query(\`Summarize this section, focusing on key information:\\n\${chunk}\`);
  summaries.push(summary);
  console.log(\`Chunk \${i+1}/5 processed\`);
}
const finalAnswer = await llm_query(\`Based on these summaries, answer: ${query}\\n\\n\${summaries.join("\\n\\n")}\`);
FINAL(finalAnswer);
\`\`\`

\`\`\`javascript
// Strategy 2: Use code to filter, then query sub-LLM for analysis
const relevant = grep(/error|failed|important/i);
console.log(\`Found \${relevant.length} relevant lines\`);
const analysis = await llm_query(\`Analyze these findings:\\n\${relevant.join("\\n")}\`);
FINAL(analysis);
\`\`\`

Available helpers: lines(), head(n), tail(n), grep(pattern), count(pattern)
`
      )
    }

    return (
      base +
      `
Write Python code to analyze the context. Example strategies:

\`\`\`python
# Strategy 1: Chunk and query sub-LLM for semantic analysis
lines = context.split("\\n")
chunk_size = len(lines) // 5
summaries = []
for i in range(5):
    chunk = "\\n".join(lines[i*chunk_size:(i+1)*chunk_size])
    summary = llm_query(f"Summarize this section, focusing on key information:\\n{chunk}")
    summaries.append(summary)
    print(f"Chunk {i+1}/5 processed")

final_answer = llm_query(f"Based on these summaries, answer: ${query}\\n\\n" + "\\n\\n".join(summaries))
FINAL(final_answer)
\`\`\`

\`\`\`python
# Strategy 2: Use code to filter, then query sub-LLM for analysis
import re
relevant = [l for l in context.split("\\n") if re.search(r'error|failed|important', l, re.I)]
print(f"Found {len(relevant)} relevant lines")
analysis = llm_query(f"Analyze these findings:\\n" + "\\n".join(relevant))
FINAL(analysis)
\`\`\`
`
    )
  }

  /**
   * Build an enhanced fallback when RLM processing fails or produces poor results.
   * Uses structural extraction to preserve the most important information.
   */
  function buildEnhancedFallback(
    output: string,
    toolId: string,
    toolArgs: Record<string, any>,
    inputTokens: number,
  ): string {
    const lines = output.split("\n")
    const parts: string[] = []

    // For session context, extract key structural information
    if (toolId === "session_context") {
      // Extract file paths mentioned
      const fileMatches = output.match(/[\w/.-]+\.(ts|tsx|js|jsx|py|rs|go|json|md|css|html)/g) || []
      const files = [...new Set(fileMatches)].slice(-15)

      // Extract tool calls
      const toolCallMatches = output.match(/\[Tool (\w+)\]/g) || []
      const toolCalls = [...new Set(toolCallMatches)].slice(-10)

      // Extract errors
      const errorLines = lines.filter((l) => /error|failed|Error|FAILED/i.test(l)).slice(-5)

      // Get first 30 lines (user's request) and last 80 lines (recent activity)
      const headLines = lines.slice(0, 30).join("\n")
      const tailLines = lines.slice(-80).join("\n")

      parts.push("## Context Summary (Fallback Mode)")
      parts.push(`*Original: ${inputTokens.toLocaleString()} tokens - RLM processing produced insufficient output*`)
      parts.push("")

      if (files.length > 0) {
        parts.push(`**Files Modified:** ${files.join(", ")}`)
      }

      if (toolCalls.length > 0) {
        parts.push(`**Recent Tool Calls:** ${toolCalls.join(", ")}`)
      }

      if (errorLines.length > 0) {
        parts.push(`**Recent Errors:**`)
        errorLines.forEach((e) => parts.push(`- ${e.slice(0, 150)}`))
      }

      parts.push("")
      parts.push("### Initial Request")
      parts.push("```")
      parts.push(headLines)
      parts.push("```")
      parts.push("")
      parts.push("### Recent Activity")
      parts.push("```")
      parts.push(tailLines)
      parts.push("```")

      return parts.join("\n")
    }

    // For other tools, use smart truncation with better structure
    const truncated = smartTruncate(output, toolId, toolArgs, 8000)
    return `## Fallback Summary\n*RLM processing failed - showing structured excerpt*\n\n${truncated.content}`
  }

  function buildQueryForTool(toolId: string, args: Record<string, any>, runtime: RlmRuntime = "bun"): string {
    switch (toolId) {
      case "read":
        return `Summarize the key contents of file "${args.filePath || "unknown"}". Focus on: structure, main functions/classes, important logic. Be concise.`
      case "bash":
        return `Summarize the command output. Extract key information, results, errors, warnings. Be concise.`
      case "grep":
        return `Summarize search results for "${args.pattern || "pattern"}". Group by file, highlight most relevant matches. Be concise.`
      case "glob":
        return `Summarize the file listing. Group by directory, highlight important files. Be concise.`
      case "session_context":
        // For full conversation overflow - create a comprehensive briefing
        // Runtime-aware code examples per the paper
        const metadata = args.metadata || {}
        const filesModified = metadata.filesModified?.join(", ") || "none tracked"
        const pendingTasks = metadata.pendingTasks?.join("; ") || "none identified"

        const baseQuery = `You are a CONTEXT MEMORY SYSTEM. Create a BRIEFING for an AI assistant to continue this conversation seamlessly.

CRITICAL: The assistant will ONLY see your briefing - it has NO memory of the conversation. Your briefing must contain ALL essential information.

## What to Extract

1. **PRIMARY GOAL**: What is the user ultimately trying to achieve?
2. **CURRENT STATE**: What has been accomplished? What's the current status?
3. **LAST ACTIONS**: What just happened? (last 3-5 tool calls, their results)
4. **ACTIVE FILES**: ${filesModified}
5. **PENDING TASKS**: ${pendingTasks}
6. **CRITICAL DETAILS**: File paths, error messages, specific values, decisions made
7. **NEXT STEPS**: What should happen next?

## Analysis Strategy

`
        if (runtime === "bun") {
          return (
            baseQuery +
            `\`\`\`javascript
// First, understand the structure
console.log(\`Context: \${context.length} chars, \${lines().length} lines\`);

// Find the most recent activity (usually most important)
console.log("=== FIRST 30 LINES (user's initial request) ===");
console.log(head(30));

console.log("\\n=== LAST 50 LINES (most recent activity) ===");
console.log(tail(50));

// Search for key patterns
const toolMatches = context.match(/\\[Tool (\\w+)/g) || [];
const tools = [...new Set(toolMatches.map(t => t.replace('[Tool ', '')))];
console.log(\`\\nTools used: \${tools.join(', ')}\`);

const errors = grep(/error|failed/i);
if (errors.length > 0) {
  console.log(\`\\nErrors found (\${errors.length}):\`);
  errors.slice(-3).forEach(e => console.log(\`  - \${e.slice(0, 100)}\`));
}

// Find file paths
const pathMatches = context.match(/[\\/\\w.-]+\\.[a-z]+/g) || [];
const paths = [...new Set(pathMatches)].slice(-10);
console.log(\`\\nFiles mentioned: \${paths.join(', ')}\`);
\`\`\`

After analysis, use llm_query() to create the briefing:

\`\`\`javascript
// Gather key sections for the briefing
const firstPart = context.slice(0, 3000);
const lastPart = context.slice(-5000);
const errorLines = grep(/error|failed/i).join("\\n");

const briefing = await llm_query(\`Create a session briefing from this conversation.

FIRST PART (user's request):
\${firstPart}

RECENT ACTIVITY:
\${lastPart}

ERRORS (if any):
\${errorLines}

Create a briefing with: Goal, Status, Recent Activity, Key Information, Next Steps.
Be SPECIFIC with file paths, function names, error messages.\`);

FINAL(briefing);
\`\`\`

IMPORTANT: Be SPECIFIC. Include actual file paths, function names, error messages. Generic summaries are useless.`
          )
        }

        // Python version
        return (
          baseQuery +
          `\`\`\`python
# First, understand the structure
print(f"Context: {len(context)} chars, {context.count(chr(10))} lines")

# Find the most recent activity (usually most important)
lines = context.split("\\n")
print("=== FIRST 30 LINES (user's initial request) ===")
print("\\n".join(lines[:30]))

print("\\n=== LAST 50 LINES (most recent activity) ===")
print("\\n".join(lines[-50:]))

# Search for key patterns
import re
tools = re.findall(r'\\[Tool (\\w+)', context)
print(f"\\nTools used: {set(tools)}")

errors = re.findall(r'(?:error|failed|Error).*', context, re.IGNORECASE)
if errors:
    print(f"\\nErrors found: {errors[-3:]}")

# Find file paths
paths = re.findall(r'[\\w/.-]+\\.[a-z]+', context)
print(f"\\nFiles mentioned: {set(list(paths)[-10:])}")
\`\`\`

After analysis, use llm_query() to create the briefing:

\`\`\`python
# Gather key sections for the briefing
first_part = context[:3000]
last_part = context[-5000:]
error_lines = "\\n".join([l for l in context.split("\\n") if re.search(r'error|failed', l, re.I)])

briefing = llm_query(f"""Create a session briefing from this conversation.

FIRST PART (user's request):
{first_part}

RECENT ACTIVITY:
{last_part}

ERRORS (if any):
{error_lines}

Create a briefing with: Goal, Status, Recent Activity, Key Information, Next Steps.
Be SPECIFIC with file paths, function names, error messages.""")

FINAL(briefing)
\`\`\`

IMPORTANT: Be SPECIFIC. Include actual file paths, function names, error messages. Generic summaries are useless.`
        )
      default:
        return `Summarize this output concisely, extracting the most important information.`
    }
  }
}
