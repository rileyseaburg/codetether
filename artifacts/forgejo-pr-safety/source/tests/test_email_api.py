"""
Tests for email debugging and testing API endpoints.

These tests verify the email testing endpoints work correctly
using real environment configuration - no mocks.
"""

import os
import pytest
from datetime import datetime

# Test imports
from a2a_server.email_api import (
    TestEmail,
    TestEmailStore,
    get_test_email_store,
    _sanitize_email,
    _get_email_config,
    _build_email_html,
    _build_email_text,
)
from a2a_server.email_inbound import (
    parse_reply_to_address,
    build_reply_to_address,
    extract_reply_body,
)


class TestEmailSanitization:
    """Test email sanitization for security."""

    def test_sanitize_normal_email(self):
        """Test sanitizing a normal email address."""
        result = _sanitize_email('john.doe@example.com')
        assert result == 'j***e@example.com'
        assert 'john' not in result
        assert 'doe' not in result

    def test_sanitize_short_email(self):
        """Test sanitizing a short local part."""
        result = _sanitize_email('ab@example.com')
        assert result == '***@example.com'

    def test_sanitize_invalid_email(self):
        """Test sanitizing an invalid email."""
        result = _sanitize_email('notanemail')
        assert result == '***@***'

    def test_sanitize_empty_email(self):
        """Test sanitizing an empty string."""
        result = _sanitize_email('')
        assert result == '***@***'

    def test_sanitize_none(self):
        """Test sanitizing None (cast to satisfy type checker, tests runtime behavior)."""
        result = _sanitize_email(None)  # type: ignore[arg-type]
        assert result == '***@***'


class TestReplyAddressParsing:
    """Test reply-to address parsing."""

    def test_parse_valid_address_with_session(self):
        """Test parsing a valid reply-to address with session ID."""
        result = parse_reply_to_address('task+ses_abc123@inbound.codetether.run')
        assert result['session_id'] == 'ses_abc123'
        assert result['codebase_id'] is None

    def test_parse_valid_address_with_session_and_codebase(self):
        """Test parsing a valid reply-to address with session and codebase."""
        result = parse_reply_to_address('task+ses_abc123+cb_xyz789@inbound.codetether.run')
        assert result['session_id'] == 'ses_abc123'
        assert result['codebase_id'] == 'cb_xyz789'

    def test_parse_invalid_prefix(self):
        """Test parsing an address with invalid prefix."""
        result = parse_reply_to_address('reply+ses_abc123@inbound.codetether.run')
        assert result['session_id'] is None
        assert result['codebase_id'] is None

    def test_parse_missing_plus(self):
        """Test parsing an address without plus separator."""
        result = parse_reply_to_address('task@inbound.codetether.run')
        assert result['session_id'] is None

    def test_build_and_parse_roundtrip(self):
        """Test that build and parse are inverses."""
        session_id = 'ses_test123'
        codebase_id = 'cb_example456'

        address = build_reply_to_address(session_id, codebase_id)
        parsed = parse_reply_to_address(address)

        assert parsed['session_id'] == session_id
        assert parsed['codebase_id'] == codebase_id


class TestExtractReplyBody:
    """Test email reply body extraction."""

    def test_extract_simple_reply(self):
        """Test extracting a simple reply."""
        body = "This is my reply.\n\nOn Mon, Jan 11 wrote:\n> Original message"
        result = extract_reply_body(body)
        assert 'This is my reply' in result
        assert 'Original message' not in result

    def test_extract_with_quoted_text(self):
        """Test extracting reply with multiple quoted lines."""
        body = """Thanks for the update!

> Previous message line 1
> Previous message line 2"""
        result = extract_reply_body(body)
        assert 'Thanks for the update' in result
        assert 'Previous message' not in result

    def test_extract_empty_body(self):
        """Test extracting from empty body."""
        result = extract_reply_body('')
        assert result == ''

    def test_extract_only_quoted(self):
        """Test extracting from body that's mostly quoted."""
        body = "> This is all quoted"
        result = extract_reply_body(body)
        # Should fall back to original if too short
        assert len(result) > 0


class TestTestEmailStore:
    """Test the in-memory email store."""

    def test_store_and_retrieve(self):
        """Test storing and retrieving an email."""
        store = TestEmailStore()
        email = TestEmail(
            id='test-1',
            to_email='recipient@example.com',
            from_email='sender@example.com',
            reply_to=None,
            subject='Test Subject',
            body_html='<p>Test</p>',
            body_text='Test',
            task_id='task-1',
            session_id='ses_1',
            codebase_id=None,
            status='queued',
            created_at=datetime.utcnow(),
        )

        store.store(email)
        retrieved = store.get('test-1')

        assert retrieved is not None
        assert retrieved.id == 'test-1'
        assert retrieved.subject == 'Test Subject'

    def test_fifo_eviction(self):
        """Test FIFO eviction when at capacity."""
        store = TestEmailStore(max_emails=3)

        for i in range(5):
            email = TestEmail(
                id=f'test-{i}',
                to_email='recipient@example.com',
                from_email='sender@example.com',
                reply_to=None,
                subject=f'Test {i}',
                body_html='',
                body_text='',
                task_id=f'task-{i}',
                session_id=None,
                codebase_id=None,
                status='queued',
                created_at=datetime.utcnow(),
            )
            store.store(email)

        # First two should be evicted
        assert store.get('test-0') is None
        assert store.get('test-1') is None
        # Last three should remain
        assert store.get('test-2') is not None
        assert store.get('test-3') is not None
        assert store.get('test-4') is not None

    def test_list_all_returns_newest_first(self):
        """Test that list_all returns newest emails first."""
        store = TestEmailStore()

        for i in range(3):
            email = TestEmail(
                id=f'test-{i}',
                to_email='recipient@example.com',
                from_email='sender@example.com',
                reply_to=None,
                subject=f'Test {i}',
                body_html='',
                body_text='',
                task_id=f'task-{i}',
                session_id=None,
                codebase_id=None,
                status='queued',
                created_at=datetime.utcnow(),
            )
            store.store(email)

        emails = store.list_all()
        assert len(emails) == 3
        assert emails[0].id == 'test-2'  # Newest first
        assert emails[2].id == 'test-0'  # Oldest last

    def test_clear(self):
        """Test clearing all emails."""
        store = TestEmailStore()

        for i in range(3):
            email = TestEmail(
                id=f'test-{i}',
                to_email='recipient@example.com',
                from_email='sender@example.com',
                reply_to=None,
                subject=f'Test {i}',
                body_html='',
                body_text='',
                task_id=f'task-{i}',
                session_id=None,
                codebase_id=None,
                status='queued',
                created_at=datetime.utcnow(),
            )
            store.store(email)

        count = store.clear()
        assert count == 3
        assert store.list_all() == []


class TestEmailHtmlBuilder:
    """Test email HTML/text building."""

    def test_build_completed_email_html(self):
        """Test building HTML for a completed task."""
        html = _build_email_html(
            task_id='task-123',
            title='Test Task',
            status='completed',
            result='Task completed successfully',
            duration_ms=5000,
            session_id='ses_abc',
        )

        assert 'task-123' in html
        assert 'Test Task' in html
        assert 'COMPLETED' in html
        assert 'Task completed successfully' in html
        assert '5s' in html

    def test_build_failed_email_html(self):
        """Test building HTML for a failed task."""
        html = _build_email_html(
            task_id='task-456',
            title='Failed Task',
            status='failed',
            error='Something went wrong',
        )

        assert 'task-456' in html
        assert 'FAILED' in html
        assert 'Something went wrong' in html

    def test_build_email_text(self):
        """Test building plain text email."""
        text = _build_email_text(
            task_id='task-789',
            title='Plain Text Task',
            status='completed',
            result='Result here',
            duration_ms=10000,
        )

        assert 'task-789' in text
        assert 'Plain Text Task' in text
        assert 'COMPLETED' in text
        assert 'Result here' in text
        assert '10s' in text

    def test_duration_formatting(self):
        """Test duration formatting for various values."""
        # Less than a minute
        html = _build_email_html(
            task_id='t1', title='T1', status='completed',
            duration_ms=45000,
        )
        assert '45s' in html

        # More than a minute
        html = _build_email_html(
            task_id='t2', title='T2', status='completed',
            duration_ms=125000,  # 2m 5s
        )
        assert '2m' in html
        assert '5s' in html


class TestEmailConfig:
    """Test email configuration handling using real environment."""

    def test_get_config_returns_valid_structure(self):
        """Test that _get_email_config returns expected structure."""
        config = _get_email_config()
        
        # Config should always have these keys regardless of env state
        assert 'configured' in config
        assert 'sendgrid_key_set' in config
        assert 'issues' in config
        assert isinstance(config['issues'], list)
        
    def test_config_reflects_real_environment(self):
        """Test that config accurately reflects real environment state."""
        config = _get_email_config()
        
        # Check if sendgrid_key_set matches actual env
        has_key = bool(os.environ.get('SENDGRID_API_KEY'))
        assert config['sendgrid_key_set'] == has_key
        
    def test_config_issues_are_actionable(self):
        """Test that any config issues contain actionable information."""
        config = _get_email_config()
        
        # If there are issues, they should be non-empty strings
        for issue in config['issues']:
            assert isinstance(issue, str)
            assert len(issue) > 0
