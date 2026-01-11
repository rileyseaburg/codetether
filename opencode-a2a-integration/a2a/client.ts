import { Log } from "../util/log"
import z from "zod"

export namespace A2AClient {
  const log = Log.create({ service: "a2a.client" })

  export const Config = z.object({
    serverUrl: z.string(),
    authToken: z.string().optional(),
    workerName: z.string(),
    workerId: z.string(),
    codebases: z.array(z.string()),
  })
  export type Config = z.infer<typeof Config>

  export const Task = z.object({
    id: z.string(),
    codebaseId: z.string(),
    title: z.string(),
    description: z.string().optional(),
    priority: z.number().default(0),
    status: z.enum(["pending", "working", "completed", "failed", "cancelled"]),
    metadata: z.record(z.string(), z.unknown()).optional(),
    createdAt: z.string(),
    updatedAt: z.string(),
  })
  export type Task = z.infer<typeof Task>

  export const TaskResult = z.object({
    status: z.enum(["completed", "failed", "cancelled"]),
    result: z.string().optional(),
    error: z.string().optional(),
  })
  export type TaskResult = z.infer<typeof TaskResult>

  export const SessionInfo = z.object({
    id: z.string(),
    projectId: z.string(),
    directory: z.string(),
    title: z.string(),
    status: z.enum(["active", "idle", "completed"]),
    model: z.string().optional(),
    createdAt: z.string(),
    updatedAt: z.string(),
  })
  export type SessionInfo = z.infer<typeof SessionInfo>

  function headers(config: Config, extra?: Record<string, string>): Record<string, string> {
    const result: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Worker-ID": config.workerId,
      "X-Agent-Name": config.workerName,
      ...extra,
    }
    if (config.authToken) {
      result["Authorization"] = `Bearer ${config.authToken}`
    }
    return result
  }

  export async function* taskStream(config: Config): AsyncGenerator<Task> {
    const url = `${config.serverUrl}/v1/worker/tasks/stream`
    log.info("connecting to task stream", { url })

    const response = await fetch(url, {
      headers: {
        ...headers(config),
        "X-Codebases": config.codebases.join(","),
        Accept: "text/event-stream",
      },
    })

    if (!response.ok) {
      log.error("task stream connection failed", { status: response.status })
      throw new Error(`Failed to connect to task stream: ${response.status}`)
    }

    if (!response.body) {
      throw new Error("No response body from task stream")
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ""

    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        log.info("task stream closed")
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split("\n")
      buffer = lines.pop() ?? ""

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue
        const data = line.slice(6).trim()
        if (!data || data === "[DONE]") continue

        const parsed = JSON.parse(data)
        if (parsed.type === "task") {
          const task = Task.parse(parsed.task)
          log.info("received task", { taskId: task.id })
          yield task
        }
      }
    }
  }

  export async function claimTask(config: Config, taskId: string): Promise<boolean> {
    const url = `${config.serverUrl}/v1/worker/tasks/claim`
    log.info("claiming task", { taskId })

    const response = await fetch(url, {
      method: "POST",
      headers: headers(config),
      body: JSON.stringify({ task_id: taskId }),
    })

    if (response.status === 409) {
      log.info("task already claimed", { taskId })
      return false
    }

    if (!response.ok) {
      log.error("failed to claim task", { taskId, status: response.status })
      return false
    }

    log.info("task claimed", { taskId })
    return true
  }

  export async function releaseTask(config: Config, taskId: string, result: TaskResult): Promise<void> {
    const url = `${config.serverUrl}/v1/worker/tasks/release`
    log.info("releasing task", { taskId, status: result.status })

    const response = await fetch(url, {
      method: "POST",
      headers: headers(config),
      body: JSON.stringify({
        task_id: taskId,
        status: result.status,
        result: result.result,
        error: result.error,
      }),
    })

    if (!response.ok) {
      log.error("failed to release task", { taskId, status: response.status })
      throw new Error(`Failed to release task: ${response.status}`)
    }

    log.info("task released", { taskId })
  }

  export async function updateTaskStatus(
    config: Config,
    taskId: string,
    status: string,
    metadata?: Record<string, unknown>,
  ): Promise<void> {
    const url = `${config.serverUrl}/v1/worker/tasks/${taskId}/status`
    log.info("updating task status", { taskId, status })

    const response = await fetch(url, {
      method: "PUT",
      headers: headers(config),
      body: JSON.stringify({ status, metadata }),
    })

    if (!response.ok) {
      log.error("failed to update task status", { taskId, status: response.status })
      throw new Error(`Failed to update task status: ${response.status}`)
    }

    log.info("task status updated", { taskId, status })
  }

  export async function registerCodebases(config: Config): Promise<void> {
    const url = `${config.serverUrl}/v1/worker/codebases`
    log.info("registering codebases", { codebases: config.codebases })

    const response = await fetch(url, {
      method: "PUT",
      headers: headers(config),
      body: JSON.stringify({ codebases: config.codebases }),
    })

    if (!response.ok) {
      log.error("failed to register codebases", { status: response.status })
      throw new Error(`Failed to register codebases: ${response.status}`)
    }

    log.info("codebases registered")
  }

  export async function reportSession(config: Config, session: SessionInfo): Promise<void> {
    const url = `${config.serverUrl}/v1/opencode/codebases/${session.projectId}/sessions/sync`
    log.info("reporting session", { sessionId: session.id, projectId: session.projectId })

    const response = await fetch(url, {
      method: "POST",
      headers: headers(config),
      body: JSON.stringify(session),
    })

    if (!response.ok) {
      log.error("failed to report session", { sessionId: session.id, status: response.status })
      throw new Error(`Failed to report session: ${response.status}`)
    }

    log.info("session reported", { sessionId: session.id })
  }
}
