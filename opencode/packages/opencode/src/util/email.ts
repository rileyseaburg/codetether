/**
 * Email Notifications for Knative Workers
 * 
 * Sends task completion emails via SendGrid.
 * Used by cloudevent handler when tasks complete.
 */

const SENDGRID_API_URL = 'https://api.sendgrid.com/v3/mail/send'

interface EmailConfig {
  apiKey: string
  fromEmail: string
  inboundDomain?: string
  replyPrefix?: string
}

interface TaskCompletionEmailParams {
  toEmail: string
  taskId: string
  title: string
  status: 'completed' | 'failed'
  result?: string
  error?: string
  runtimeSeconds?: number
  sessionId?: string
  workerName?: string
  tenantConfig?: TenantEmailConfig
}

function getConfig(): EmailConfig {
  return {
    apiKey: process.env.SENDGRID_API_KEY || '',
    fromEmail: process.env.SENDGRID_FROM_EMAIL || '',
    inboundDomain: process.env.EMAIL_INBOUND_DOMAIN,
    replyPrefix: process.env.EMAIL_REPLY_PREFIX || 'task',
  }
}

export function isEmailConfigured(): boolean {
  const config = getConfig()
  return !!(config.apiKey && config.fromEmail)
}

function formatRuntime(seconds?: number): string {
  if (!seconds) return 'N/A'
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`
  }
  return `${seconds}s`
}

function sanitizeResult(result?: string, maxLength: number = 3000): string {
  if (!result) return ''
  
  // Basic HTML escaping
  let displayResult = result
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
    .replace(/\n/g, '<br>')
  
  if (displayResult.length > maxLength) {
    displayResult = displayResult.substring(0, maxLength) + '...'
  }
  
  return displayResult
}

function buildEmailHtml(params: TaskCompletionEmailParams): string {
  const statusColor = params.status === 'completed' ? '#22c55e' : '#ef4444'
  const statusIcon = params.status === 'completed' ? '✓' : '✗'
  const durationStr = formatRuntime(params.runtimeSeconds)
  const workerName = params.workerName || params.tenantConfig?.fromName || 'CodeTether'
  
  // Result section
  let resultSection = ''
  if (params.result && params.status === 'completed') {
    const sanitized = sanitizeResult(params.result)
    if (sanitized) {
      resultSection = `
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 140px; vertical-align: top;">Output</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
            <div style="font-size: 14px; line-height: 1.6; color: #1f2937;">${sanitized}</div>
          </td>
        </tr>`
    }
  }
  
  // Error section
  let errorSection = ''
  if (params.error) {
    const truncated = params.error.length > 1000 
      ? params.error.substring(0, 1000) + '...' 
      : params.error
    const escapedError = truncated
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
    
    errorSection = `
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 140px;">Error</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
            <pre style="margin: 0; white-space: pre-wrap; word-break: break-word; font-family: monospace; font-size: 13px; background: #fef2f2; padding: 12px; border-radius: 6px; color: #dc2626;">${escapedError}</pre>
          </td>
        </tr>`
  }
  
  // Footer
  const footerHtml = `
    <div style="background: #f9fafb; padding: 16px; text-align: center; font-size: 12px; color: #6b7280;">
      Sent by CodeTether - ${workerName}
    </div>`
  
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
  <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <div style="background: linear-gradient(135deg, #1e293b 0%, #334155 100%); padding: 24px; text-align: center;">
      <h1 style="margin: 0; color: white; font-size: 20px; font-weight: 600;">Task Report</h1>
    </div>
    <div style="padding: 24px;">
      <div style="display: inline-block; padding: 6px 12px; border-radius: 20px; background: ${statusColor}20; color: ${statusColor}; font-weight: 600; font-size: 14px; margin-bottom: 16px;">
        ${statusIcon} ${params.status.toUpperCase()}
      </div>
      <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 140px;">Task</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">${params.title.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Task ID</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-family: monospace; font-size: 13px;">${params.taskId}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Duration</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">${durationStr}</td>
        </tr>
        ${resultSection}
        ${errorSection}
      </table>
    </div>
    ${footerHtml}
  </div>
</body>
</html>`
}

export async function sendTaskCompletionEmail(
  params: TaskCompletionEmailParams
): Promise<boolean> {
  // Use tenant config if provided, otherwise fall back to global config
  const config = params.tenantConfig || getConfig()
  
  if (!config.apiKey || !config.fromEmail) {
    console.warn('[email] Missing email configuration')
    return false
  }
  
  // Build subject
  const subject = params.status === 'completed' 
    ? `✅ Done: ${params.title}`
    : `❌ Failed: ${params.title}`
  
  // Build payload with tenant-specific from address
  const fromName = params.tenantConfig?.fromName || 'CodeTether'
  const payload = {
    personalizations: [{ to: [{ email: params.toEmail }] }],
    from: { 
      email: config.fromEmail,
      name: fromName 
    },
    subject,
    content: [{ type: 'text/html', value: buildEmailHtml(params) }],
  }
  
  try {
    const response = await fetch(SENDGRID_API_URL, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${config.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })
    
    if (response.status === 200 || response.status === 202) {
      console.log(`[email] Sent completion email to ${params.toEmail} for task ${params.taskId}`)
      return true
    } else {
      const errorText = await response.text()
      console.error(`[email] SendGrid error ${response.status}: ${errorText}`)
      return false
    }
  } catch (error) {
    console.error(`[email] Failed to send email: ${error}`)
    return false
  }
}
