"""
Tests for the Proactive API endpoints.

Tests cover the Pydantic response models and helper functions that transform
database rows to API responses. These don't require a live DB.
"""

import json
import pytest
from datetime import datetime, timezone

from a2a_server.proactive_api import (
    _rule_row_to_response,
    _health_check_row_to_response,
    _loop_row_to_response,
    _iteration_row_to_response,
    RuleCreate,
    LoopCreate,
    HealthCheckCreate,
)


def _make_rule_row(**overrides):
    """Construct a dict that looks like a DB row from agent_rules."""
    base = {
        'id': 'rule-1',
        'tenant_id': 'tenant-1',
        'user_id': 'user-1',
        'name': 'Test Rule',
        'description': 'A test rule',
        'trigger_type': 'event',
        'trigger_config': json.dumps({'event_type': 'task.completed'}),
        'action': json.dumps({'task_template': {'prompt': 'do something'}}),
        'enabled': True,
        'cooldown_seconds': 300,
        'last_triggered_at': None,
        'trigger_count': 0,
        'next_run_at': None,
        'created_at': datetime(2025, 1, 1, tzinfo=timezone.utc),
        'updated_at': datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    base.update(overrides)

    class FakeRow(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    return FakeRow(base)


def _make_health_check_row(**overrides):
    base = {
        'id': 'hc-1',
        'tenant_id': 'tenant-1',
        'name': 'DB Check',
        'description': 'Check DB connectivity',
        'check_type': 'db_query',
        'check_config': json.dumps({'query': 'SELECT 1'}),
        'interval_seconds': 60,
        'last_checked_at': None,
        'next_check_at': datetime(2025, 1, 1, tzinfo=timezone.utc),
        'last_status': 'healthy',
        'last_result': json.dumps({'response_time_ms': 5}),
        'consecutive_failures': 0,
        'enabled': True,
        'created_at': datetime(2025, 1, 1, tzinfo=timezone.utc),
        'updated_at': datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    base.update(overrides)

    class FakeRow(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    return FakeRow(base)


def _make_loop_row(**overrides):
    base = {
        'id': 'loop-1',
        'tenant_id': 'tenant-1',
        'user_id': 'user-1',
        'persona_slug': 'monitor',
        'codebase_id': None,
        'status': 'running',
        'state': json.dumps({'focus': 'latency'}),
        'iteration_count': 42,
        'iterations_today': 5,
        'iteration_interval_seconds': 300,
        'max_iterations_per_day': 100,
        'daily_cost_ceiling_cents': 500,
        'cost_today_cents': 120,
        'cost_total_cents': 4500,
        'last_iteration_at': datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
        'last_heartbeat': datetime(2025, 1, 1, 12, 5, tzinfo=timezone.utc),
        'created_at': datetime(2025, 1, 1, tzinfo=timezone.utc),
        'updated_at': datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    base.update(overrides)

    class FakeRow(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    return FakeRow(base)


def _make_iteration_row(**overrides):
    base = {
        'id': 'iter-1',
        'loop_id': 'loop-1',
        'iteration_number': 1,
        'task_id': 'task-1',
        'input_state': json.dumps({'focus': 'latency'}),
        'output_state': json.dumps({'focus': 'latency', 'result': 'OK'}),
        'cost_cents': 10,
        'duration_seconds': 45,
        'started_at': datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
        'completed_at': datetime(2025, 1, 1, 12, 0, 45, tzinfo=timezone.utc),
    }
    base.update(overrides)

    class FakeRow(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    return FakeRow(base)


# ============================================================================
# Row-to-response helpers
# ============================================================================


class TestRuleRowToResponse:
    def test_basic_conversion(self):
        row = _make_rule_row()
        resp = _rule_row_to_response(row)
        assert resp.id == 'rule-1'
        assert resp.name == 'Test Rule'
        assert resp.trigger_type == 'event'
        assert resp.trigger_config == {'event_type': 'task.completed'}
        assert resp.action == {'task_template': {'prompt': 'do something'}}
        assert resp.enabled is True
        assert resp.cooldown_seconds == 300
        assert resp.trigger_count == 0

    def test_json_string_config(self):
        row = _make_rule_row(
            trigger_config='{"event_type": "health.check.failed"}',
            action='{"escalate": true}',
        )
        resp = _rule_row_to_response(row)
        assert resp.trigger_config == {'event_type': 'health.check.failed'}
        assert resp.action == {'escalate': True}

    def test_dict_config(self):
        row = _make_rule_row(
            trigger_config={'event_type': 'custom'},
            action={'do': 'thing'},
        )
        resp = _rule_row_to_response(row)
        assert resp.trigger_config == {'event_type': 'custom'}
        assert resp.action == {'do': 'thing'}


class TestHealthCheckRowToResponse:
    def test_basic_conversion(self):
        row = _make_health_check_row()
        resp = _health_check_row_to_response(row)
        assert resp.id == 'hc-1'
        assert resp.name == 'DB Check'
        assert resp.check_type == 'db_query'
        assert resp.last_status == 'healthy'
        assert resp.last_result == {'response_time_ms': 5}

    def test_empty_last_result(self):
        row = _make_health_check_row(last_result='')
        resp = _health_check_row_to_response(row)
        assert resp.last_result == {}

    def test_none_last_result(self):
        row = _make_health_check_row(last_result=None)
        resp = _health_check_row_to_response(row)
        assert resp.last_result == {}


class TestLoopRowToResponse:
    def test_basic_conversion(self):
        row = _make_loop_row()
        resp = _loop_row_to_response(row)
        assert resp.id == 'loop-1'
        assert resp.persona_slug == 'monitor'
        assert resp.status == 'running'
        assert resp.state == {'focus': 'latency'}
        assert resp.iteration_count == 42
        assert resp.iterations_today == 5
        assert resp.cost_today_cents == 120
        assert resp.cost_total_cents == 4500

    def test_dict_state(self):
        row = _make_loop_row(state={'already': 'dict'})
        resp = _loop_row_to_response(row)
        assert resp.state == {'already': 'dict'}

    def test_empty_state(self):
        row = _make_loop_row(state='')
        resp = _loop_row_to_response(row)
        assert resp.state == {}


class TestIterationRowToResponse:
    def test_basic_conversion(self):
        row = _make_iteration_row()
        resp = _iteration_row_to_response(row)
        assert resp.id == 'iter-1'
        assert resp.loop_id == 'loop-1'
        assert resp.iteration_number == 1
        assert resp.task_id == 'task-1'
        assert resp.cost_cents == 10
        assert resp.duration_seconds == 45
        assert resp.input_state == {'focus': 'latency'}
        assert resp.output_state == {'focus': 'latency', 'result': 'OK'}

    def test_empty_states(self):
        row = _make_iteration_row(input_state='', output_state='')
        resp = _iteration_row_to_response(row)
        assert resp.input_state == {}
        assert resp.output_state == {}


# ============================================================================
# Pydantic model validation
# ============================================================================


class TestRuleCreateValidation:
    def test_valid_event_rule(self):
        r = RuleCreate(
            name='My Rule',
            trigger_type='event',
            trigger_config={'event_type': 'task.completed'},
            action={'prompt': 'analyze'},
        )
        assert r.trigger_type == 'event'

    def test_valid_cron_rule(self):
        r = RuleCreate(
            name='Hourly Scan',
            trigger_type='cron',
            trigger_config={'cron_expression': '0 * * * *'},
            action={'prompt': 'scan'},
        )
        assert r.trigger_type == 'cron'

    def test_valid_threshold_rule(self):
        r = RuleCreate(
            name='Alert',
            trigger_type='threshold',
            trigger_config={'health_check_id': 'hc-1', 'condition': "status == 'failed'"},
            action={'prompt': 'investigate'},
        )
        assert r.trigger_type == 'threshold'

    def test_invalid_trigger_type(self):
        with pytest.raises(Exception):
            RuleCreate(name='Bad', trigger_type='invalid', action={})

    def test_empty_name_fails(self):
        with pytest.raises(Exception):
            RuleCreate(name='', trigger_type='event', action={})

    def test_negative_cooldown(self):
        with pytest.raises(Exception):
            RuleCreate(name='X', trigger_type='event', action={}, cooldown_seconds=-1)


class TestLoopCreateValidation:
    def test_valid_loop(self):
        l = LoopCreate(persona_slug='monitor')
        assert l.persona_slug == 'monitor'
        assert l.iteration_interval_seconds == 300  # default
        assert l.max_iterations_per_day == 100  # default
        assert l.daily_cost_ceiling_cents == 500  # default

    def test_empty_persona_fails(self):
        with pytest.raises(Exception):
            LoopCreate(persona_slug='')

    def test_interval_too_short(self):
        with pytest.raises(Exception):
            LoopCreate(persona_slug='monitor', iteration_interval_seconds=10)


class TestHealthCheckCreateValidation:
    def test_valid_http_check(self):
        hc = HealthCheckCreate(
            name='API Health',
            check_type='http',
            check_config={'url': 'https://example.com/health'},
        )
        assert hc.check_type == 'http'

    def test_invalid_check_type(self):
        with pytest.raises(Exception):
            HealthCheckCreate(
                name='Bad', check_type='ftp', check_config={},
            )

    def test_interval_too_short(self):
        with pytest.raises(Exception):
            HealthCheckCreate(
                name='Bad', check_type='http', check_config={},
                interval_seconds=5,
            )
