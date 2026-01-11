import { cmd } from "./cmd"
import { UI } from "../ui"
import { bootstrap } from "../bootstrap"
import { Server } from "../../server/server"
import { createOpencodeClient } from "@opencode-ai/sdk/v2"
import { Log } from "../../util/log"
import { randomBytes } from "crypto"
import { A2AEmail } from "../../a2a/email"
import { Notify } from "../../a2a/notify"
import { Vault } from "../../a2a/vault"

const log = Log.create({ service: "a2a" })

function generateWorkerID(): string {
  return `wrk_${Date.now().toString(36)}_${randomBytes(8).toString("hex")}`
}

interface Task {
  id: string
  title: string
  description?: string
  prompt?: string
  codebase_id?: string
  priority?: number
  status: string
  metadata?: Record<string, unknown>
}

interface TaskEvent {
  event?: string
  type?: string
  task?: Task
  data?: Task
}

export const A2ACommand = cmd({
  command: "a2a",
  describe: "connect to an A2A server as a worker agent",
  builder: (yargs) =>
    yargs
      .option("server", {
        alias: ["s"],
        type: "string",
        describe: "A2A server URL",
        demandOption: true,
      })
      .option("token", {
        alias: ["t"],
        type: "string",
        describe: "authentication token",
      })
      .option("name", {
        alias: ["n"],
        type: "string",
        describe: "worker name",
        default: `opencode-worker-${process.pid}`,
      })
      .option("codebases", {
        alias: ["c"],
        type: "string",
        describe: "comma-separated list of codebase paths",
      })
      .option("auto-approve", {
        type: "string",
        choices: ["all", "safe", "none"],
        default: "safe",
        describe: "auto-approve policy: all, safe (read-only), none",
      })
      .option("email", {
        alias: ["e"],
        type: "string",
        describe: "email address for task completion reports",
      })
      .option("sendgrid-key", {
        type: "string",
        describe: "SendGrid API key (or set SENDGRID_API_KEY env var)",
      })
      .option("push-url", {
        type: "string",
        describe: "push notification endpoint URL",
      })
      .option("push-token", {
        type: "string",
        describe: "authentication token for push notifications",
      }),
  handler: async (args) => {
    const server = args.server.replace(/\/$/, "")
    const token = args.token
    const name = args.name
    const codebases = args.codebases
      ?.split(",")
      .map((p) => p.trim())
      .filter(Boolean) ?? [process.cwd()]
    const policy = args["auto-approve"] as "all" | "safe" | "none"
    const workerID = generateWorkerID()
    const email = args.email

    // Resolve SendGrid API key: CLI flag > env var > Vault (only if VAULT_ADDR is set)
    let sendgridKey = args["sendgrid-key"] ?? process.env.SENDGRID_API_KEY
    if (email && !sendgridKey && process.env.VAULT_ADDR) {
      UI.println(UI.Style.TEXT_DIM + "  Fetching SendGrid key from Vault...")
      sendgridKey = (await Vault.getSendGridKey()) ?? undefined
    }

    const emailConfig: A2AEmail.Config | undefined =
      email && sendgridKey
        ? {
            apiKey: sendgridKey,
            from: "noreply@spotlessbinco.com",
            to: email,
          }
        : undefined

    // Build push notification config
    const pushUrl = args["push-url"]
    const pushToken = args["push-token"]

    const notifyConfig: Notify.Config = {
      // Always send to A2A server monitor (shows up in iOS app)
      a2aServer: { url: server, token, workerName: name },
    }
    if (pushUrl) {
      notifyConfig.push = { endpoint: pushUrl, token: pushToken }
    }
    if (email && sendgridKey) {
      notifyConfig.email = { to: email, sendgridKey }
    }

    UI.println(UI.Style.TEXT_INFO_BOLD + "~", UI.Style.TEXT_NORMAL, `Starting A2A worker: ${name}`)
    UI.println(UI.Style.TEXT_DIM + "  Worker ID:", workerID)
    UI.println(UI.Style.TEXT_DIM + "  Server:", server)
    UI.println(UI.Style.TEXT_DIM + "  Codebases:", codebases.join(", "))
    if (emailConfig) {
      UI.println(UI.Style.TEXT_DIM + "  Email reports:", emailConfig.to)
    }
    if (pushUrl) {
      UI.println(UI.Style.TEXT_DIM + "  Push notifications:", pushUrl)
    }

    const codebase = codebases[0]
    const processing = new Set<string>()

    await bootstrap(codebase, async () => {
      const localServer = Server.listen({ port: 0, hostname: "127.0.0.1" })
      const sdk = createOpencodeClient({ baseUrl: `http://${localServer.hostname}:${localServer.port}` })

      const baseHeaders: Record<string, string> = { "Content-Type": "application/json" }
      if (token) baseHeaders["Authorization"] = `Bearer ${token}`

      // Send worker started notification
      await Notify.send(notifyConfig, {
        type: "worker_started",
        title: "OpenCode Worker Started",
        message: `Worker '${name}' connected to A2A server`,
        metadata: { worker: name, worker_id: workerID, server },
      }).catch((e) => log.warn("startup notification failed", { error: String(e) }))

      // Setup shutdown handlers
      let shuttingDown = false
      const shutdown = async (signal: string) => {
        if (shuttingDown) return
        shuttingDown = true
        UI.println()
        UI.println(UI.Style.TEXT_WARNING_BOLD + "!", UI.Style.TEXT_NORMAL, `Received ${signal}, shutting down...`)
        await Notify.send(notifyConfig, {
          type: "worker_stopped",
          title: "OpenCode Worker Stopped",
          message: `Worker '${name}' disconnected (${signal})`,
          metadata: { worker: name, worker_id: workerID, signal },
        }).catch(() => {})
        localServer.stop()
        process.exit(0)
      }

      process.on("SIGINT", () => shutdown("SIGINT"))
      process.on("SIGTERM", () => shutdown("SIGTERM"))

      // Report session to A2A server
      const reportSession = async (sessionID: string, taskID: string, status: string) => {
        await fetch(`${server}/v1/opencode/sessions/${sessionID}/sync`, {
          method: "POST",
          headers: baseHeaders,
          body: JSON.stringify({ task_id: taskID, status, worker_id: workerID }),
        }).catch(() => {})
      }

      // Update task status during execution
      const updateTaskStatus = async (taskID: string, status: string, metadata?: Record<string, unknown>) => {
        await fetch(`${server}/v1/opencode/tasks/${taskID}/status`, {
          method: "PUT",
          headers: baseHeaders,
          body: JSON.stringify({ status, metadata, worker_id: workerID }),
        }).catch(() => {})
      }

      // Register worker with server
      const registerWorker = async () => {
        UI.println(UI.Style.TEXT_INFO_BOLD + "~", UI.Style.TEXT_NORMAL, "Registering worker...")
        const res = await fetch(`${server}/v1/worker/codebases`, {
          method: "PUT",
          headers: baseHeaders,
          body: JSON.stringify({ codebases, worker_id: workerID, agent_name: name }),
        }).catch(() => null)
        if (res?.ok) {
          UI.println(UI.Style.TEXT_SUCCESS_BOLD + "✓", UI.Style.TEXT_NORMAL, "Worker registered")
        }
      }

      // Fetch and process any pending tasks on startup
      const fetchPendingTasks = async () => {
        UI.println(UI.Style.TEXT_INFO_BOLD + "~", UI.Style.TEXT_NORMAL, "Checking for pending tasks...")
        const res = await fetch(`${server}/v1/opencode/tasks?status=pending`, {
          headers: baseHeaders,
        }).catch(() => null)
        if (!res?.ok) return

        const data = await res.json().catch(() => ({ tasks: [] }))
        const tasks = (data.tasks || data || []) as Task[]
        UI.println(UI.Style.TEXT_DIM + `  Found ${tasks.length} pending task(s)`)

        for (const task of tasks) {
          if (processing.has(task.id)) continue
          processing.add(task.id)
          handleTask(
            task,
            sdk,
            server,
            token,
            workerID,
            name,
            policy,
            processing,
            emailConfig,
            notifyConfig,
            updateTaskStatus,
            reportSession,
          ).catch((e) => {
            log.error("task_error", { taskID: task.id, error: String(e) })
            processing.delete(task.id)
          })
        }
      }

      await registerWorker()
      await fetchPendingTasks()

      const connect = async (): Promise<void> => {
        const sseHeaders: Record<string, string> = {
          Accept: "text/event-stream",
          "X-Worker-ID": workerID,
          "X-Agent-Name": name,
          "X-Codebases": codebases.join(","),
        }
        if (token) sseHeaders["Authorization"] = `Bearer ${token}`

        const url = `${server}/v1/worker/tasks/stream?agent_name=${encodeURIComponent(name)}&worker_id=${encodeURIComponent(workerID)}`

        UI.println(UI.Style.TEXT_INFO_BOLD + "~", UI.Style.TEXT_NORMAL, "Connecting to task stream...")

        const response = await fetch(url, { headers: sseHeaders })

        if (!response.ok) {
          UI.error(`Failed to connect: ${response.status} ${response.statusText}`)
          await Bun.sleep(5000)
          return connect()
        }

        if (!response.body) {
          UI.error("No response body")
          await Bun.sleep(5000)
          return connect()
        }

        UI.println(UI.Style.TEXT_SUCCESS_BOLD + "✓", UI.Style.TEXT_NORMAL, "Connected to A2A server")

        // Re-fetch pending tasks after reconnect
        await fetchPendingTasks()

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ""
        let eventType = ""

        const processEvents = async (): Promise<void> => {
          const { done, value } = await reader.read()

          if (done) {
            UI.println(UI.Style.TEXT_WARNING_BOLD + "!", UI.Style.TEXT_NORMAL, "Connection closed, reconnecting...")
            await Bun.sleep(1000)
            return connect()
          }

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split("\n")
          buffer = lines.pop() ?? ""

          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventType = line.slice(6).trim()
              continue
            }
            if (!line.startsWith("data:")) continue

            const data = line.slice(5).trim()
            if (!data || data === "[DONE]") continue

            const parsed = JSON.parse(data) as TaskEvent
            const task = parsed.task || parsed.data || (parsed as unknown as Task)
            const type = eventType || parsed.event || parsed.type || ""

            if ((type === "task_available" || type === "task" || type === "task_assigned") && task?.id) {
              if (processing.has(task.id)) continue
              processing.add(task.id)
              handleTask(
                task,
                sdk,
                server,
                token,
                workerID,
                name,
                policy,
                processing,
                emailConfig,
                notifyConfig,
                updateTaskStatus,
                reportSession,
              ).catch((e) => {
                log.error("task_error", { taskID: task.id, error: String(e) })
                processing.delete(task.id)
              })
            }

            eventType = ""
          }

          return processEvents()
        }

        return processEvents()
      }

      await connect()
      localServer.stop()
    })
  },
})

async function handleTask(
  task: Task,
  sdk: ReturnType<typeof createOpencodeClient>,
  server: string,
  token: string | undefined,
  workerID: string,
  workerName: string,
  policy: "all" | "safe" | "none",
  processing: Set<string>,
  emailConfig?: A2AEmail.Config,
  notifyConfig?: Notify.Config,
  updateStatus?: (taskID: string, status: string, metadata?: Record<string, unknown>) => Promise<void>,
  reportSession?: (sessionID: string, taskID: string, status: string) => Promise<void>,
) {
  const startTime = Date.now()
  UI.println()
  UI.println(UI.Style.TEXT_INFO_BOLD + "→", UI.Style.TEXT_NORMAL, `Task available: ${task.title}`)
  log.info("task_available", { taskID: task.id, title: task.title })

  const headers: Record<string, string> = { "Content-Type": "application/json", "X-Worker-ID": workerID }
  if (token) headers["Authorization"] = `Bearer ${token}`

  const claimResponse = await fetch(`${server}/v1/worker/tasks/claim`, {
    method: "POST",
    headers,
    body: JSON.stringify({ task_id: task.id }),
  })

  if (!claimResponse.ok) {
    const text = await claimResponse.text()
    UI.println(UI.Style.TEXT_WARNING_BOLD + "!", UI.Style.TEXT_NORMAL, `Failed to claim task: ${text}`)
    log.warn("claim_failed", { taskID: task.id, status: claimResponse.status, body: text })
    processing.delete(task.id)
    return
  }

  UI.println(UI.Style.TEXT_SUCCESS_BOLD + "✓", UI.Style.TEXT_NORMAL, `Claimed task: ${task.id}`)
  log.info("task_claimed", { taskID: task.id })

  await updateStatus?.(task.id, "working", { phase: "creating_session" })

  const sessionResult = await sdk.session.create({ title: task.title })
  if (!sessionResult.data?.id) {
    UI.error("Failed to create session")
    await releaseTask(server, token, workerID, task.id, "failed", "Failed to create session")
    processing.delete(task.id)
    return
  }

  const sessionID = sessionResult.data.id
  UI.println(UI.Style.TEXT_DIM + "  Session:", sessionID)

  await reportSession?.(sessionID, task.id, "started")
  await updateStatus?.(task.id, "working", { phase: "executing", session_id: sessionID })

  const prompt = task.prompt || task.description || task.title
  let output = ""
  let errorMsg: string | undefined
  let toolCount = 0

  const events = await sdk.event.subscribe()

  const eventProcessor = (async () => {
    for await (const event of events.stream) {
      if (event.type === "message.part.updated") {
        const part = event.properties.part
        if (part.sessionID !== sessionID) continue

        if (part.type === "tool" && part.state.status === "running") {
          toolCount++
          await updateStatus?.(task.id, "working", {
            phase: "tool_execution",
            tool: part.tool,
            tool_count: toolCount,
          })
        }

        if (part.type === "tool" && part.state.status === "completed") {
          const title = part.state.title || JSON.stringify(part.state.input)
          UI.println(
            UI.Style.TEXT_INFO_BOLD + "|",
            UI.Style.TEXT_DIM,
            part.tool.padEnd(12),
            UI.Style.TEXT_NORMAL,
            title,
          )
        }

        if (part.type === "text" && part.time?.end) {
          output = part.text
          UI.println()
          UI.println(part.text)
          UI.println()
        }
      }

      if (event.type === "session.error") {
        const props = event.properties
        if (props.sessionID !== sessionID || !props.error) continue
        errorMsg =
          "data" in props.error && props.error.data && "message" in props.error.data
            ? String(props.error.data.message)
            : String(props.error.name)
        UI.error(errorMsg)
      }

      if (event.type === "session.idle" && event.properties.sessionID === sessionID) {
        break
      }

      if (event.type === "permission.updated") {
        const permission = event.properties
        if (permission.sessionID !== sessionID) continue

        const tool = permission.type || ""
        const isReadOnly = ["read", "glob", "grep", "list", "websearch", "lsp"].includes(tool)

        const approved = policy === "all" || (policy === "safe" && isReadOnly)
        const response: "once" | "always" | "reject" = approved ? "once" : "reject"

        if (approved) {
          const label = policy === "all" ? "Auto-approved" : "Auto-approved (safe)"
          UI.println(UI.Style.TEXT_INFO_BOLD + "~", UI.Style.TEXT_NORMAL, `${label}: ${permission.title}`)
        }
        if (!approved) {
          UI.println(UI.Style.TEXT_WARNING_BOLD + "!", UI.Style.TEXT_NORMAL, `Auto-rejected: ${permission.title}`)
        }

        await sdk.permission.respond({
          sessionID,
          permissionID: permission.id,
          response,
        })
      }
    }
  })()

  await sdk.session.prompt({
    sessionID,
    parts: [{ type: "text", text: prompt }],
  })

  await eventProcessor

  const status = errorMsg ? "failed" : "completed"
  const result = errorMsg ?? output
  const duration = Date.now() - startTime

  await reportSession?.(sessionID, task.id, status)
  await releaseTask(server, token, workerID, task.id, status, result)

  // Send email report if configured
  if (emailConfig) {
    const report: A2AEmail.TaskReport = {
      taskId: task.id,
      title: task.title,
      status,
      sessionId: sessionID,
      output: status === "completed" ? output : undefined,
      error: errorMsg,
      duration,
      toolCount,
      workerName,
    }
    await A2AEmail.sendTaskReport(emailConfig, report)
    UI.println(UI.Style.TEXT_DIM + "  Email report sent to:", emailConfig.to)
  }

  // Send push notification for task completion/failure
  if (notifyConfig) {
    const eventType: Notify.Event["type"] = status === "completed" ? "task_completed" : "task_failed"
    await Notify.send(notifyConfig, {
      type: eventType,
      title: status === "completed" ? "Task Completed" : "Task Failed",
      message: `${task.title} (${Math.round(duration / 1000)}s)`,
      metadata: { task_id: task.id, session_id: sessionID, duration, tool_count: toolCount, worker: workerName },
    }).catch((e) => log.warn("task notification failed", { error: String(e) }))
  }

  processing.delete(task.id)
  UI.println(UI.Style.TEXT_SUCCESS_BOLD + "✓", UI.Style.TEXT_NORMAL, `Task ${status}: ${task.id}`)
  log.info("task_released", { taskID: task.id, status, sessionID, toolCount, duration })
}

async function releaseTask(
  server: string,
  token: string | undefined,
  workerID: string,
  taskID: string,
  status: "completed" | "failed",
  result: string,
) {
  const headers: Record<string, string> = { "Content-Type": "application/json", "X-Worker-ID": workerID }
  if (token) headers["Authorization"] = `Bearer ${token}`

  const response = await fetch(`${server}/v1/worker/tasks/release`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      task_id: taskID,
      status,
      result,
    }),
  })

  if (!response.ok) {
    const text = await response.text()
    UI.println(UI.Style.TEXT_WARNING_BOLD + "!", UI.Style.TEXT_NORMAL, `Failed to release task: ${text}`)
    log.warn("release_failed", { taskID, status: response.status, body: text })
  }
}
