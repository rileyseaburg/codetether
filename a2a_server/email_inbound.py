"""
Email Inbound Webhook Handler for A2A Server.

Handles SendGrid Inbound Parse webhooks to enable email reply-based task continuation.
When a worker sends an email notification (e.g., asking a question or reporting completion),
users can reply directly to that email and have their response continue the worker's task.

Flow:
1. Worker sends email with reply-to: task+{session_id}@{inbound_domain}
2. User replies to email
3. SendGrid Inbound Parse forwards to POST /v1/email/inbound
4. This module extracts session_id from "to" address, parses reply text
5. Creates a new task with same session_id to continue the conversation
"""

import logging
import os
import re
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, Request, HTTPException, Form, UploadFile, File
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Router for email inbound endpoints
email_router = APIRouter(prefix='/v1/email', tags=['email'])

# Environment configuration
EMAIL_INBOUND_DOMAIN = os.environ.get(
    'EMAIL_INBOUND_DOMAIN', 'inbound.codetether.run'
)
EMAIL_REPLY_PREFIX = os.environ.get('EMAIL_REPLY_PREFIX', 'task')


class EmailReplyContext(BaseModel):
    """Parsed context from an inbound email reply."""

    session_id: Optional[str] = None
    task_id: Optional[str] = None
    codebase_id: Optional[str] = None
    from_email: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    received_at: datetime


def parse_reply_to_address(to_address: str) -> Dict[str, Optional[str]]:
    """
    Parse the reply-to address to extract session/task context.

    Expected formats:
    - task+{session_id}@inbound.codetether.run
    - task+{session_id}+{codebase_id}@inbound.codetether.run

    Returns dict with session_id, task_id, codebase_id (any may be None).
    """
    result: Dict[str, Optional[str]] = {
        'session_id': None,
        'task_id': None,
        'codebase_id': None,
    }

    # Extract local part before @
    match = re.match(r'^([^@]+)@', to_address.lower().strip())
    if not match:
        return result

    local_part = match.group(1)

    # Check if it starts with our prefix
    prefix = EMAIL_REPLY_PREFIX.lower()
    if not local_part.startswith(f'{prefix}+'):
        logger.debug(
            f'Email to address does not match expected prefix: {to_address}'
        )
        return result

    # Extract the parts after the prefix
    parts_str = local_part[len(prefix) + 1 :]  # +1 for the '+'
    parts = parts_str.split('+')

    if len(parts) >= 1 and parts[0]:
        result['session_id'] = parts[0]
    if len(parts) >= 2 and parts[1]:
        result['codebase_id'] = parts[1]

    return result


def extract_reply_body(text: str, html: Optional[str] = None) -> str:
    """
    Extract the actual reply content from an email, removing quoted text.

    Email clients typically include the original message when replying.
    This function attempts to extract just the new reply content.
    """
    if not text:
        return ''

    lines = text.split('\n')
    reply_lines = []

    # Common reply markers
    reply_markers = [
        'On ',  # "On Mon, Jan 11, 2026 at..."
        '-----Original Message-----',
        '________________________________',
        'From:',
        '> ',  # Quoted text
        'wrote:',
    ]

    for line in lines:
        stripped = line.strip()

        # Check if this line starts a quote section
        is_quote_start = False
        for marker in reply_markers:
            if stripped.startswith(marker):
                is_quote_start = True
                break

        # Also check for "On ... wrote:" pattern spanning multiple words
        if re.match(r'^On .+ wrote:$', stripped):
            is_quote_start = True

        if is_quote_start:
            # Stop processing - everything after is quoted
            break

        reply_lines.append(line)

    # Clean up the result
    result = '\n'.join(reply_lines).strip()

    # If we got nothing useful, fall back to the original
    if not result or len(result) < 10:
        result = text.strip()

    return result


def build_reply_to_address(
    session_id: str,
    codebase_id: Optional[str] = None,
    domain: Optional[str] = None,
) -> str:
    """
    Build the reply-to address for outbound emails.

    Format: task+{session_id}@{domain}
    Or: task+{session_id}+{codebase_id}@{domain}
    """
    domain = domain or EMAIL_INBOUND_DOMAIN
    prefix = EMAIL_REPLY_PREFIX

    if codebase_id:
        return f'{prefix}+{session_id}+{codebase_id}@{domain}'
    return f'{prefix}+{session_id}@{domain}'


@email_router.post('/inbound')
async def handle_inbound_email(
    request: Request,
    # SendGrid Inbound Parse sends multipart/form-data
    # See: https://docs.sendgrid.com/for-developers/parsing-email/setting-up-the-inbound-parse-webhook
    to: str = Form(default=''),
    from_: str = Form(default='', alias='from'),
    subject: str = Form(default=''),
    text: str = Form(default=''),
    html: str = Form(default=''),
    sender_ip: str = Form(default=''),
    envelope: str = Form(default=''),
    charsets: str = Form(default=''),
    SPF: str = Form(default=''),
):
    """
    Handle inbound email from SendGrid Inbound Parse webhook.

    This endpoint receives emails sent to {prefix}+{session_id}@{domain}
    and creates a continuation task to resume the worker conversation.

    SendGrid configuration:
    1. Go to Settings > Inbound Parse
    2. Add your domain (e.g., inbound.codetether.run)
    3. Set destination URL to: https://api.codetether.run/v1/email/inbound
    4. Enable "POST the raw, full MIME message"
    """
    logger.info(
        f'Received inbound email from {from_} to {to} subject: {subject}'
    )

    # Parse the reply-to address to get context
    context = parse_reply_to_address(to)
    session_id = context.get('session_id')
    codebase_id = context.get('codebase_id')

    if not session_id:
        logger.warning(f'Could not extract session_id from to address: {to}')
        # Still accept the webhook to prevent SendGrid retries
        return {
            'success': False,
            'error': 'Could not parse session context from address',
        }

    # Extract the actual reply content (without quoted text)
    reply_body = extract_reply_body(text, html)

    if not reply_body or len(reply_body.strip()) < 3:
        logger.warning(f'Empty or too short reply body from {from_}')
        return {'success': False, 'error': 'Reply body is empty or too short'}

    logger.info(
        f'Extracted reply for session {session_id}: {reply_body[:100]}...'
    )

    # Create the email reply context
    email_context = EmailReplyContext(
        session_id=session_id,
        codebase_id=codebase_id,
        from_email=from_,
        subject=subject,
        body_text=reply_body,
        body_html=html if html else None,
        received_at=datetime.utcnow(),
    )

    # Create a continuation task
    try:
        task = await create_continuation_task(email_context)
        logger.info(
            f'Created continuation task {task.get("id")} from email reply'
        )
        return {
            'success': True,
            'task_id': task.get('id'),
            'session_id': session_id,
            'message': 'Reply received and task created',
        }
    except Exception as e:
        logger.error(f'Failed to create continuation task: {e}')
        return {'success': False, 'error': str(e)}


async def create_continuation_task(
    context: EmailReplyContext,
) -> Dict[str, Any]:
    """
    Create a new task that continues the conversation from an email reply.

    The task will use the same session_id so the worker continues
    the existing OpenCode session.
    """
    # Import here to avoid circular imports
    from .monitor_api import get_opencode_bridge

    bridge = get_opencode_bridge()
    if bridge is None:
        raise RuntimeError('OpenCode bridge not available')

    # Determine codebase_id - try to look it up from the session if not provided
    codebase_id = context.codebase_id

    if not codebase_id:
        # Try to find codebase from existing sessions with this session_id
        # This is best-effort - if we can't find it, we'll use a placeholder
        try:
            from . import database as db

            sessions = await db.db_list_all_sessions(limit=100)
            for session in sessions:
                if session.get('id') == context.session_id:
                    codebase_id = session.get('codebase_id')
                    break
        except Exception as e:
            logger.debug(f'Could not look up codebase for session: {e}')

    if not codebase_id:
        # Use 'global' codebase - workers with a global codebase can pick this up
        codebase_id = 'global'

    # Build the prompt from the email reply
    prompt = f"""[Email Reply from {context.from_email}]

Subject: {context.subject}

{context.body_text}"""

    # Create the task with resume_session_id in metadata to continue the conversation
    task = await bridge.create_task(
        codebase_id=codebase_id,
        title=f'Email reply: {context.subject[:50]}',
        prompt=prompt,
        agent_type='build',  # Default agent type
        metadata={
            'source': 'email_reply',
            'from_email': context.from_email,
            'original_subject': context.subject,
            'received_at': context.received_at.isoformat(),
            'resume_session_id': context.session_id,  # Key: resume the existing session
        },
    )

    if task is None:
        raise RuntimeError('Failed to create continuation task')

    if hasattr(task, 'to_dict'):
        return task.to_dict()
    elif isinstance(task, dict):
        return task
    else:
        # AgentTask dataclass - convert manually
        return {
            'id': task.id,
            'codebase_id': task.codebase_id,
            'title': task.title,
            'prompt': task.prompt,
            'agent_type': task.agent_type,
            'status': task.status.value
            if hasattr(task.status, 'value')
            else str(task.status),
            'metadata': task.metadata,
        }


@email_router.get('/test-reply-address')
async def test_reply_address(
    session_id: str,
    codebase_id: Optional[str] = None,
):
    """
    Test endpoint to generate a reply-to address.

    Useful for debugging the email reply flow.
    """
    address = build_reply_to_address(session_id, codebase_id)
    parsed = parse_reply_to_address(address)

    return {
        'reply_to_address': address,
        'parsed_back': parsed,
        'domain': EMAIL_INBOUND_DOMAIN,
        'prefix': EMAIL_REPLY_PREFIX,
    }


@email_router.post('/test-inbound')
async def test_inbound_parse(
    request: Request,
):
    """
    Debug endpoint to inspect raw inbound parse payload.

    Use this to troubleshoot SendGrid webhook configuration.
    """
    # Get form data
    form_data = await request.form()

    # Log all fields
    fields = {}
    for key in form_data.keys():
        value = form_data.get(key)
        if isinstance(value, UploadFile):
            fields[key] = f'<UploadFile: {value.filename}>'
        else:
            fields[key] = str(value)[:500]  # Truncate long values

    logger.info(f'Test inbound parse received fields: {list(fields.keys())}')

    return {
        'success': True,
        'fields_received': list(fields.keys()),
        'sample_data': fields,
    }
