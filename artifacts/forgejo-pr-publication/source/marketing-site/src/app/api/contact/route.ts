import { NextRequest, NextResponse } from 'next/server'

interface ContactFormData {
  name: string
  email: string
  company?: string
  useCase?: string
  message?: string
}

export async function POST(request: NextRequest) {
  try {
    const data: ContactFormData = await request.json()

    // Validate required fields
    if (!data.name || !data.email) {
      return NextResponse.json(
        { error: 'Name and email are required' },
        { status: 400 }
      )
    }

    // Get SendGrid API key from environment
    const sendgridApiKey = process.env.SENDGRID_API_KEY
    const notificationEmail = process.env.CONTACT_NOTIFICATION_EMAIL || 'riley@spotlessbinco.com'
    const fromEmail = process.env.SENDGRID_FROM_EMAIL || 'noreply@codetether.run'

    if (!sendgridApiKey) {
      console.error('SENDGRID_API_KEY not configured')
      return NextResponse.json(
        { error: 'Email service not configured' },
        { status: 500 }
      )
    }

    // Build email content
    const useCaseLabels: Record<string, string> = {
      coding: 'AI Coding Assistants',
      support: 'Customer Support Automation',
      data: 'Data Pipeline Orchestration',
      research: 'Research & Analysis',
      devops: 'DevOps Automation',
      content: 'Content Generation',
      other: 'Other',
    }

    const useCaseLabel = data.useCase ? useCaseLabels[data.useCase] || data.useCase : 'Not specified'

    const htmlContent = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f3f4f6;">
  <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <div style="background: linear-gradient(135deg, #0891b2 0%, #06b6d4 100%); padding: 24px; text-align: center;">
      <h1 style="margin: 0; color: white; font-size: 20px; font-weight: 600;">New Demo Request</h1>
    </div>
    <div style="padding: 24px;">
      <table style="width: 100%; border-collapse: collapse;">
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 120px;">Name</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">${data.name}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Email</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
            <a href="mailto:${data.email}" style="color: #0891b2;">${data.email}</a>
          </td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Company</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">${data.company || 'Not provided'}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Use Case</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">${useCaseLabel}</td>
        </tr>
        ${data.message ? `
        <tr>
          <td style="padding: 12px; font-weight: 600; color: #374151; vertical-align: top;">Message</td>
          <td style="padding: 12px;">
            <div style="background: #f9fafb; padding: 12px; border-radius: 6px; white-space: pre-wrap;">${data.message}</div>
          </td>
        </tr>
        ` : ''}
      </table>
    </div>
    <div style="background: #f9fafb; padding: 16px; text-align: center; font-size: 12px; color: #6b7280;">
      Submitted via codetether.run contact form
    </div>
  </div>
</body>
</html>`

    // Send notification email to team
    const sendgridResponse = await fetch('https://api.sendgrid.com/v3/mail/send', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${sendgridApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        personalizations: [
          {
            to: [{ email: notificationEmail }],
          },
        ],
        from: { email: fromEmail, name: 'CodeTether' },
        reply_to: { email: data.email, name: data.name },
        subject: `[CodeTether Demo] ${data.name} from ${data.company || 'Unknown Company'}`,
        content: [{ type: 'text/html', value: htmlContent }],
      }),
    })

    if (!sendgridResponse.ok) {
      const errorText = await sendgridResponse.text()
      console.error('SendGrid error:', sendgridResponse.status, errorText)
      return NextResponse.json(
        { error: 'Failed to send notification' },
        { status: 500 }
      )
    }

    // Send confirmation email to the submitter
    const confirmationHtml = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f3f4f6;">
  <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <div style="background: linear-gradient(135deg, #0891b2 0%, #06b6d4 100%); padding: 24px; text-align: center;">
      <h1 style="margin: 0; color: white; font-size: 20px; font-weight: 600;">Thanks for reaching out!</h1>
    </div>
    <div style="padding: 24px;">
      <p style="margin: 0 0 16px; color: #374151; font-size: 16px;">
        Hi ${data.name},
      </p>
      <p style="margin: 0 0 16px; color: #374151; font-size: 16px;">
        Thanks for your interest in CodeTether! We've received your demo request and will be in touch within 24 hours.
      </p>
      <p style="margin: 0 0 16px; color: #374151; font-size: 16px;">
        In the meantime, feel free to:
      </p>
      <ul style="margin: 0 0 16px; padding-left: 24px; color: #374151;">
        <li style="margin-bottom: 8px;">Check out our <a href="https://docs.codetether.run" style="color: #0891b2;">documentation</a></li>
        <li style="margin-bottom: 8px;">Try the <a href="https://docs.codetether.run/getting-started/quickstart/" style="color: #0891b2;">quick start guide</a></li>
        <li style="margin-bottom: 8px;">Explore the <a href="https://github.com/rileyseaburg/codetether" style="color: #0891b2;">GitHub repository</a></li>
      </ul>
      <p style="margin: 0; color: #374151; font-size: 16px;">
        Best,<br>
        The CodeTether Team
      </p>
    </div>
    <div style="background: #f9fafb; padding: 16px; text-align: center; font-size: 12px; color: #6b7280;">
      <a href="https://codetether.run" style="color: #0891b2;">codetether.run</a> |
      <a href="https://docs.codetether.run" style="color: #0891b2;">docs</a> |
      <a href="https://github.com/rileyseaburg/codetether" style="color: #0891b2;">github</a>
    </div>
  </div>
</body>
</html>`

    await fetch('https://api.sendgrid.com/v3/mail/send', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${sendgridApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        personalizations: [
          {
            to: [{ email: data.email }],
          },
        ],
        from: { email: fromEmail, name: 'CodeTether' },
        subject: 'Thanks for contacting CodeTether!',
        content: [{ type: 'text/html', value: confirmationHtml }],
      }),
    })

    console.log('Contact form submitted:', {
      name: data.name,
      email: data.email,
      company: data.company,
      useCase: data.useCase,
    })

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Contact form error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
