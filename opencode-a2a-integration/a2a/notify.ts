import { Log } from "../util/log"

const log = Log.create({ service: "a2a.notify" })

export namespace Notify {
  export interface Config {
    a2aServer?: {
      url: string
      token?: string
      workerName: string
    }
    email?: {
      to: string
      sendgridKey: string
      from: string
    }
    push?: {
      endpoint: string
      token?: string
      deviceId?: string
    }
  }

  export interface Event {
    type: "worker_started" | "worker_stopped" | "task_started" | "task_completed" | "task_failed" | "error"
    title: string
    message: string
    metadata?: Record<string, unknown>
  }

  export async function send(config: Config, event: Event): Promise<void> {
    const promises: Promise<void>[] = []

    // Send to A2A server monitor (shows up in iOS app via SSE)
    if (config.a2aServer?.url) {
      promises.push(
        sendToMonitor(config.a2aServer.url, config.a2aServer.token, config.a2aServer.workerName, event).catch((e) => {
          log.warn("monitor notification failed", { error: String(e) })
        }),
      )
    }

    if (config.push?.endpoint) {
      promises.push(
        sendPush(config.push.endpoint, event, config.push.token).catch((e) => {
          log.warn("push notification failed", { error: String(e) })
        }),
      )
    }

    if (config.email?.sendgridKey && config.email?.to && config.email?.from) {
      promises.push(
        sendEmail(config.email.to, config.email.from, config.email.sendgridKey, event).catch((e) => {
          log.warn("email notification failed", { error: String(e) })
        }),
      )
    }

    await Promise.all(promises)
  }

  async function sendToMonitor(
    serverUrl: string,
    token: string | undefined,
    workerName: string,
    event: Event,
  ): Promise<void> {
    log.info("sending to monitor", { type: event.type, server: serverUrl })

    const headers: Record<string, string> = { "Content-Type": "application/json" }
    if (token) headers["Authorization"] = `Bearer ${token}`

    // Use the intervene endpoint to send messages that show up in the monitor
    const body = {
      agent_id: workerName,
      message: `[${event.type.toUpperCase()}] ${event.title}\n\n${event.message}`,
      timestamp: new Date().toISOString(),
    }

    const response = await fetch(`${serverUrl}/v1/monitor/intervene`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      const text = await response.text()
      log.warn("monitor notification failed", { status: response.status, body: text })
      return
    }

    log.info("monitor notification sent", { type: event.type })
  }

  export async function sendPush(endpoint: string, event: Event, token?: string): Promise<void> {
    log.info("sending push notification", { type: event.type, endpoint })

    const headers: Record<string, string> = { "Content-Type": "application/json" }
    if (token) headers["Authorization"] = `Bearer ${token}`

    const body = {
      title: event.title,
      body: event.message,
      data: { type: event.type, ...event.metadata },
    }

    const response = await fetch(endpoint, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    })

    if (!response.ok) {
      const text = await response.text()
      log.warn("push notification failed", { status: response.status, body: text })
      return
    }

    log.info("push notification sent", { type: event.type })
  }

  async function sendEmail(to: string, from: string, apiKey: string, event: Event): Promise<void> {
    log.info("sending email notification", { type: event.type, to, from })

    const subject = `[OpenCode] ${event.title}`
    const html = buildEmailHtml(event)

    const response = await fetch("https://api.sendgrid.com/v3/mail/send", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        personalizations: [{ to: [{ email: to }] }],
        from: { email: from },
        subject,
        content: [{ type: "text/html", value: html }],
      }),
    })

    if (!response.ok) {
      const text = await response.text()
      log.error("email notification failed", { status: response.status, body: text, from, to })
      throw new Error(`SendGrid API error: ${response.status} - ${text}`)
    }

    log.info("email notification sent", { type: event.type })
  }

  function buildEmailHtml(event: Event): string {
    const colorMap: Record<Event["type"], string> = {
      worker_started: "#22c55e",
      worker_stopped: "#6b7280",
      task_started: "#3b82f6",
      task_completed: "#22c55e",
      task_failed: "#ef4444",
      error: "#ef4444",
    }
    const color = colorMap[event.type] ?? "#6b7280"

    const metadataRows = event.metadata
      ? Object.entries(event.metadata)
          .map(
            ([key, value]) =>
              `<tr><td style="padding: 8px; font-weight: 600;">${key}</td><td style="padding: 8px;">${String(value)}</td></tr>`,
          )
          .join("")
      : ""

    return `
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f3f4f6;">
  <div style="max-width: 500px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <div style="background: ${color}; padding: 20px; text-align: center;">
      <h1 style="margin: 0; color: white; font-size: 18px;">${event.title}</h1>
    </div>
    <div style="padding: 20px;">
      <p style="margin: 0 0 16px; color: #374151;">${event.message}</p>
      ${metadataRows ? `<table style="width: 100%; border-collapse: collapse; font-size: 14px;">${metadataRows}</table>` : ""}
    </div>
  </div>
</body>
</html>`
  }
}
