import { Log } from "../util/log"
import { A2AClient } from "./client"
import { A2AExecutor } from "./executor"

const log = Log.create({ service: "a2a.worker" })

export namespace A2AWorker {
  export interface Config {
    serverUrl: string
    authToken?: string
    workerName: string
    workerId?: string
    codebases: Map<string, string>
  }

  const codebases = new Map<string, string>()

  export function registerCodebase(id: string, path: string): void {
    codebases.set(id, path)
    log.info("registered codebase", { id, path })
  }

  export async function start(config: Config, signal?: AbortSignal): Promise<void> {
    const workerId = config.workerId ?? crypto.randomUUID()

    for (const [id, path] of Array.from(config.codebases.entries())) {
      codebases.set(id, path)
    }

    const clientConfig: A2AClient.Config = {
      serverUrl: config.serverUrl,
      authToken: config.authToken,
      workerName: config.workerName,
      workerId,
      codebases: Array.from(codebases.keys()),
    }

    log.info("starting worker", {
      workerId,
      workerName: config.workerName,
      codebases: clientConfig.codebases,
    })

    await A2AClient.registerCodebases(clientConfig)

    while (!signal?.aborted) {
      try {
        await processTaskStream(clientConfig, signal)
      } catch (e) {
        if (signal?.aborted) break

        const error = e instanceof Error ? e.message : String(e)
        log.error("task stream error, reconnecting", { error })

        await sleep(5000, signal)
      }
    }

    log.info("worker stopped", { workerId })
  }

  async function processTaskStream(config: A2AClient.Config, signal?: AbortSignal): Promise<void> {
    log.info("connecting to task stream")

    for await (const task of A2AClient.taskStream(config)) {
      if (signal?.aborted) break

      const codebasePath = codebases.get(task.codebaseId)
      if (!codebasePath) {
        log.warn("unknown codebase, skipping task", {
          taskId: task.id,
          codebaseId: task.codebaseId,
        })
        continue
      }

      const claimed = await A2AClient.claimTask(config, task.id)
      if (!claimed) continue

      await executeTask(config, task, codebasePath, signal)
    }
  }

  async function executeTask(
    config: A2AClient.Config,
    task: A2AClient.Task,
    codebasePath: string,
    signal?: AbortSignal,
  ): Promise<void> {
    if (signal?.aborted) {
      log.info("task skipped due to abort", { taskId: task.id })
      return
    }

    log.info("executing task", { taskId: task.id, codebasePath })

    const executorTask: A2AExecutor.Task = {
      id: task.id,
      codebase_id: task.codebaseId,
      title: task.title,
      prompt: task.description || task.title,
      agent_type: (task.metadata as Record<string, unknown> | undefined)?.agent_type as string | undefined,
      metadata: task.metadata as A2AExecutor.Task["metadata"],
    }

    const onProgress = (status: string) => {
      if (signal?.aborted) return
      A2AClient.updateTaskStatus(config, task.id, status).catch((e) => {
        log.warn("failed to update task status", { taskId: task.id, error: e })
      })
    }

    const result = await A2AExecutor.execute(executorTask, codebasePath, onProgress)

    if (signal?.aborted) {
      log.info("task aborted after execution", { taskId: task.id })
      await A2AClient.releaseTask(config, task.id, {
        status: "cancelled",
        error: "Worker shutdown",
      })
      return
    }

    const taskResult: A2AClient.TaskResult = {
      status: result.success ? "completed" : "failed",
      result: result.output,
      error: result.error,
    }

    await A2AClient.releaseTask(config, task.id, taskResult)

    log.info("task completed", {
      taskId: task.id,
      success: result.success,
      sessionId: result.sessionId,
    })
  }

  function sleep(ms: number, signal?: AbortSignal): Promise<void> {
    return new Promise((resolve) => {
      const timeout = setTimeout(resolve, ms)
      signal?.addEventListener("abort", () => {
        clearTimeout(timeout)
        resolve()
      })
    })
  }
}
