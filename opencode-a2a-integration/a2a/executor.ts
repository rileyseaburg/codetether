import { Session } from "../session"
import { SessionPrompt } from "../session/prompt"
import { Agent } from "../agent/agent"
import { Provider } from "../provider/provider"
import { Bus } from "../bus"
import { MessageV2 } from "../session/message-v2"
import { SessionStatus } from "../session/status"
import { Log } from "../util/log"

const log = Log.create({ service: "a2a.executor" })

export namespace A2AExecutor {
  export interface Task {
    id: string
    codebase_id: string
    title: string
    prompt: string
    agent_type?: string
    metadata?: {
      model?: string
      files?: string[]
    }
  }

  export interface ExecutionResult {
    success: boolean
    sessionId: string
    output?: string
    error?: string
  }

  export async function execute(
    task: Task,
    _codebasePath: string,
    onProgress?: (status: string) => void,
  ): Promise<ExecutionResult> {
    log.info("executing task", { taskId: task.id })

    const name = task.agent_type ?? "build"
    const agent = await Agent.get(name)
    if (!agent) {
      return {
        success: false,
        sessionId: "",
        error: `Agent "${name}" not found`,
      }
    }

    const session = await Session.create({ title: task.title })
    log.info("created session", { sessionId: session.id, taskId: task.id })
    onProgress?.(`Session created: ${session.id}`)

    const model = await resolveModel(task, agent)
    if (!model) {
      return {
        success: false,
        sessionId: session.id,
        error: "Failed to resolve model",
      }
    }

    const state = { output: "", error: undefined as string | undefined }
    const unsubs: (() => void)[] = []

    unsubs.push(
      Bus.subscribe(MessageV2.Event.PartUpdated, (event) => {
        const part = event.properties.part
        if (part.sessionID !== session.id) return

        if (part.type === "text" && part.time?.end) {
          state.output = part.text
          onProgress?.(`Response received`)
        }

        if (part.type === "tool" && part.state.status === "completed") {
          onProgress?.(`Tool: ${part.state.title || part.tool}`)
        }

        if (part.type === "tool" && part.state.status === "error") {
          onProgress?.(`Tool error: ${part.state.error}`)
        }
      }),
    )

    unsubs.push(
      Bus.subscribe(Session.Event.Error, (event) => {
        if (event.properties.sessionID !== session.id) return
        const err = event.properties.error
        state.error =
          err && "data" in err && err.data && "message" in err.data
            ? String(err.data.message)
            : String(err?.name ?? "Unknown error")
        onProgress?.(`Error: ${state.error}`)
      }),
    )

    const parts = buildPromptParts(task)
    onProgress?.(`Sending prompt to ${name} agent`)

    const result = await SessionPrompt.prompt({
      sessionID: session.id,
      agent: name,
      model,
      parts,
    }).catch((err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err)
      log.error("task execution failed", { taskId: task.id, error: msg })
      return { error: msg }
    })

    await waitForIdle(session.id)
    for (const unsub of unsubs) unsub()

    if ("error" in result) {
      return {
        success: false,
        sessionId: session.id,
        error: result.error,
      }
    }

    if (state.error) {
      return {
        success: false,
        sessionId: session.id,
        error: state.error,
      }
    }

    return {
      success: true,
      sessionId: session.id,
      output: state.output || (await extractFinalOutput(session.id)),
    }
  }

  async function resolveModel(
    task: Task,
    agent: Agent.Info,
  ): Promise<{ providerID: string; modelID: string } | undefined> {
    if (task.metadata?.model) return Provider.parseModel(task.metadata.model)
    if (agent.model) return agent.model
    return Provider.defaultModel()
  }

  function buildPromptParts(task: Task): SessionPrompt.PromptInput["parts"] {
    const parts: SessionPrompt.PromptInput["parts"] = [
      {
        type: "text",
        text: task.prompt,
      },
    ]

    for (const filepath of task.metadata?.files ?? []) {
      parts.push({
        type: "file",
        url: `file://${filepath}`,
        filename: filepath,
        mime: "text/plain",
      })
    }

    return parts
  }

  function waitForIdle(id: string): Promise<void> {
    return new Promise((resolve) => {
      if (SessionStatus.get(id).type === "idle") {
        resolve()
        return
      }

      const unsub = Bus.subscribe(SessionStatus.Event.Idle, (event) => {
        if (event.properties.sessionID !== id) return
        unsub()
        resolve()
      })
    })
  }

  async function extractFinalOutput(id: string): Promise<string> {
    const msgs = await Session.messages({ sessionID: id, limit: 10 })

    for (const msg of msgs.toReversed()) {
      if (msg.info.role !== "assistant") continue

      for (const part of msg.parts) {
        if (part.type === "text" && part.text) return part.text
      }
    }

    return ""
  }
}
