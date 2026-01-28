import { createMemo, createSignal, onCleanup, onMount, Show } from "solid-js"
import { useTheme } from "@tui/context/theme"
import { useSync } from "@tui/context/sync"
import { createStore } from "solid-js/store"

export function RlmPane(props: { sessionID: string }) {
  const { theme } = useTheme()
  const sync = useSync()

  const [store, setStore] = createStore({
    active: false,
    inputTokens: 0,
    outputTokens: 0,
    iteration: 0,
    maxIterations: 15,
    subcalls: 0,
    phase: "" as string,
    status: "idle" as "idle" | "running" | "completed" | "error",
    contentType: "" as string,
    elapsed: 0,
  })

  const [frame, setFrame] = createSignal(0)
  const spinnerFrames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

  onMount(() => {
    const interval = setInterval(() => {
      if (store.active && store.status === "running") {
        setFrame((f) => (f + 1) % spinnerFrames.length)
      }
    }, 80)
    onCleanup(() => clearInterval(interval))
  })

  // Watch for RLM status updates
  const rlmStatus = createMemo(() => {
    const status = sync.data.session_status[props.sessionID]
    if (status?.type === "rlm") return status
    return null
  })

  // Watch for RLM tool parts in the session messages
  const rlmPart = createMemo(() => {
    const messages = sync.data.message[props.sessionID] ?? []
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i]
      if (msg.role !== "assistant") continue
      const parts = sync.data.part[msg.id] ?? []
      for (let j = parts.length - 1; j >= 0; j--) {
        const part = parts[j]
        if (part.type === "tool" && part.tool === "rlm") {
          return part
        }
      }
    }
    return null
  })

  // Update store based on RLM status events
  createMemo(() => {
    const status = rlmStatus()
    if (status) {
      setStore({
        active: true,
        status: "running",
        phase: status.phase,
        iteration: (status as any).iteration ?? store.iteration,
        subcalls: (status as any).subcalls ?? store.subcalls,
      })
      return
    }

    const part = rlmPart()
    if (!part) {
      if (store.active && store.status !== "idle") {
        // Keep showing for a bit after completion
      } else {
        setStore({ active: false })
      }
      return
    }

    const state = part.state
    const meta = (state as any).metadata ?? {}
    const stats = meta.stats ?? {}

    if (state.status === "pending" || state.status === "running") {
      setStore({
        active: true,
        status: "running",
        iteration: meta.iteration ?? stats.iterations ?? store.iteration,
        maxIterations: meta.maxIterations ?? 15,
        subcalls: stats.subcalls ?? store.subcalls,
        inputTokens: stats.inputTokens ?? store.inputTokens,
        phase: meta.status ?? "processing",
      })
    } else if (state.status === "completed") {
      setStore({
        status: "completed",
        outputTokens: stats.outputTokens ?? 0,
        iteration: stats.iterations ?? store.iteration,
        subcalls: stats.subcalls ?? store.subcalls,
        elapsed: stats.elapsed ?? 0,
      })
      setTimeout(() => setStore({ active: false, status: "idle" }), 3000)
    } else if (state.status === "error") {
      setStore({ status: "error" })
      setTimeout(() => setStore({ active: false, status: "idle" }), 4000)
    }
  })

  const spinner = createMemo(() => spinnerFrames[frame()])
  const statusIcon = createMemo(() => {
    if (store.status === "running") return spinner()
    if (store.status === "completed") return "✓"
    if (store.status === "error") return "✗"
    return "○"
  })
  const statusColor = createMemo(() => {
    if (store.status === "running") return theme.accent
    if (store.status === "completed") return theme.success
    if (store.status === "error") return theme.error
    return theme.textMuted
  })

  const compressionRatio = createMemo(() => {
    if (store.inputTokens > 0 && store.outputTokens > 0) {
      return (store.inputTokens / store.outputTokens).toFixed(1)
    }
    return null
  })

  const phaseText = createMemo(() => {
    switch (store.phase) {
      case "started":
        return "Starting..."
      case "analyzing":
        return "Analyzing"
      case "summarizing":
        return "Processing"
      case "completing":
        return "Finishing"
      default:
        return store.phase || "Processing"
    }
  })

  return (
    <Show when={store.active}>
      <box backgroundColor={theme.backgroundPanel} paddingLeft={2} height={1} flexShrink={0}>
        <box flexDirection="row" gap={2}>
          <text fg={statusColor()}>{statusIcon()}</text>
          <text fg={theme.accent}>RLM</text>

          <Show when={store.status === "running"}>
            <text fg={theme.text}>{phaseText()}</text>
            <text fg={theme.textMuted}>
              iter {store.iteration}/{store.maxIterations}
            </text>
            <Show when={store.subcalls > 0}>
              <text fg={theme.textMuted}>• {store.subcalls} sub-calls</text>
            </Show>
          </Show>

          <Show when={store.status === "completed"}>
            <text fg={theme.success}>Done</text>
            <Show when={compressionRatio()}>
              <text fg={theme.textMuted}>{compressionRatio()}x compression</text>
            </Show>
            <text fg={theme.textMuted}>
              {store.iteration} iter • {store.subcalls} sub-calls
            </text>
            <Show when={store.elapsed > 0}>
              <text fg={theme.textMuted}>• {(store.elapsed / 1000).toFixed(1)}s</text>
            </Show>
          </Show>

          <Show when={store.status === "error"}>
            <text fg={theme.error}>Failed</text>
          </Show>
        </box>
      </box>
    </Show>
  )
}
