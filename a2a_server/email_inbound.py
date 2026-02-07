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

# Contact email forwarding
CONTACT_FORWARD_EMAIL = os.environ.get(
    'CONTACT_FORWARD_EMAIL', 'riley@evolvingsoftware.io'
)
CONTACT_EMAIL_PREFIXES = [
    'info',
    'support',
    'hello',
    'contact',
    'help',
    'sales',
]


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
    model: Optional[str] = None  # Model selection from email


# Supported model aliases for email replies
# Maps friendly names to provider/model format
MODEL_ALIASES: Dict[str, str] = {
    # Claude models
    'claude': 'anthropic/claude-sonnet-4-20250514',
    'claude-sonnet': 'anthropic/claude-sonnet-4-20250514',
    'claude-sonnet-4': 'anthropic/claude-sonnet-4-20250514',
    'sonnet': 'anthropic/claude-sonnet-4-20250514',
    'sonnet-4': 'anthropic/claude-sonnet-4-20250514',
    'claude-opus': 'anthropic/claude-opus-4-20250514',
    'opus': 'anthropic/claude-opus-4-20250514',
    'opus-4': 'anthropic/claude-opus-4-20250514',
    'claude-haiku': 'anthropic/claude-3-5-haiku-latest',
    'haiku': 'anthropic/claude-3-5-haiku-latest',
    # OpenAI models
    'gpt-4': 'openai/gpt-4',
    'gpt-4o': 'openai/gpt-4o',
    'gpt-4-turbo': 'openai/gpt-4-turbo',
    'gpt-4.1': 'openai/gpt-4.1',
    'o1': 'openai/o1',
    'o1-mini': 'openai/o1-mini',
    'o3': 'openai/o3',
    'o3-mini': 'openai/o3-mini',
    # Google models
    'gemini': 'google/gemini-2.5-pro',
    'gemini-pro': 'google/gemini-2.5-pro',
    'gemini-2.5-pro': 'google/gemini-2.5-pro',
    'gemini-flash': 'google/gemini-2.5-flash',
    'gemini-2.5-flash': 'google/gemini-2.5-flash',
    # MiniMax models
    'minimax': 'minimax/MiniMax-M1-80k',
    'minimax-m1': 'minimax/MiniMax-M1-80k',
    'm1': 'minimax/MiniMax-M1-80k',
    # Grok
    'grok': 'xai/grok-3',
    'grok-3': 'xai/grok-3',
}


def parse_model_from_subject(subject: str) -> tuple[Optional[str], str]:
    """
    Parse model selection from email subject.

    Supports formats:
    - [model:claude-sonnet] or [model: claude-sonnet]
    - [use:gpt-4o] or [use: gpt-4o]
    - [with:gemini] or [with: gemini]

    Also supports direct provider/model format:
    - [model:anthropic/claude-sonnet-4-20250514]

    Returns:
        Tuple of (resolved_model, cleaned_subject)
        - resolved_model: The full provider/model path, or None if not specified
        - cleaned_subject: Subject with the model tag removed
    """
    # Pattern to match [model:xxx], [use:xxx], [with:xxx]
    pattern = r'\[(model|use|with)\s*:\s*([^\]]+)\]'
    match = re.search(pattern, subject, re.IGNORECASE)

    if not match:
        return None, subject

    model_spec = match.group(2).strip().lower()

    # Remove the tag from subject
    cleaned_subject = re.sub(pattern, '', subject, flags=re.IGNORECASE).strip()
    # Clean up any double spaces
    cleaned_subject = re.sub(r'\s+', ' ', cleaned_subject).strip()

    # Check if it's already a full provider/model path
    if '/' in model_spec:
        logger.info(f'Model specified directly in email subject: {model_spec}')
        return model_spec, cleaned_subject

    # Look up alias
    resolved = MODEL_ALIASES.get(model_spec)
    if resolved:
        logger.info(
            f'Resolved model alias "{model_spec}" to "{resolved}" from email subject'
        )
        return resolved, cleaned_subject

    # Unknown alias - log warning but still try to use it
    logger.warning(
        f'Unknown model alias "{model_spec}" in email subject, '
        f'will attempt to use as-is. Known aliases: {", ".join(sorted(MODEL_ALIASES.keys()))}'
    )
    return model_spec, cleaned_subject


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
    # IMPORTANT: Don't lowercase the entire address - session IDs are case-sensitive!
    # Only lowercase the prefix for comparison, but preserve the original case of session_id
    match = re.match(r'^([^@]+)@', to_address.strip())
    if not match:
        return result

    local_part = match.group(1)

    # Check if it starts with our prefix (case-insensitive comparison)
    prefix = EMAIL_REPLY_PREFIX.lower()
    if not local_part.lower().startswith(f'{prefix}+'):
        logger.debug(
            f'Email to address does not match expected prefix: {to_address}'
        )
        return result

    # Extract the parts after the prefix, preserving original case
    # Skip the prefix length + 1 for the '+'
    parts_str = local_part[len(prefix) + 1 :]
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


def is_contact_email(to_address: str) -> bool:
    """Check if email is to a general contact address like info@, support@, etc."""
    match = re.match(r'^([^@+]+)[@+]', to_address.lower().strip())
    if not match:
        return False
    local_part = match.group(1)
    return local_part in CONTACT_EMAIL_PREFIXES


async def forward_contact_email(
    from_email: str,
    to_email: str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
) -> bool:
    """Forward a contact email to the admin address."""
    import httpx

    api_key = os.environ.get('SENDGRID_API_KEY', '')
    if not api_key or not CONTACT_FORWARD_EMAIL:
        logger.warning(
            'Cannot forward contact email: missing SENDGRID_API_KEY or CONTACT_FORWARD_EMAIL'
        )
        return False

    # Build forwarded email
    forward_subject = f'[CodeTether Contact] {subject}'
    forward_body = f"""New contact form submission / email received:

From: {from_email}
To: {to_email}
Subject: {subject}

---
{body_text}
---

Reply directly to this email to respond to the sender.
"""

    payload = {
        'personalizations': [
            {
                'to': [{'email': CONTACT_FORWARD_EMAIL}],
            }
        ],
        'from': {
            'email': os.environ.get(
                'SENDGRID_FROM_EMAIL', 'noreply@codetether.run'
            ),
            'name': 'CodeTether',
        },
        'reply_to': {'email': from_email},
        'subject': forward_subject,
        'content': [
            {'type': 'text/plain', 'value': forward_body},
        ],
    }

    if body_html:
        payload['content'].append(
            {'type': 'text/html', 'value': f'<pre>{body_html}</pre>'}
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                'https://api.sendgrid.com/v3/mail/send',
                json=payload,
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                timeout=30.0,
            )
            if response.status_code in (200, 202):
                logger.info(
                    f'Forwarded contact email from {from_email} to {CONTACT_FORWARD_EMAIL}'
                )
                return True
            else:
                logger.error(
                    f'Failed to forward contact email: {response.status_code} {response.text}'
                )
                return False
    except Exception as e:
        logger.error(f'Error forwarding contact email: {e}')
        return False


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

    Also handles contact emails (info@, support@, etc.) by forwarding
    them to the configured admin email address.

    SendGrid configuration:
    1. Go to Settings > Inbound Parse
    2. Add your domain (e.g., inbound.codetether.run)
    3. Set destination URL to: https://api.codetether.run/v1/email/inbound
    4. Enable "POST the raw, full MIME message"
    """
    from . import database as db

    logger.info(
        f'Received inbound email from {from_} to {to} subject: {subject}'
    )

    # Check if this is a contact email (info@, support@, etc.)
    if is_contact_email(to):
        logger.info(
            f'Contact email detected, forwarding to {CONTACT_FORWARD_EMAIL}'
        )
        forwarded = await forward_contact_email(
            from_email=from_,
            to_email=to,
            subject=subject,
            body_text=text,
            body_html=html if html else None,
        )
        return {
            'success': forwarded,
            'type': 'contact_forward',
            'forwarded_to': CONTACT_FORWARD_EMAIL if forwarded else None,
            'message': 'Contact email forwarded'
            if forwarded
            else 'Failed to forward contact email',
        }

    # Parse the reply-to address to get context
    context = parse_reply_to_address(to)
    session_id = context.get('session_id')
    codebase_id = context.get('codebase_id')

    # Parse model selection from subject (e.g., [model:claude-sonnet])
    model, cleaned_subject = parse_model_from_subject(subject)
    if model:
        logger.info(f'Model "{model}" selected via email subject')

    # Extract the actual reply content (without quoted text)
    reply_body = extract_reply_body(text, html)

    # Log the inbound email to the database
    email_id = await db.db_log_inbound_email(
        from_email=from_,
        to_email=to,
        subject=subject,
        body_text=reply_body or text,
        body_html=html if html else None,
        session_id=session_id,
        codebase_id=codebase_id,
        sender_ip=sender_ip,
        spf_result=SPF,
        status='received',
        metadata={
            'envelope': envelope,
            'charsets': charsets,
            'original_text_length': len(text) if text else 0,
            'extracted_text_length': len(reply_body) if reply_body else 0,
            'model': model,  # Track model selection in metadata
        },
    )

    if not session_id:
        logger.warning(f'Could not extract session_id from to address: {to}')
        # Update the email record with error
        if email_id:
            await db.db_update_inbound_email(
                email_id,
                status='failed',
                error='Could not parse session context from address',
            )
        # Still accept the webhook to prevent SendGrid retries
        return {
            'success': False,
            'error': 'Could not parse session context from address',
        }

    if not reply_body or len(reply_body.strip()) < 3:
        logger.warning(f'Empty or too short reply body from {from_}')
        if email_id:
            await db.db_update_inbound_email(
                email_id,
                status='failed',
                error='Reply body is empty or too short',
            )
        return {'success': False, 'error': 'Reply body is empty or too short'}

    logger.info(
        f'Extracted reply for session {session_id}: {reply_body[:100]}...'
    )

    # Create the email reply context
    email_context = EmailReplyContext(
        session_id=session_id,
        codebase_id=codebase_id,
        from_email=from_,
        subject=cleaned_subject,  # Use cleaned subject (model tag removed)
        body_text=reply_body,
        body_html=html if html else None,
        received_at=datetime.utcnow(),
        model=model,  # Pass model selection
    )

    # Create a continuation task
    try:
        task = await create_continuation_task(email_context)
        task_id = task.get('id')
        logger.info(f'Created continuation task {task_id} from email reply')

        # Update the email record with success
        if email_id:
            await db.db_update_inbound_email(
                email_id,
                task_id=task_id,
                status='processed',
            )

        return {
            'success': True,
            'task_id': task_id,
            'session_id': session_id,
            'email_id': email_id,
            'model': model,  # Include model selection in response
            'message': 'Reply received and task created'
            + (f' (model: {model})' if model else ''),
        }
    except Exception as e:
        logger.error(f'Failed to create continuation task: {e}')
        if email_id:
            await db.db_update_inbound_email(
                email_id,
                status='failed',
                error=str(e),
            )
        return {'success': False, 'error': str(e)}


async def create_continuation_task(
    context: EmailReplyContext,
) -> Dict[str, Any]:
    """
    Create a new task that continues the conversation from an email reply.

    The task will use the same session_id so the worker continues
    the existing agent session.
    """
    # Import here to avoid circular imports
    from .monitor_api import get_agent_bridge

    bridge = get_agent_bridge()
    if bridge is None:
        raise RuntimeError('Agent bridge not available')

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

    # Build metadata for the task
    metadata = {
        'source': 'email_reply',
        'from_email': context.from_email,
        'original_subject': context.subject,
        'received_at': context.received_at.isoformat(),
        'resume_session_id': context.session_id,  # Key: resume the existing session
    }

    # Log model selection
    if context.model:
        logger.info(
            f'Creating continuation task with model: {context.model}'
        )
        metadata['model_source'] = 'email_subject'

    # Create the task with resume_session_id in metadata to continue the conversation
    task = await bridge.create_task(
        codebase_id=codebase_id,
        title=f'Email reply: {context.subject[:50]}',
        prompt=prompt,
        agent_type='build',  # Default agent type
        model=context.model,  # Pass model from email subject
        metadata=metadata,
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


@email_router.get('/test-model-parsing')
async def test_model_parsing(subject: str):
    """
    Test endpoint to verify model parsing from email subjects.

    Example subjects:
    - "Re: Task completed [model:claude-sonnet]"
    - "[use:gpt-4o] Please fix the bug"
    - "[with:gemini] Review my code"
    - "Re: Task [model:anthropic/claude-sonnet-4-20250514]"

    Supported model aliases:
    - claude, claude-sonnet, sonnet, opus, haiku
    - gpt-4, gpt-4o, gpt-4-turbo, o1, o3
    - gemini, gemini-pro, gemini-flash
    - minimax, m1, grok
    """
    model, cleaned_subject = parse_model_from_subject(subject)

    return {
        'original_subject': subject,
        'cleaned_subject': cleaned_subject,
        'parsed_model': model,
        'available_aliases': sorted(MODEL_ALIASES.keys()),
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
