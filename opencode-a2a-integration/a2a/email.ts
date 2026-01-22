import { Log } from "../util/log"

const log = Log.create({ service: "a2a.email" })

export namespace A2AEmail {
  export interface Config {
    apiKey: string
    from: string
    to: string
    /** Domain for email reply-to addresses (e.g., 'inbound.codetether.run') */
    inboundDomain?: string
    /** Prefix for reply-to addresses (default: 'task') */
    replyPrefix?: string
  }

  export interface TaskReport {
    taskId: string
    title: string
    status: "completed" | "failed"
    sessionId: string
    codebaseId?: string
    output?: string
    error?: string
    duration?: number
    toolCount?: number
    workerName: string
  }

  /**
   * Build the reply-to address for email replies to continue tasks.
   * Format: {prefix}+{sessionId}@{domain}
   * Or: {prefix}+{sessionId}+{codebaseId}@{domain}
   */
  export function buildReplyToAddress(config: Config, sessionId: string, codebaseId?: string): string | undefined {
    if (!config.inboundDomain || !sessionId) {
      return undefined
    }
    const prefix = config.replyPrefix ?? "task"
    if (codebaseId) {
      return `${prefix}+${sessionId}+${codebaseId}@${config.inboundDomain}`
    }
    return `${prefix}+${sessionId}@${config.inboundDomain}`
  }

  function formatDuration(ms?: number): string {
    if (!ms) return "N/A"
    const seconds = Math.floor(ms / 1000)
    const minutes = Math.floor(seconds / 60)
    if (minutes > 0) return `${minutes}m ${seconds % 60}s`
    return `${seconds}s`
  }

  function truncate(text: string, max: number): string {
    if (text.length <= max) return text
    return text.slice(0, max) + "..."
  }

  function buildTaskReportHtml(report: TaskReport, replyEnabled: boolean): string {
    const statusColor = report.status === "completed" ? "#22c55e" : "#ef4444"
    const statusIcon = report.status === "completed" ? "✓" : "✗"
    const outputSection = report.output
      ? `
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 140px;">Output</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
            <pre style="margin: 0; white-space: pre-wrap; word-break: break-word; font-family: monospace; font-size: 13px; background: #f9fafb; padding: 12px; border-radius: 6px; max-height: 300px; overflow-y: auto;">${report.output}</pre>
          </td>
        </tr>`
      : ""
    const errorSection = report.error
      ? `
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 140px;">Error</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
            <pre style="margin: 0; white-space: pre-wrap; word-break: break-word; font-family: monospace; font-size: 13px; background: #fef2f2; padding: 12px; border-radius: 6px; color: #dc2626;">${report.error}</pre>
          </td>
        </tr>`
      : ""

    return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
  <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <div style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%); padding: 24px; text-align: center;">
      <h1 style="margin: 0; color: white; font-size: 20px; font-weight: 600;">A2A Task Report</h1>
    </div>
    <div style="padding: 24px;">
      <div style="display: inline-block; padding: 6px 12px; border-radius: 20px; background: ${statusColor}20; color: ${statusColor}; font-weight: 600; font-size: 14px; margin-bottom: 16px;">
        ${statusIcon} ${report.status.toUpperCase()}
      </div>
      <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 140px;">Task ID</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-family: monospace; font-size: 13px;">${report.taskId}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Title</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">${report.title}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Session ID</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-family: monospace; font-size: 13px;">${report.sessionId}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Worker</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">${report.workerName}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Duration</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">${formatDuration(report.duration)}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Tools Used</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">${report.toolCount ?? 0}</td>
        </tr>
        ${outputSection}
        ${errorSection}
      </table>
    </div>
    ${replyEnabled ? `
    <div style="background: #f9fafb; padding: 16px; text-align: center;">
      <p style="margin: 0 0 8px 0; font-size: 13px; color: #374151; font-weight: 500;">
        Reply to this email to continue the conversation
      </p>
      <p style="margin: 0; font-size: 12px; color: #6b7280;">
        Your reply will be sent to the worker to continue working on this task.
      </p>
      <p style="margin: 8px 0 0 0; font-size: 11px; color: #9ca3af;">
        Sent by OpenCode A2A Worker
      </p>
    </div>` : `
    <div style="background: #f9fafb; padding: 16px; text-align: center; font-size: 12px; color: #6b7280;">
      Sent by OpenCode A2A Worker
    </div>`}
  </div>
</body>
</html>`
  }

  function buildDailySummaryHtml(reports: TaskReport[]): string {
    const completed = reports.filter((r) => r.status === "completed").length
    const failed = reports.filter((r) => r.status === "failed").length
    const total = reports.length
    const totalDuration = reports.reduce((sum, r) => sum + (r.duration ?? 0), 0)
    const totalTools = reports.reduce((sum, r) => sum + (r.toolCount ?? 0), 0)

    const rows = reports
      .map((r) => {
        const statusColor = r.status === "completed" ? "#22c55e" : "#ef4444"
        const statusIcon = r.status === "completed" ? "✓" : "✗"
        return `
        <tr>
          <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; font-family: monospace; font-size: 12px;">${r.taskId.slice(0, 12)}...</td>
          <td style="padding: 10px; border-bottom: 1px solid #e5e7eb;">${truncate(r.title, 40)}</td>
          <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; text-align: center;">
            <span style="color: ${statusColor}; font-weight: 600;">${statusIcon} ${r.status}</span>
          </td>
          <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; text-align: right;">${formatDuration(r.duration)}</td>
          <td style="padding: 10px; border-bottom: 1px solid #e5e7eb; text-align: right;">${r.toolCount ?? 0}</td>
        </tr>`
      })
      .join("")

    return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
  <div style="max-width: 700px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <div style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%); padding: 24px; text-align: center;">
      <h1 style="margin: 0; color: white; font-size: 20px; font-weight: 600;">A2A Daily Summary</h1>
      <p style="margin: 8px 0 0; color: #94a3b8; font-size: 14px;">${new Date().toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</p>
    </div>
    <div style="padding: 24px;">
      <div style="display: flex; gap: 16px; margin-bottom: 24px;">
        <div style="flex: 1; background: #f0fdf4; border-radius: 8px; padding: 16px; text-align: center;">
          <div style="font-size: 28px; font-weight: 700; color: #22c55e;">${completed}</div>
          <div style="font-size: 12px; color: #6b7280; text-transform: uppercase;">Completed</div>
        </div>
        <div style="flex: 1; background: #fef2f2; border-radius: 8px; padding: 16px; text-align: center;">
          <div style="font-size: 28px; font-weight: 700; color: #ef4444;">${failed}</div>
          <div style="font-size: 12px; color: #6b7280; text-transform: uppercase;">Failed</div>
        </div>
        <div style="flex: 1; background: #f8fafc; border-radius: 8px; padding: 16px; text-align: center;">
          <div style="font-size: 28px; font-weight: 700; color: #1e293b;">${total}</div>
          <div style="font-size: 12px; color: #6b7280; text-transform: uppercase;">Total</div>
        </div>
      </div>
      <div style="display: flex; gap: 16px; margin-bottom: 24px;">
        <div style="flex: 1; background: #f8fafc; border-radius: 8px; padding: 12px; text-align: center;">
          <div style="font-size: 16px; font-weight: 600; color: #1e293b;">${formatDuration(totalDuration)}</div>
          <div style="font-size: 11px; color: #6b7280;">Total Duration</div>
        </div>
        <div style="flex: 1; background: #f8fafc; border-radius: 8px; padding: 12px; text-align: center;">
          <div style="font-size: 16px; font-weight: 600; color: #1e293b;">${totalTools}</div>
          <div style="font-size: 11px; color: #6b7280;">Tools Executed</div>
        </div>
      </div>
      <table style="width: 100%; border-collapse: collapse;">
        <thead>
          <tr style="background: #f9fafb;">
            <th style="padding: 10px; text-align: left; font-size: 12px; color: #6b7280; text-transform: uppercase;">Task ID</th>
            <th style="padding: 10px; text-align: left; font-size: 12px; color: #6b7280; text-transform: uppercase;">Title</th>
            <th style="padding: 10px; text-align: center; font-size: 12px; color: #6b7280; text-transform: uppercase;">Status</th>
            <th style="padding: 10px; text-align: right; font-size: 12px; color: #6b7280; text-transform: uppercase;">Duration</th>
            <th style="padding: 10px; text-align: right; font-size: 12px; color: #6b7280; text-transform: uppercase;">Tools</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    </div>
    <div style="background: #f9fafb; padding: 16px; text-align: center; font-size: 12px; color: #6b7280;">
      Sent by OpenCode A2A Worker
    </div>
  </div>
</body>
</html>`
  }

  export async function sendTaskReport(config: Config, report: TaskReport): Promise<void> {
    log.info("sending task report", { taskId: report.taskId, status: report.status, to: config.to })

    const subject = `[A2A] Task ${report.status}: ${report.title}`
    const replyTo = buildReplyToAddress(config, report.sessionId, report.codebaseId)
    const replyEnabled = !!replyTo
    const html = buildTaskReportHtml(report, replyEnabled)

    // Build the email payload
    const payload: Record<string, unknown> = {
      personalizations: [{ to: [{ email: config.to }] }],
      from: { email: config.from },
      subject,
      content: [{ type: "text/html", value: html }],
    }

    // Add reply-to if configured for email reply continuation
    if (replyTo) {
      payload.reply_to = { email: replyTo }
      log.debug("email reply-to set", { replyTo })
    }

    const response = await fetch("https://api.sendgrid.com/v3/mail/send", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${config.apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      const text = await response.text()
      log.error("failed to send task report", { status: response.status, body: text, from: config.from, to: config.to })
      throw new Error(`SendGrid API error: ${response.status} - ${text}`)
    }

    log.info("task report sent", { taskId: report.taskId, to: config.to, replyEnabled })
  }

  export async function sendDailySummary(config: Config, reports: TaskReport[]): Promise<void> {
    if (reports.length === 0) {
      log.info("no reports to send in daily summary")
      return
    }

    log.info("sending daily summary", { count: reports.length, to: config.to })

    const completed = reports.filter((r) => r.status === "completed").length
    const failed = reports.filter((r) => r.status === "failed").length
    const subject = `[A2A] Daily Summary: ${completed} completed, ${failed} failed`
    const html = buildDailySummaryHtml(reports)

    const response = await fetch("https://api.sendgrid.com/v3/mail/send", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${config.apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        personalizations: [{ to: [{ email: config.to }] }],
        from: { email: config.from },
        subject,
        content: [{ type: "text/html", value: html }],
      }),
    })

    if (!response.ok) {
      const text = await response.text()
      log.error("failed to send daily summary", { status: response.status, body: text, from: config.from, to: config.to })
      throw new Error(`SendGrid API error: ${response.status} - ${text}`)
    }

    log.info("daily summary sent", { count: reports.length, to: config.to })
  }
}
