import { RlmRepl } from "./rlm-repl"
import { RlmReplBun } from "./rlm-repl-bun"
import { RlmReplRust } from "./rlm-repl-rust"
import { Log } from "../util/log"
import { Config } from "../config/config"

const log = Log.create({ service: "rlm-pool" })

type Runtime = "python" | "bun" | "rust"
type AnyRepl = RlmRepl.Repl | RlmReplBun.Repl | RlmReplRust.Repl

interface PooledRepl {
  repl: AnyRepl
  runtime: Runtime
  createdAt: number
  lastUsed: number
  inUse: boolean
}

const MAX_POOL_SIZE = 3
const MAX_AGE_MS = 5 * 60 * 1000 // 5 minutes
const CLEANUP_INTERVAL_MS = 60 * 1000 // 1 minute

/**
 * REPL pool for faster RLM processing.
 * Pre-warms REPLs so they're ready when needed.
 */
export namespace RlmPool {
  const pool: PooledRepl[] = []
  let cleanupTimer: ReturnType<typeof setInterval> | undefined

  /**
   * Get the preferred runtime from config.
   */
  async function getPreferredRuntime(): Promise<Runtime> {
    const config = await Config.get()
    const preferred = config.rlm?.runtime ?? "python"

    if (preferred === "rust") {
      const available = await RlmReplRust.isAvailable()
      if (!available) {
        log.warn("Rust runtime not available, falling back to bun")
        return "bun"
      }
      return "rust"
    }

    // Default to bun as it's fastest and always available
    if (preferred === "python") {
      // Could check if python3 is available, but bun is faster
      return "bun"
    }

    return preferred as Runtime
  }

  /**
   * Create a new REPL with the given runtime.
   */
  async function createRepl(runtime: Runtime, context: string): Promise<AnyRepl> {
    switch (runtime) {
      case "rust":
        return RlmReplRust.create(context)
      case "bun":
        return RlmReplBun.create(context)
      case "python":
      default:
        return RlmRepl.create(context)
    }
  }

  /**
   * Execute code on a REPL.
   */
  async function executeOn(
    repl: AnyRepl,
    runtime: Runtime,
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
   * Destroy a REPL.
   */
  async function destroyRepl(repl: AnyRepl, runtime: Runtime): Promise<void> {
    switch (runtime) {
      case "rust":
        return RlmReplRust.destroy(repl as RlmReplRust.Repl)
      case "bun":
        return RlmReplBun.destroy(repl as RlmReplBun.Repl)
      case "python":
      default:
        return RlmRepl.destroy(repl as RlmRepl.Repl)
    }
  }

  /**
   * Acquire a REPL from the pool or create a new one.
   * The context is loaded fresh for each acquisition.
   */
  export async function acquire(context: string): Promise<{
    repl: AnyRepl
    runtime: Runtime
    release: () => Promise<void>
  }> {
    const runtime = await getPreferredRuntime()

    // Always create fresh REPL with context
    // (pooling context doesn't make sense as it changes each time)
    log.info("Creating RLM REPL", { runtime, contextLength: context.length })
    const repl = await createRepl(runtime, context)

    const pooled: PooledRepl = {
      repl,
      runtime,
      createdAt: Date.now(),
      lastUsed: Date.now(),
      inUse: true,
    }

    pool.push(pooled)
    startCleanup()

    return {
      repl,
      runtime,
      release: async () => {
        pooled.inUse = false
        pooled.lastUsed = Date.now()

        // If pool is full, destroy oldest
        if (pool.length > MAX_POOL_SIZE) {
          const toRemove = pool
            .filter((p) => !p.inUse)
            .sort((a, b) => a.lastUsed - b.lastUsed)
            .slice(0, pool.length - MAX_POOL_SIZE)

          for (const p of toRemove) {
            const idx = pool.indexOf(p)
            if (idx !== -1) pool.splice(idx, 1)
            await destroyRepl(p.repl, p.runtime).catch(() => {})
          }
        }
      },
    }
  }

  /**
   * Execute code with automatic acquire/release.
   */
  export async function execute(
    context: string,
    code: string,
    onLlmQuery: (prompt: string) => Promise<string>,
  ): Promise<{ stdout: string; stderr: string; final?: string; runtime: Runtime }> {
    const { repl, runtime, release } = await acquire(context)
    try {
      const result = await executeOn(repl, runtime, code, onLlmQuery)
      return { ...result, runtime }
    } finally {
      await release()
    }
  }

  /**
   * Start cleanup timer.
   */
  function startCleanup() {
    if (cleanupTimer) return
    cleanupTimer = setInterval(cleanup, CLEANUP_INTERVAL_MS)
  }

  /**
   * Stop cleanup timer.
   */
  function stopCleanup() {
    if (cleanupTimer) {
      clearInterval(cleanupTimer)
      cleanupTimer = undefined
    }
  }

  /**
   * Clean up old/unused REPLs.
   */
  async function cleanup() {
    const now = Date.now()
    const toRemove = pool.filter((p) => !p.inUse && now - p.lastUsed > MAX_AGE_MS)

    for (const p of toRemove) {
      const idx = pool.indexOf(p)
      if (idx !== -1) pool.splice(idx, 1)
      await destroyRepl(p.repl, p.runtime).catch(() => {})
      log.info("Cleaned up old REPL", { runtime: p.runtime, age: now - p.createdAt })
    }

    if (pool.length === 0) {
      stopCleanup()
    }
  }

  /**
   * Destroy all REPLs in the pool.
   */
  export async function destroyAll(): Promise<void> {
    stopCleanup()
    const toDestroy = [...pool]
    pool.length = 0

    await Promise.all(toDestroy.map((p) => destroyRepl(p.repl, p.runtime).catch(() => {})))
    log.info("Destroyed all pooled REPLs", { count: toDestroy.length })
  }

  /**
   * Get pool stats.
   */
  export function stats(): { total: number; inUse: number; idle: number } {
    const inUse = pool.filter((p) => p.inUse).length
    return {
      total: pool.length,
      inUse,
      idle: pool.length - inUse,
    }
  }
}
