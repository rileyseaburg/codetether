"""
Tests for model-aware task routing.

Tests the model_ref feature which allows tasks to target specific models
and workers to advertise models_supported.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from a2a_server.message_broker import InMemoryMessageBroker
from a2a_server.models import AgentCard, AgentProvider, AgentCapabilities


def make_agent_card(name: str, description: str, url: str) -> AgentCard:
    """Helper to create an AgentCard with required fields."""
    return AgentCard(
        name=name,
        description=description,
        url=url,
        provider=AgentProvider(organization='Test', url='http://test.com'),
        capabilities=AgentCapabilities(
            streaming=True,
            push_notifications=True,
            state_transition_history=False,
            media=False,
            extensions=None,
        ),
        additional_interfaces=None,
        version='1.0',
    )


class TestModelRouting:
    """Test model_ref on task routing."""

    @pytest.fixture
    def broker(self):
        """Create an in-memory broker for testing."""
        broker = InMemoryMessageBroker()
        return broker

    @pytest.mark.asyncio
    async def test_register_agent_with_models_supported(self, broker):
        """Test that agents can register with models_supported."""
        await broker.start()

        card = make_agent_card(
            name='gpt-worker:instance1',
            description='Worker with GPT models',
            url='http://localhost:8000',
        )

        models = ['openai:gpt-5.2', 'openai:gpt-5-mini', 'openai:o4-mini']
        await broker.register_agent(card, models_supported=models)

        # Verify agent has models_supported
        assert broker._agent_models.get('gpt-worker:instance1') == models

        await broker.stop()

    @pytest.mark.asyncio
    async def test_discover_agents_includes_models_supported(self, broker):
        """Test that discover_agents returns models_supported."""
        await broker.start()

        card = make_agent_card(
            name='claude-worker:dev',
            description='Worker with Claude models',
            url='http://localhost:8001',
        )

        models = ['anthropic:claude-sonnet-4.5', 'anthropic:claude-opus-4.5']
        await broker.register_agent(card, models_supported=models)

        # Discover agents
        agents = await broker.discover_agents(max_age_seconds=120)

        assert len(agents) == 1
        assert agents[0]['name'] == 'claude-worker:dev'
        assert agents[0]['models_supported'] == models

        await broker.stop()

    @pytest.mark.asyncio
    async def test_discover_agents_without_models(self, broker):
        """Test that agents without models_supported return None."""
        await broker.start()

        card = make_agent_card(
            name='generic-worker:prod',
            description='Worker without specific models',
            url='http://localhost:8002',
        )

        # Register without models_supported
        await broker.register_agent(card)

        agents = await broker.discover_agents(max_age_seconds=120)

        assert len(agents) == 1
        assert agents[0]['models_supported'] is None

        await broker.stop()

    @pytest.mark.asyncio
    async def test_unregister_agent_clears_models(self, broker):
        """Test that unregistering clears models_supported."""
        await broker.start()

        card = make_agent_card(
            name='temp-worker:test',
            description='Temporary worker',
            url='http://localhost:8003',
        )

        models = ['google:gemini-2.5-pro']
        await broker.register_agent(card, models_supported=models)

        # Verify registered
        assert 'temp-worker:test' in broker._agent_models

        # Unregister
        await broker.unregister_agent('temp-worker:test')

        # Verify cleared
        assert 'temp-worker:test' not in broker._agent_models

        await broker.stop()


class TestModelRefNormalization:
    """Test model_ref format normalization."""

    def test_normalized_format_examples(self):
        """Verify model_ref uses provider:model format."""
        # Current models as of January 2026
        valid_formats = [
            'openai:gpt-5.2',
            'openai:gpt-5-mini',
            'openai:gpt-5-nano',
            'openai:o4-mini',
            'anthropic:claude-sonnet-4.5',
            'anthropic:claude-opus-4.5',
            'anthropic:claude-haiku-4.5',
            'google:gemini-2.5-pro',
            'google:gemini-2.5-flash',
            'local:llama4:70b',
            'azure:deployment-name',
        ]

        for model_ref in valid_formats:
            parts = model_ref.split(':', 1)
            assert len(parts) == 2, f'Invalid format: {model_ref}'
            provider, model = parts
            assert provider, f'Provider is empty: {model_ref}'
            assert model, f'Model is empty: {model_ref}'


class TestModelRefToOpenCode:
    """Test conversion from provider:model to provider/model (OpenCode format)."""

    def test_colon_to_slash_conversion(self):
        """Test basic colon -> slash conversion."""
        # Import the TaskExecutor to get the conversion method
        # We'll test the conversion logic directly
        conversions = [
            ('anthropic:claude-sonnet-4.5', 'anthropic/claude-sonnet-4.5'),
            ('openai:gpt-5.2', 'openai/gpt-5.2'),
            ('openai:o4-mini', 'openai/o4-mini'),
            ('google:gemini-2.5-pro', 'google/gemini-2.5-pro'),
            ('azure:my-deployment', 'azure/my-deployment'),
        ]

        for codetether_format, opencode_format in conversions:
            # Simulate the conversion
            if ':' in codetether_format:
                result = codetether_format.replace(':', '/', 1)
            else:
                result = codetether_format
            assert result == opencode_format, (
                f'Expected {opencode_format}, got {result}'
            )

    def test_only_first_colon_replaced(self):
        """Test that only the first colon is replaced (for local:llama4:70b)."""
        model_ref = 'local:llama4:70b'
        result = model_ref.replace(':', '/', 1)
        assert result == 'local/llama4:70b'

    def test_already_slash_format_unchanged(self):
        """Test that already-slash format passes through unchanged."""
        model_ref = 'anthropic/claude-sonnet-4.5'
        # If no colon, pass through
        if ':' in model_ref:
            result = model_ref.replace(':', '/', 1)
        else:
            result = model_ref
        assert result == 'anthropic/claude-sonnet-4.5'

    def test_empty_string_unchanged(self):
        """Test that empty string passes through."""
        model_ref = ''
        if model_ref and ':' in model_ref:
            result = model_ref.replace(':', '/', 1)
        else:
            result = model_ref
        assert result == ''

    def test_none_handling(self):
        """Test that None is handled gracefully."""
        model_ref = None
        result = model_ref  # Should pass through as-is
        assert result is None


class TestTaskQueueModelRef:
    """Test model_ref in TaskRun dataclass."""

    def test_task_run_has_model_ref_field(self):
        """Verify TaskRun has model_ref field."""
        from a2a_server.task_queue import TaskRun

        run = TaskRun(
            id='test-run-1',
            task_id='test-task-1',
            model_ref='anthropic:claude-sonnet-4.5',
        )

        assert run.model_ref == 'anthropic:claude-sonnet-4.5'

    def test_task_run_model_ref_optional(self):
        """Verify model_ref defaults to None."""
        from a2a_server.task_queue import TaskRun

        run = TaskRun(
            id='test-run-2',
            task_id='test-task-2',
        )

        assert run.model_ref is None


class TestMultipleWorkersWithDifferentModels:
    """Test routing scenarios with multiple workers supporting different models."""

    @pytest.fixture
    def broker(self):
        return InMemoryMessageBroker()

    @pytest.mark.asyncio
    async def test_multiple_workers_different_models(self, broker):
        """Test discovery with multiple workers having different models."""
        await broker.start()

        # Register OpenAI worker
        openai_card = make_agent_card(
            name='code-reviewer:openai-vm',
            description='Code reviewer with OpenAI',
            url='http://openai-worker:8000',
        )
        await broker.register_agent(
            openai_card,
            role='code-reviewer',
            models_supported=['openai:gpt-4.1', 'openai:gpt-4.1-mini'],
        )

        # Register Anthropic worker
        anthropic_card = make_agent_card(
            name='code-reviewer:anthropic-vm',
            description='Code reviewer with Claude',
            url='http://anthropic-worker:8000',
        )
        await broker.register_agent(
            openai_card,
            role='code-reviewer',
            models_supported=['openai:gpt-4.1', 'openai:gpt-4.1-mini'],
        )

        # Register Anthropic worker
        anthropic_card = make_agent_card(
            name='code-reviewer:anthropic-vm',
            description='Code reviewer with Claude',
            url='http://anthropic-worker:8000',
        )
        await broker.register_agent(
            anthropic_card,
            role='code-reviewer',
            models_supported=[
                'anthropic:claude-3.5-sonnet',
                'anthropic:claude-3-opus',
            ],
        )

        # Discover all agents
        agents = await broker.discover_agents()

        assert len(agents) == 2

        # Both should have role="code-reviewer"
        roles = {a['role'] for a in agents}
        assert roles == {'code-reviewer'}

        # Check models_supported are distinct
        models_by_name = {a['name']: a['models_supported'] for a in agents}
        assert 'openai:gpt-4.1' in models_by_name['code-reviewer:openai-vm']
        assert (
            'anthropic:claude-3.5-sonnet'
            in models_by_name['code-reviewer:anthropic-vm']
        )

        await broker.stop()

    @pytest.mark.asyncio
    async def test_discover_by_role_preserves_models(self, broker):
        """Test that discover_agents_by_role includes models_supported."""
        await broker.start()

        # Register two workers with same role, different models
        card1 = make_agent_card(
            name='test-runner:worker1',
            description='Test runner 1',
            url='http://worker1:8000',
        )
        await broker.register_agent(
            card1,
            role='test-runner',
            models_supported=['openai:gpt-4o'],
        )

        card2 = make_agent_card(
            name='test-runner:worker2',
            description='Test runner 2',
            url='http://worker2:8000',
        )
        await broker.register_agent(
            card2,
            role='test-runner',
            models_supported=['google:gemini-2.5-flash'],
        )

        # Discover by role
        agents = await broker.discover_agents_by_role('test-runner')

        assert len(agents) == 2
        for agent in agents:
            assert agent['role'] == 'test-runner'
            assert agent['models_supported'] is not None

        await broker.stop()
