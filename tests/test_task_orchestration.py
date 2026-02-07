"""Tests for task orchestration policy (complexity/personality/model routing)."""

from a2a_server.task_orchestration import orchestrate_task_route


def test_explicit_model_ref_wins():
    decision, metadata = orchestrate_task_route(
        prompt='Refactor this module',
        agent_type='build',
        model_ref='openai:gpt-5.1',
    )

    assert decision.model_ref == 'openai:gpt-5.1'
    assert decision.model_source == 'explicit'
    assert metadata['model_ref'] == 'openai:gpt-5.1'
    assert metadata['model'] == 'openai/gpt-5.1'


def test_complexity_inference_quick_vs_deep():
    quick_decision, quick_metadata = orchestrate_task_route(
        prompt='Fix a typo in README',
        agent_type='build',
        metadata={},
    )
    deep_decision, deep_metadata = orchestrate_task_route(
        prompt=(
            'Design a distributed migration plan for multi-step refactor with '
            'performance and security validation across services.'
        ),
        agent_type='architect',
        files=[f'file_{i}.py' for i in range(12)],
        metadata={},
    )

    assert quick_decision.complexity == 'quick'
    assert quick_metadata['model_tier'] == 'fast'
    assert deep_decision.complexity == 'deep'
    assert deep_metadata['model_tier'] == 'heavy'


def test_personality_maps_to_target_and_model(monkeypatch):
    monkeypatch.setenv(
        'A2A_PERSONALITY_AGENT_MAP',
        '{"builder":"builder-worker"}',
    )
    monkeypatch.setenv(
        'A2A_PERSONALITY_MODEL_MAP',
        '{"builder":"anthropic:claude-sonnet-4"}',
    )

    decision, metadata = orchestrate_task_route(
        prompt='Implement this feature end-to-end',
        worker_personality='builder',
    )

    assert decision.worker_personality == 'builder'
    assert decision.target_agent_name == 'builder-worker'
    assert decision.model_ref == 'anthropic:claude-sonnet-4'
    assert metadata['target_agent_name'] == 'builder-worker'
    assert metadata['model'] == 'anthropic/claude-sonnet-4'
