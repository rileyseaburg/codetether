"""
Email Notifications for Hosted Workers

Sends task completion/failure emails via SendGrid.
Used by hosted_worker.py when tasks complete.

Configuration (environment variables):
- SENDGRID_API_KEY: SendGrid API key (required)
- SENDGRID_FROM_EMAIL: Sender email address (required)
- EMAIL_INBOUND_DOMAIN: Domain for reply-to addresses (optional)
- EMAIL_REPLY_PREFIX: Prefix for reply addresses, default "task" (optional)
"""

import html as html_module
import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# SendGrid API endpoint
SENDGRID_API_URL = 'https://api.sendgrid.com/v3/mail/send'


def _get_config() -> Dict[str, Any]:
    """Get email configuration from environment."""
    return {
        'api_key': os.environ.get('SENDGRID_API_KEY', ''),
        'from_email': os.environ.get('SENDGRID_FROM_EMAIL', ''),
        'inbound_domain': os.environ.get('EMAIL_INBOUND_DOMAIN', ''),
        'reply_prefix': os.environ.get('EMAIL_REPLY_PREFIX', 'task'),
    }


def is_configured() -> bool:
    """Check if email notifications are properly configured."""
    config = _get_config()
    return bool(config['api_key'] and config['from_email'])


def build_reply_to_address(
    session_id: str,
    codebase_id: Optional[str] = None,
) -> Optional[str]:
    """
    Build reply-to address for email continuation.

    Format: {prefix}+{session_id}@{domain}
    Or: {prefix}+{session_id}+{codebase_id}@{domain}
    """
    config = _get_config()
    if not config['inbound_domain']:
        return None

    prefix = config['reply_prefix']
    domain = config['inbound_domain']

    if codebase_id:
        return f'{prefix}+{session_id}+{codebase_id}@{domain}'
    return f'{prefix}+{session_id}@{domain}'


def _format_runtime(seconds: Optional[int]) -> str:
    """Format runtime seconds as human-readable string."""
    if not seconds:
        return 'N/A'

    minutes = seconds // 60
    remaining_seconds = seconds % 60

    if minutes > 0:
        return f'{minutes}m {remaining_seconds}s'
    return f'{seconds}s'


def _sanitize_result(result: Optional[str], max_length: int = 3000) -> str:
    """
    Sanitize and format result for HTML email.

    Handles NDJSON streaming output, extracts text content,
    escapes HTML, and truncates to max length.
    """
    if not result:
        return ''

    text_parts = []

    try:
        lines = result.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    # OpenCode streaming format
                    event_type = parsed.get('type', '')
                    part = parsed.get('part', {})

                    if event_type == 'text' and isinstance(part, dict):
                        text = part.get('text', '')
                        if text:
                            text_parts.append(text)
                    elif 'text' in parsed and isinstance(parsed['text'], str):
                        text_parts.append(parsed['text'])
                    elif 'result' in parsed:
                        text_parts.append(str(parsed['result']))
                    elif 'output' in parsed:
                        text_parts.append(str(parsed['output']))
                    elif 'message' in parsed and isinstance(
                        parsed['message'], str
                    ):
                        text_parts.append(parsed['message'])
            except json.JSONDecodeError:
                if line and not line.startswith('{'):
                    text_parts.append(line)

        if text_parts:
            display_result = ' '.join(text_parts)
        else:
            # Try parsing as single JSON
            try:
                parsed = json.loads(result)
                if isinstance(parsed, dict):
                    for key in [
                        'result',
                        'output',
                        'message',
                        'content',
                        'response',
                        'text',
                    ]:
                        if key in parsed:
                            display_result = str(parsed[key])
                            break
                    else:
                        display_result = result
                else:
                    display_result = result
            except json.JSONDecodeError:
                display_result = result
    except Exception:
        display_result = result

    # Escape HTML and truncate
    display_result = html_module.escape(display_result)
    display_result = display_result.replace('\n', '<br>')

    if len(display_result) > max_length:
        display_result = display_result[:max_length] + '...'

    return display_result


def _build_email_html(
    task_id: str,
    title: str,
    status: str,
    result: Optional[str] = None,
    error: Optional[str] = None,
    runtime_seconds: Optional[int] = None,
    session_id: Optional[str] = None,
    reply_enabled: bool = False,
    worker_name: str = 'Hosted Worker',
) -> str:
    """Build HTML email body for task completion."""
    status_color = '#22c55e' if status == 'completed' else '#ef4444'
    status_icon = '✓' if status == 'completed' else '✗'
    duration_str = _format_runtime(runtime_seconds)

    # Result section
    result_section = ''
    if result and status == 'completed':
        sanitized = _sanitize_result(result)
        if sanitized:
            result_section = f"""
            <tr>
              <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 140px; vertical-align: top;">Output</td>
              <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                <div style="font-size: 14px; line-height: 1.6; color: #1f2937;">{sanitized}</div>
              </td>
            </tr>"""

    # Error section
    error_section = ''
    if error:
        truncated = html_module.escape(
            error[:1000] + '...' if len(error) > 1000 else error
        )
        error_section = f"""
            <tr>
              <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 140px;">Error</td>
              <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
                <pre style="margin: 0; white-space: pre-wrap; word-break: break-word; font-family: monospace; font-size: 13px; background: #fef2f2; padding: 12px; border-radius: 6px; color: #dc2626;">{truncated}</pre>
              </td>
            </tr>"""

    # Footer
    if reply_enabled:
        footer_html = f"""
    <div style="background: #f9fafb; padding: 16px; text-align: center;">
      <p style="margin: 0 0 8px 0; font-size: 13px; color: #374151; font-weight: 500;">
        Reply to this email to continue the conversation
      </p>
      <p style="margin: 0; font-size: 12px; color: #6b7280;">
        Your reply will be sent to the agent to continue working on this task.
      </p>
      <p style="margin: 8px 0 0 0; font-size: 11px; color: #9ca3af;">
        Sent by CodeTether - {worker_name}
      </p>
    </div>"""
    else:
        footer_html = f"""
    <div style="background: #f9fafb; padding: 16px; text-align: center; font-size: 12px; color: #6b7280;">
      Sent by CodeTether - {worker_name}
    </div>"""

    return f"""
<!DOCTYPE html>
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
      <div style="display: inline-block; padding: 6px 12px; border-radius: 20px; background: {status_color}20; color: {status_color}; font-weight: 600; font-size: 14px; margin-bottom: 16px;">
        {status_icon} {status.upper()}
      </div>
      <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 140px;">Task</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">{html_module.escape(title)}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Task ID</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-family: monospace; font-size: 13px;">{task_id}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Duration</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">{duration_str}</td>
        </tr>
        {result_section}
        {error_section}
      </table>
    </div>
    {footer_html}
  </div>
</body>
</html>"""


async def send_task_completion_email(
    to_email: str,
    task_id: str,
    title: str,
    status: str,
    result: Optional[str] = None,
    error: Optional[str] = None,
    runtime_seconds: Optional[int] = None,
    session_id: Optional[str] = None,
    codebase_id: Optional[str] = None,
    worker_name: str = 'Hosted Worker',
) -> bool:
    """
    Send a task completion email via SendGrid.

    Args:
        to_email: Recipient email address
        task_id: ID of the completed task
        title: Task title
        status: Task status ('completed' or 'failed')
        result: Task result/output (optional)
        error: Error message if failed (optional)
        runtime_seconds: Task runtime in seconds (optional)
        session_id: Session ID for reply continuation (optional)
        codebase_id: Codebase ID for reply continuation (optional)
        worker_name: Worker name for email footer

    Returns:
        True if email sent successfully, False otherwise
    """
    config = _get_config()

    if not config['api_key'] or not config['from_email']:
        logger.warning(
            'Email not configured (missing SENDGRID_API_KEY or SENDGRID_FROM_EMAIL)'
        )
        return False

    # Build reply-to address if session_id is provided
    reply_to = None
    reply_enabled = False
    if session_id and config['inbound_domain']:
        reply_to = build_reply_to_address(session_id, codebase_id)
        reply_enabled = True

    # Build email content
    html_body = _build_email_html(
        task_id=task_id,
        title=title,
        status=status,
        result=result,
        error=error,
        runtime_seconds=runtime_seconds,
        session_id=session_id,
        reply_enabled=reply_enabled,
        worker_name=worker_name,
    )

    subject = f'[CodeTether] Task {status}: {title}'

    # Build SendGrid payload
    payload = {
        'personalizations': [{'to': [{'email': to_email}]}],
        'from': {'email': config['from_email']},
        'subject': subject,
        'content': [{'type': 'text/html', 'value': html_body}],
    }

    if reply_to:
        payload['reply_to'] = {'email': reply_to}

    # Send via SendGrid
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                SENDGRID_API_URL,
                json=payload,
                headers={
                    'Authorization': f'Bearer {config["api_key"]}',
                    'Content-Type': 'application/json',
                },
            )

            if response.status_code in (200, 202):
                logger.info(f'Email sent to {to_email} for task {task_id}')
                return True
            else:
                logger.error(
                    f'SendGrid error {response.status_code}: {response.text}'
                )
                return False

    except Exception as e:
        logger.error(f'Failed to send email: {e}')
        return False


async def send_task_question_email(
    to_email: str,
    task_id: str,
    title: str,
    question: str,
    session_id: str,
    codebase_id: Optional[str] = None,
    worker_name: str = 'Hosted Worker',
) -> bool:
    """
    Send a "needs input" email when task requires user response.

    Args:
        to_email: Recipient email address
        task_id: ID of the task needing input
        title: Task title
        question: The question/input needed from user
        session_id: Session ID for reply (required for question emails)
        codebase_id: Codebase ID for reply continuation
        worker_name: Worker name for email footer

    Returns:
        True if email sent successfully, False otherwise
    """
    config = _get_config()

    if not config['api_key'] or not config['from_email']:
        logger.warning('Email not configured')
        return False

    if not config['inbound_domain']:
        logger.warning(
            'Cannot send question email without EMAIL_INBOUND_DOMAIN configured'
        )
        return False

    reply_to = build_reply_to_address(session_id, codebase_id)

    # Build question email HTML
    question_escaped = html_module.escape(question).replace('\n', '<br>')

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 20px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
  <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <div style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); padding: 24px; text-align: center;">
      <h1 style="margin: 0; color: white; font-size: 20px; font-weight: 600;">Input Needed</h1>
    </div>
    <div style="padding: 24px;">
      <div style="display: inline-block; padding: 6px 12px; border-radius: 20px; background: #fef3c720; color: #d97706; font-weight: 600; font-size: 14px; margin-bottom: 16px;">
        ⏳ WAITING FOR INPUT
      </div>
      <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 140px;">Task</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">{html_module.escape(title)}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; vertical-align: top;">Question</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
            <div style="background: #fffbeb; padding: 16px; border-radius: 8px; border-left: 4px solid #f59e0b;">
              <p style="margin: 0; font-size: 15px; line-height: 1.6; color: #1f2937;">{question_escaped}</p>
            </div>
          </td>
        </tr>
      </table>
    </div>
    <div style="background: #f9fafb; padding: 16px; text-align: center;">
      <p style="margin: 0 0 8px 0; font-size: 14px; color: #374151; font-weight: 600;">
        Reply to this email with your answer
      </p>
      <p style="margin: 0; font-size: 12px; color: #6b7280;">
        Your response will be sent to the agent to continue the task.
      </p>
      <p style="margin: 8px 0 0 0; font-size: 11px; color: #9ca3af;">
        Sent by CodeTether - {worker_name}
      </p>
    </div>
  </div>
</body>
</html>"""

    subject = f'[CodeTether] Input needed: {title}'

    payload = {
        'personalizations': [{'to': [{'email': to_email}]}],
        'from': {'email': config['from_email']},
        'reply_to': {'email': reply_to},
        'subject': subject,
        'content': [{'type': 'text/html', 'value': html_body}],
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                SENDGRID_API_URL,
                json=payload,
                headers={
                    'Authorization': f'Bearer {config["api_key"]}',
                    'Content-Type': 'application/json',
                },
            )

            if response.status_code in (200, 202):
                logger.info(
                    f'Question email sent to {to_email} for task {task_id}'
                )
                return True
            else:
                logger.error(
                    f'SendGrid error {response.status_code}: {response.text}'
                )
                return False

    except Exception as e:
        logger.error(f'Failed to send question email: {e}')
        return False
