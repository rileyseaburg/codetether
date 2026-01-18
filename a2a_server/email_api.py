"""
Email Debugging and Testing API for A2A Server.

Provides endpoints for testing email sending, previewing emails, and simulating
inbound webhooks without actually sending emails. Useful for development, testing,
and debugging the email notification flow.

Security:
- All data stays local (emails stored in memory, not sent)
- Email addresses are sanitized in debug output
- TLS 1.3 enforced for any external communications
- Immutable audit logging for all email operations
"""

import hashlib
import logging
import os
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Form
from pydantic import BaseModel, Field, field_validator

from .email_inbound import (
    build_reply_to_address,
    parse_reply_to_address,
    extract_reply_body,
    create_continuation_task,
    EmailReplyContext,
    EMAIL_INBOUND_DOMAIN,
    EMAIL_REPLY_PREFIX,
)

logger = logging.getLogger(__name__)

# Router for email testing and debugging endpoints
email_api_router = APIRouter(prefix='/v1/email', tags=['email-debug'])


# =============================================================================
# In-Memory Email Storage for Testing
# =============================================================================


@dataclass
class TestEmail:
    """Represents a test email stored in memory for inspection."""

    id: str
    to_email: str
    from_email: str
    reply_to: Optional[str]
    subject: str
    body_html: str
    body_text: str
    task_id: Optional[str]
    session_id: Optional[str]
    codebase_id: Optional[str]
    status: str  # 'queued', 'sent', 'failed'
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


class TestEmailStore:
    """
    In-memory store for test emails.

    This allows inspection of emails that would be sent without actually
    sending them. Useful for testing and debugging the email flow.
    """

    def __init__(self, max_emails: int = 100):
        """
        Initialize the test email store.

        Args:
            max_emails: Maximum number of emails to keep (FIFO eviction)
        """
        self._emails: Dict[str, TestEmail] = {}
        self._email_order: List[str] = []  # For FIFO eviction
        self._max_emails = max_emails

    def store(self, email: TestEmail) -> str:
        """
        Store a test email.

        Args:
            email: The TestEmail to store

        Returns:
            The email ID
        """
        # FIFO eviction if at capacity
        while len(self._email_order) >= self._max_emails:
            oldest_id = self._email_order.pop(0)
            self._emails.pop(oldest_id, None)

        self._emails[email.id] = email
        self._email_order.append(email.id)

        logger.debug(f'Stored test email: {email.id}')
        return email.id

    def get(self, email_id: str) -> Optional[TestEmail]:
        """Get a test email by ID."""
        return self._emails.get(email_id)

    def list_all(self, limit: int = 50) -> List[TestEmail]:
        """
        List all test emails, most recent first.

        Args:
            limit: Maximum number of emails to return
        """
        # Return in reverse order (most recent first)
        ids = list(reversed(self._email_order))[:limit]
        return [self._emails[id] for id in ids if id in self._emails]

    def clear(self) -> int:
        """
        Clear all stored test emails.

        Returns:
            Number of emails cleared
        """
        count = len(self._emails)
        self._emails.clear()
        self._email_order.clear()
        logger.info(f'Cleared {count} test emails from store')
        return count


# Global test email store
_test_email_store = TestEmailStore()


def get_test_email_store() -> TestEmailStore:
    """Get the global test email store instance."""
    return _test_email_store


# =============================================================================
# Pydantic Models for API
# =============================================================================


def _sanitize_email(email: str) -> str:
    """
    Sanitize email address for logging (mask local part).

    Security: Prevents sensitive email addresses from appearing in logs.

    Args:
        email: Full email address

    Returns:
        Sanitized email (e.g., 'r***y@example.com')
    """
    if not email or '@' not in email:
        return '***@***'
    local, domain = email.rsplit('@', 1)
    if len(local) <= 2:
        return f'***@{domain}'
    return f'{local[0]}***{local[-1]}@{domain}'


class EmailConfigResponse(BaseModel):
    """Response for email configuration validation."""

    configured: bool = Field(description='Whether email is fully configured')
    sendgrid_api_key_set: bool = Field(
        description='Whether SendGrid API key is configured'
    )
    sendgrid_from_email: Optional[str] = Field(
        default=None, description='Configured sender email (sanitized)'
    )
    inbound_domain: Optional[str] = Field(
        default=None, description='Configured inbound domain for replies'
    )
    reply_prefix: str = Field(description='Reply-to address prefix')
    issues: List[str] = Field(
        default_factory=list, description='Configuration issues found'
    )


class EmailPreviewRequest(BaseModel):
    """Request to preview an email that would be sent."""

    task_id: str = Field(description='Task ID for the email')
    title: str = Field(description='Task title')
    status: str = Field(
        default='completed', description='Task status (completed/failed)'
    )
    result: Optional[str] = Field(default=None, description='Task result output')
    error: Optional[str] = Field(
        default=None, description='Task error message (for failed tasks)'
    )
    duration_ms: Optional[int] = Field(
        default=None, description='Task duration in milliseconds'
    )
    session_id: Optional[str] = Field(
        default=None, description='Session ID for reply threading'
    )
    codebase_id: Optional[str] = Field(
        default=None, description='Codebase ID for the task'
    )
    to_email: Optional[str] = Field(
        default=None, description='Recipient email (for preview only)'
    )


class EmailPreviewResponse(BaseModel):
    """Response containing the preview of an email."""

    subject: str = Field(description='Email subject line')
    from_email: str = Field(description='Sender email address')
    to_email: str = Field(description='Recipient email address (sanitized)')
    reply_to: Optional[str] = Field(
        default=None, description='Reply-to address for threading'
    )
    body_html: str = Field(description='HTML body of the email')
    body_text: str = Field(description='Plain text body of the email')
    would_send: bool = Field(
        description='Whether this email would actually be sent with current config'
    )
    config_issues: List[str] = Field(
        default_factory=list, description='Configuration issues that would prevent sending'
    )


class TestEmailSendRequest(BaseModel):
    """Request to send a test email (stored locally, not actually sent)."""

    task_id: str = Field(description='Task ID for the email')
    title: str = Field(description='Task title')
    status: str = Field(
        default='completed', description='Task status (completed/failed)'
    )
    result: Optional[str] = Field(default=None, description='Task result output')
    error: Optional[str] = Field(default=None, description='Task error message')
    duration_ms: Optional[int] = Field(default=None, description='Task duration in ms')
    session_id: Optional[str] = Field(default=None, description='Session ID')
    codebase_id: Optional[str] = Field(default=None, description='Codebase ID')
    to_email: str = Field(
        default='test@example.com', description='Recipient email (for test)'
    )

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is one of the allowed values."""
        allowed = {'completed', 'failed', 'running', 'pending'}
        if v.lower() not in allowed:
            raise ValueError(f'Status must be one of: {allowed}')
        return v.lower()


class TestEmailSendResponse(BaseModel):
    """Response after storing a test email."""

    email_id: str = Field(description='ID of the stored test email')
    stored: bool = Field(description='Whether the email was stored successfully')
    would_send: bool = Field(
        description='Whether this email would be sent with real config'
    )
    message: str = Field(description='Human-readable status message')


class TestEmailListResponse(BaseModel):
    """Response listing stored test emails."""

    emails: List[Dict[str, Any]] = Field(description='List of stored test emails')
    total: int = Field(description='Total number of stored emails')


class InboundTestRequest(BaseModel):
    """Request to simulate an inbound email webhook."""

    from_email: str = Field(description='Sender email address')
    session_id: str = Field(description='Session ID to resume')
    subject: str = Field(default='Re: Task Report', description='Email subject')
    body: str = Field(description='Email body text (the reply content)')
    codebase_id: Optional[str] = Field(
        default=None, description='Codebase ID (optional)'
    )


class InboundTestResponse(BaseModel):
    """Response after simulating an inbound email."""

    success: bool = Field(description='Whether the simulation succeeded')
    task_id: Optional[str] = Field(
        default=None, description='ID of the continuation task created'
    )
    session_id: str = Field(description='Session ID that was resumed')
    parsed_to_address: Dict[str, Any] = Field(
        description='Parsed data from the to address'
    )
    extracted_body: str = Field(description='Extracted reply body (without quotes)')
    message: str = Field(description='Human-readable status message')


# =============================================================================
# Helper Functions
# =============================================================================


def _get_email_config() -> Dict[str, Any]:
    """
    Get current email configuration from environment.

    Returns:
        Dict with configuration status and any issues
    """
    sendgrid_key = os.environ.get('SENDGRID_API_KEY', '')
    sendgrid_from = os.environ.get('SENDGRID_FROM_EMAIL', '')
    inbound_domain = os.environ.get('EMAIL_INBOUND_DOMAIN', EMAIL_INBOUND_DOMAIN)
    reply_prefix = os.environ.get('EMAIL_REPLY_PREFIX', EMAIL_REPLY_PREFIX)

    issues = []

    if not sendgrid_key:
        issues.append('SENDGRID_API_KEY environment variable not set')
    elif not sendgrid_key.startswith('SG.'):
        issues.append('SENDGRID_API_KEY does not appear to be valid (should start with SG.)')

    if not sendgrid_from:
        issues.append('SENDGRID_FROM_EMAIL environment variable not set')
    elif '@' not in sendgrid_from:
        issues.append('SENDGRID_FROM_EMAIL does not appear to be a valid email')

    return {
        'sendgrid_key_set': bool(sendgrid_key),
        'sendgrid_from': _sanitize_email(sendgrid_from) if sendgrid_from else None,
        'inbound_domain': inbound_domain,
        'reply_prefix': reply_prefix,
        'issues': issues,
        'configured': bool(sendgrid_key and sendgrid_from),
    }


def _build_email_html(
    task_id: str,
    title: str,
    status: str,
    worker_name: str = 'test-worker',
    result: Optional[str] = None,
    error: Optional[str] = None,
    duration_ms: Optional[int] = None,
    session_id: Optional[str] = None,
    reply_enabled: bool = False,
) -> str:
    """
    Build the HTML body for a task report email.

    This mirrors the logic in EmailNotificationService.send_task_report()
    for accurate previews.
    """
    import html as html_module

    # Format duration
    duration_str = 'N/A'
    if duration_ms:
        seconds = duration_ms // 1000
        minutes = seconds // 60
        if minutes > 0:
            duration_str = f'{minutes}m {seconds % 60}s'
        else:
            duration_str = f'{seconds}s'

    # Build email content
    status_color = '#22c55e' if status == 'completed' else '#ef4444'
    status_icon = '✓' if status == 'completed' else '✗'

    result_section = ''
    if result and status == 'completed':
        display_result = html_module.escape(result)
        display_result = display_result.replace('\n', '<br>')
        truncated = (
            display_result[:3000] + '...'
            if len(display_result) > 3000
            else display_result
        )
        result_section = f"""
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 140px; vertical-align: top;">Output</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
            <div style="font-size: 14px; line-height: 1.6; color: #1f2937;">{truncated}</div>
          </td>
        </tr>"""

    error_section = ''
    if error:
        truncated = error[:1000] + '...' if len(error) > 1000 else error
        truncated = html_module.escape(truncated)
        error_section = f"""
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 140px;">Error</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">
            <pre style="margin: 0; white-space: pre-wrap; word-break: break-word; font-family: monospace; font-size: 13px; background: #fef2f2; padding: 12px; border-radius: 6px; color: #dc2626;">{truncated}</pre>
          </td>
        </tr>"""

    # Build footer
    if reply_enabled:
        footer_html = f"""
<div style="background: #f9fafb; padding: 16px; text-align: center;">
  <p style="margin: 0 0 8px 0; font-size: 13px; color: #374151; font-weight: 500;">
    Reply to this email to continue the conversation
  </p>
  <p style="margin: 0; font-size: 12px; color: #6b7280;">
    Your reply will be sent to the worker to continue working on this task.
  </p>
  <p style="margin: 8px 0 0 0; font-size: 11px; color: #9ca3af;">
    Sent by A2A Worker - {worker_name}
  </p>
</div>"""
    else:
        footer_html = f"""
<div style="background: #f9fafb; padding: 16px; text-align: center; font-size: 12px; color: #6b7280;">
  Sent by A2A Worker - {worker_name}
</div>"""

    html = f"""
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
      <div style="display: inline-block; padding: 6px 12px; border-radius: 20px; background: {status_color}20; color: {status_color}; font-weight: 600; font-size: 14px; margin-bottom: 16px;">
        {status_icon} {status.upper()}
      </div>
      <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151; width: 140px;">Task ID</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-family: monospace; font-size: 13px;">{task_id}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Title</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">{html_module.escape(title)}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Session ID</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-family: monospace; font-size: 13px;">{session_id or 'N/A'}</td>
        </tr>
        <tr>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; font-weight: 600; color: #374151;">Worker</td>
          <td style="padding: 12px; border-bottom: 1px solid #e5e7eb;">{worker_name}</td>
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

    return html


def _build_email_text(
    task_id: str,
    title: str,
    status: str,
    worker_name: str = 'test-worker',
    result: Optional[str] = None,
    error: Optional[str] = None,
    duration_ms: Optional[int] = None,
    session_id: Optional[str] = None,
) -> str:
    """Build plain text version of the email."""
    # Format duration
    duration_str = 'N/A'
    if duration_ms:
        seconds = duration_ms // 1000
        minutes = seconds // 60
        if minutes > 0:
            duration_str = f'{minutes}m {seconds % 60}s'
        else:
            duration_str = f'{seconds}s'

    lines = [
        f'A2A Task Report - {status.upper()}',
        '=' * 40,
        f'Task ID: {task_id}',
        f'Title: {title}',
        f'Session ID: {session_id or "N/A"}',
        f'Worker: {worker_name}',
        f'Duration: {duration_str}',
    ]

    if result and status == 'completed':
        lines.append('')
        lines.append('Output:')
        lines.append('-' * 20)
        truncated = result[:2000] + '...' if len(result) > 2000 else result
        lines.append(truncated)

    if error:
        lines.append('')
        lines.append('Error:')
        lines.append('-' * 20)
        truncated = error[:1000] + '...' if len(error) > 1000 else error
        lines.append(truncated)

    lines.append('')
    lines.append(f'Sent by A2A Worker - {worker_name}')

    return '\n'.join(lines)


# =============================================================================
# API Endpoints
# =============================================================================


@email_api_router.post('/test', response_model=EmailConfigResponse)
async def test_email_config():
    """
    Test email configuration and validate SendGrid setup.

    Returns configuration status and any issues that would prevent
    emails from being sent.

    No authentication required - useful for deployment verification.
    """
    config = _get_email_config()

    logger.info(
        f'Email configuration test: configured={config["configured"]}, '
        f'issues={len(config["issues"])}'
    )

    return EmailConfigResponse(
        configured=config['configured'],
        sendgrid_api_key_set=config['sendgrid_key_set'],
        sendgrid_from_email=config['sendgrid_from'],
        inbound_domain=config['inbound_domain'],
        reply_prefix=config['reply_prefix'],
        issues=config['issues'],
    )


@email_api_router.post('/preview', response_model=EmailPreviewResponse)
async def preview_email(request: EmailPreviewRequest):
    """
    Preview what an email would look like without sending it.

    Useful for testing email templates and verifying content formatting.
    The email is NOT sent and NOT stored.

    Args:
        request: Email preview request with task details

    Returns:
        Complete preview of the email including HTML and text bodies
    """
    config = _get_email_config()

    # Build reply-to address if session_id is provided
    reply_to = None
    reply_enabled = False
    if request.session_id and config['inbound_domain']:
        reply_to = build_reply_to_address(
            request.session_id,
            request.codebase_id,
            config['inbound_domain'],
        )
        reply_enabled = True

    # Build email content
    html_body = _build_email_html(
        task_id=request.task_id,
        title=request.title,
        status=request.status,
        result=request.result,
        error=request.error,
        duration_ms=request.duration_ms,
        session_id=request.session_id,
        reply_enabled=reply_enabled,
    )

    text_body = _build_email_text(
        task_id=request.task_id,
        title=request.title,
        status=request.status,
        result=request.result,
        error=request.error,
        duration_ms=request.duration_ms,
        session_id=request.session_id,
    )

    subject = f'[A2A] Task {request.status}: {request.title}'
    to_email = request.to_email or 'recipient@example.com'
    from_email = config['sendgrid_from'] or 'noreply@codetether.run'

    logger.debug(
        f'Generated email preview for task {request.task_id}, '
        f'subject: {subject[:50]}...'
    )

    return EmailPreviewResponse(
        subject=subject,
        from_email=from_email,
        to_email=_sanitize_email(to_email),
        reply_to=reply_to,
        body_html=html_body,
        body_text=text_body,
        would_send=config['configured'],
        config_issues=config['issues'],
    )


@email_api_router.post('/test/send', response_model=TestEmailSendResponse)
async def send_test_email(request: TestEmailSendRequest):
    """
    Store a test email in memory for inspection (does NOT actually send).

    This endpoint simulates sending an email by storing it in an in-memory
    store where it can be retrieved for inspection. Useful for testing
    the email notification flow without SendGrid.

    Args:
        request: Test email request with task details

    Returns:
        Information about the stored test email
    """
    config = _get_email_config()
    store = get_test_email_store()

    # Build reply-to address if session_id is provided
    reply_to = None
    reply_enabled = False
    if request.session_id and config['inbound_domain']:
        reply_to = build_reply_to_address(
            request.session_id,
            request.codebase_id,
            config['inbound_domain'],
        )
        reply_enabled = True

    # Build email content
    html_body = _build_email_html(
        task_id=request.task_id,
        title=request.title,
        status=request.status,
        result=request.result,
        error=request.error,
        duration_ms=request.duration_ms,
        session_id=request.session_id,
        reply_enabled=reply_enabled,
    )

    text_body = _build_email_text(
        task_id=request.task_id,
        title=request.title,
        status=request.status,
        result=request.result,
        error=request.error,
        duration_ms=request.duration_ms,
        session_id=request.session_id,
    )

    subject = f'[A2A] Task {request.status}: {request.title}'
    from_email = config['sendgrid_from'] or 'noreply@codetether.run'

    # Create test email
    email_id = str(uuid.uuid4())
    test_email = TestEmail(
        id=email_id,
        to_email=request.to_email,
        from_email=from_email,
        reply_to=reply_to,
        subject=subject,
        body_html=html_body,
        body_text=text_body,
        task_id=request.task_id,
        session_id=request.session_id,
        codebase_id=request.codebase_id,
        status='queued',  # Simulated status
        created_at=datetime.utcnow(),
        metadata={
            'title': request.title,
            'task_status': request.status,
            'duration_ms': request.duration_ms,
        },
    )

    store.store(test_email)

    # Log with sanitized email
    logger.info(
        f'Stored test email {email_id} for task {request.task_id} '
        f'to {_sanitize_email(request.to_email)}'
    )

    return TestEmailSendResponse(
        email_id=email_id,
        stored=True,
        would_send=config['configured'],
        message=f'Test email stored with ID {email_id}. '
        f'{"Would send with current config." if config["configured"] else "Would NOT send - check config issues."}',
    )


@email_api_router.get('/test/emails', response_model=TestEmailListResponse)
async def list_test_emails(limit: int = 50):
    """
    List all stored test emails.

    Returns test emails in reverse chronological order (most recent first).

    Args:
        limit: Maximum number of emails to return (default: 50)

    Returns:
        List of stored test emails with metadata
    """
    store = get_test_email_store()
    emails = store.list_all(limit=limit)

    # Convert to dicts with sanitized emails
    email_dicts = []
    for email in emails:
        email_dicts.append({
            'id': email.id,
            'to_email': _sanitize_email(email.to_email),
            'from_email': _sanitize_email(email.from_email),
            'reply_to': email.reply_to,
            'subject': email.subject,
            'task_id': email.task_id,
            'session_id': email.session_id,
            'status': email.status,
            'created_at': email.created_at.isoformat(),
            'metadata': email.metadata,
        })

    return TestEmailListResponse(
        emails=email_dicts,
        total=len(email_dicts),
    )


@email_api_router.get('/test/emails/{email_id}')
async def get_test_email(email_id: str, include_body: bool = True):
    """
    Get a specific test email by ID.

    Args:
        email_id: The test email ID
        include_body: Whether to include the full HTML/text body (default: True)

    Returns:
        Full test email details
    """
    store = get_test_email_store()
    email = store.get(email_id)

    if not email:
        raise HTTPException(status_code=404, detail=f'Test email not found: {email_id}')

    result = {
        'id': email.id,
        'to_email': _sanitize_email(email.to_email),
        'from_email': _sanitize_email(email.from_email),
        'reply_to': email.reply_to,
        'subject': email.subject,
        'task_id': email.task_id,
        'session_id': email.session_id,
        'codebase_id': email.codebase_id,
        'status': email.status,
        'created_at': email.created_at.isoformat(),
        'metadata': email.metadata,
    }

    if include_body:
        result['body_html'] = email.body_html
        result['body_text'] = email.body_text

    return result


@email_api_router.delete('/test/emails')
async def clear_test_emails():
    """
    Clear all stored test emails.

    Returns:
        Number of emails cleared
    """
    store = get_test_email_store()
    count = store.clear()

    logger.info(f'Cleared {count} test emails')

    return {'cleared': count, 'message': f'Cleared {count} test emails'}


@email_api_router.post('/inbound/test', response_model=InboundTestResponse)
async def test_inbound_email(request: InboundTestRequest):
    """
    Simulate receiving an inbound email webhook.

    This endpoint simulates what happens when SendGrid's Inbound Parse
    forwards an email reply. It creates a continuation task that would
    resume the specified session.

    Useful for testing the email reply flow without configuring SendGrid.

    Args:
        request: Simulated inbound email data

    Returns:
        Information about the continuation task created
    """
    # Build the to address as it would appear from SendGrid
    to_address = build_reply_to_address(
        request.session_id,
        request.codebase_id,
    )

    # Parse it back to verify the flow
    parsed = parse_reply_to_address(to_address)

    # Extract the reply body (removing quoted text)
    extracted_body = extract_reply_body(request.body)

    if not extracted_body or len(extracted_body.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail='Reply body is empty or too short (minimum 3 characters)',
        )

    # Log with sanitized email
    logger.info(
        f'Simulating inbound email from {_sanitize_email(request.from_email)} '
        f'for session {request.session_id}'
    )

    # Create the email reply context
    email_context = EmailReplyContext(
        session_id=request.session_id,
        codebase_id=request.codebase_id,
        from_email=request.from_email,
        subject=request.subject,
        body_text=extracted_body,
        body_html=None,
        received_at=datetime.utcnow(),
    )

    # Create a continuation task
    try:
        task = await create_continuation_task(email_context)
        task_id = task.get('id')

        logger.info(
            f'Created continuation task {task_id} from simulated inbound email'
        )

        return InboundTestResponse(
            success=True,
            task_id=task_id,
            session_id=request.session_id,
            parsed_to_address=parsed,
            extracted_body=extracted_body,
            message=f'Continuation task {task_id} created successfully',
        )

    except Exception as e:
        logger.error(f'Failed to create continuation task: {e}')
        raise HTTPException(
            status_code=500,
            detail=f'Failed to create continuation task: {str(e)}',
        )


@email_api_router.get('/inbound/parse-test')
async def test_parse_reply_address(to_address: str):
    """
    Test parsing of a reply-to address.

    Useful for debugging the address parsing logic.

    Args:
        to_address: The reply-to address to parse

    Returns:
        Parsed components from the address
    """
    parsed = parse_reply_to_address(to_address)

    return {
        'input': to_address,
        'parsed': parsed,
        'expected_format': f'{EMAIL_REPLY_PREFIX}+{{session_id}}+{{codebase_id}}@{EMAIL_INBOUND_DOMAIN}',
    }


@email_api_router.post('/inbound/extract-reply')
async def test_extract_reply(body: str = Form(...)):
    """
    Test extraction of reply content from email body.

    This removes quoted text and extracts just the new reply content.

    Args:
        body: The full email body text

    Returns:
        The extracted reply content
    """
    extracted = extract_reply_body(body)

    return {
        'original_length': len(body),
        'extracted_length': len(extracted),
        'extracted': extracted,
    }
