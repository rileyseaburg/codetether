"""Tests for task orchestration policy (complexity/personality/model routing)."""

import pytest

from a2a_server.task_orchestration import (
    normalize_model_ref,
    orchestrate_task_route,
)


@pytest.fixture(autouse=True)
def clear_routing_env(monkeypatch):
    """Ensure routing-related env vars are isolated per test."""
    keys = [
        'A2A_ROUTING_AUTO_MODEL',
        'A2A_ROUTING_MODEL_FAST',
        'A2A_ROUTING_MODEL_BALANCED',
        'A2A_ROUTING_MODEL_HEAVY',
        'A2A_PERSONALITY_AGENT_MAP',
        'A2A_PERSONALITY_MODEL_MAP',
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)


def test_normalize_model_ref_supports_colon_and_slash():
    assert normalize_model_ref('openai:gpt-5-mini') == 'openai:gpt-5-mini'
    assert normalize_model_ref('openai/gpt-5-mini') == 'openai:gpt-5-mini'
    assert normalize_model_ref('') is None
    assert normalize_model_ref(None) is None


def test_explicit_model_ref_has_highest_priority():
    decision, metadata = orchestrate_task_route(
        prompt='Fix typo in docs',
        agent_type='build',
        model_ref='anthropic:claude-sonnet-4',
        metadata={},
    )

    assert decision.model_ref == 'anthropic:claude-sonnet-4'
    assert decision.model_source == 'explicit'
    assert metadata['model_ref'] == 'anthropic:claude-sonnet-4'
    assert metadata['model'] == 'anthropic/claude-sonnet-4'


def test_personality_map_sets_target_agent_and_model(monkeypatch):
    monkeypatch.setenv(
        'A2A_PERSONALITY_AGENT_MAP',
        '{"reviewer":"code-reviewer","builder":"implementation-agent"}',
    )
    monkeypatch.setenv(
        'A2A_PERSONALITY_MODEL_MAP',
        '{"reviewer":"anthropic:claude-sonnet-4"}',
    )

    decision, metadata = orchestrate_task_route(
        prompt='Review this PR for regressions',
        agent_type='general',
        metadata={'worker_personality': 'reviewer'},
    )

    assert decision.target_agent_name == 'code-reviewer'
    assert decision.model_ref == 'anthropic:claude-sonnet-4'
    assert decision.model_source == 'personality_map'
    assert metadata['target_agent_name'] == 'code-reviewer'
    assert metadata['model'] == 'anthropic/claude-sonnet-4'


def test_auto_model_routing_uses_tier_models(monkeypatch):
    monkeypatch.setenv('A2A_ROUTING_AUTO_MODEL', 'true')
    monkeypatch.setenv('A2A_ROUTING_MODEL_FAST', 'openai:gpt-5-mini')
    monkeypatch.setenv('A2A_ROUTING_MODEL_BALANCED', 'anthropic:claude-sonnet-4')
    monkeypatch.setenv('A2A_ROUTING_MODEL_HEAVY', 'openai:o3')

    quick_decision, _ = orchestrate_task_route(
        prompt='Fix typo',
        agent_type='build',
        metadata={},
    )
    deep_decision, _ = orchestrate_task_route(
        prompt=(
            'Design and implement a multi-step migration and distributed '
            'orchestration plan with security hardening and performance benchmarking.'
        ),
        agent_type='architect',
        metadata={},
    )

    assert quick_decision.model_tier in ('fast', 'balanced')
    if quick_decision.model_tier == 'fast':
        assert quick_decision.model_ref == 'openai:gpt-5-mini'
    else:
        assert quick_decision.model_ref == 'anthropic:claude-sonnet-4'

    assert deep_decision.model_tier == 'heavy'
    assert deep_decision.model_ref == 'openai:o3'
    assert deep_decision.model_source == 'tier_map'


def test_auto_model_disabled_leaves_model_unset():
    decision, metadata = orchestrate_task_route(
        prompt='Refactor module',
        agent_type='build',
        metadata={},
    )

    assert decision.model_ref is None
    assert decision.model_source == 'none'
    assert 'model_ref' not in metadata or metadata['model_ref'] is None


def test_routing_metadata_block_is_present():
    decision, metadata = orchestrate_task_route(
        prompt='Investigate root cause of production incident',
        agent_type='general',
        metadata={'worker_personality': 'incident-responder'},
    )

    assert 'routing' in metadata
    routing = metadata['routing']
    assert routing['complexity'] == decision.complexity
    assert routing['model_tier'] == decision.model_tier
    assert routing['worker_personality'] == decision.worker_personality
    assert routing['policy'] == 'a2a.task_orchestration.v1'


def test_budget_hint_caps_tier_for_quick_tasks():
    decision, metadata = orchestrate_task_route(
        prompt='Fix a typo in one line of README',
        agent_type='build',
        metadata={'budget_tier': 'minimal'},
    )

    assert decision.complexity == 'quick'
    assert decision.model_tier == 'fast'
    assert metadata['model_tier'] == 'fast'


def test_deep_tasks_keep_at_least_balanced_tier_under_budget_pressure():
    decision, metadata = orchestrate_task_route(
        prompt=(
            'Design a distributed migration and multi-step orchestration plan '
            'with incident root-cause analysis, security hardening, and '
            'performance benchmarking.'
        ),
        agent_type='architect',
        metadata={'budget_tier': 'minimal'},
    )

    assert decision.complexity == 'deep'
    assert decision.model_tier == 'balanced'
    assert metadata['model_tier'] == 'balanced'
