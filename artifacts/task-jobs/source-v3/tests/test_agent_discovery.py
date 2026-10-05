"""
Tests for agent discovery with role:instance pattern and TTL cleanup.

Run with: pytest tests/test_agent_discovery.py -v

Note: These tests use the InMemoryMessageBroker which mimics Redis behavior
without requiring Redis to be running.
"""

import asyncio
import sys
import os

# Add parent dir to path to avoid __init__.py import chain
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock

# Import directly from modules to avoid server.py import chain
from a2a_server.message_broker import InMemoryMessageBroker
from a2a_server.models import AgentCard, AgentCapabilities, AgentProvider


@pytest.fixture
def broker():
    """Create an in-memory broker for testing."""
    return InMemoryMessageBroker()


@pytest.fixture
def make_agent_card():
    """Factory for creating test agent cards."""

    def _make(name: str, description: str = 'Test agent') -> AgentCard:
        return AgentCard(
            name=name,
            description=description,
            url=f'http://localhost:8000/{name}',
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

    return _make


class TestAgentDiscoveryRoleInstance:
    """Tests for role:instance pattern in agent discovery."""

    @pytest.mark.asyncio
    async def test_register_extracts_role_from_name(
        self, broker, make_agent_card
    ):
        """Role should be extracted from name pattern 'role:instance'."""
        await broker.start()

        card = make_agent_card('code-reviewer:dev-vm:abc123')
        await broker.register_agent(card)

        agents = await broker.discover_agents(max_age_seconds=0)
        assert len(agents) == 1
        assert agents[0]['name'] == 'code-reviewer:dev-vm:abc123'
        assert agents[0]['role'] == 'code-reviewer'
        assert agents[0]['instance_id'] == 'dev-vm:abc123'

    @pytest.mark.asyncio
    async def test_two_instances_same_role(self, broker, make_agent_card):
        """Two workers with same role should show as distinct agents."""
        await broker.start()

        card_a = make_agent_card('code-reviewer:host-a:111')
        card_b = make_agent_card('code-reviewer:host-b:222')

        await broker.register_agent(card_a)
        await broker.register_agent(card_b)

        agents = await broker.discover_agents(max_age_seconds=0)
        assert len(agents) == 2

        names = {a['name'] for a in agents}
        roles = {a['role'] for a in agents}

        assert names == {'code-reviewer:host-a:111', 'code-reviewer:host-b:222'}
        assert roles == {'code-reviewer'}  # Same role

    @pytest.mark.asyncio
    async def test_explicit_role_parameter(self, broker, make_agent_card):
        """Explicit role parameter should override name parsing."""
        await broker.start()

        card = make_agent_card('my-agent-name')
        await broker.register_agent(
            card, role='custom-role', instance_id='inst-1'
        )

        agents = await broker.discover_agents(max_age_seconds=0)
        assert len(agents) == 1
        assert agents[0]['role'] == 'custom-role'
        assert agents[0]['instance_id'] == 'inst-1'


class TestAgentDiscoveryTTL:
    """Tests for TTL filtering and stale agent cleanup."""

    @pytest.mark.asyncio
    async def test_stale_agents_filtered(self, broker, make_agent_card):
        """Agents older than max_age_seconds should be filtered."""
        await broker.start()

        card = make_agent_card('old-agent:host:123')
        await broker.register_agent(card)

        # Manually backdate last_seen
        broker._agent_last_seen['old-agent:host:123'] = (
            datetime.utcnow() - timedelta(seconds=200)
        )

        # With default max_age=120s, should be filtered
        agents = await broker.discover_agents(max_age_seconds=120)
        assert len(agents) == 0

    @pytest.mark.asyncio
    async def test_fresh_agents_included(self, broker, make_agent_card):
        """Agents within max_age_seconds should be included."""
        await broker.start()

        card = make_agent_card('fresh-agent:host:456')
        await broker.register_agent(card)

        # last_seen is now, should be included
        agents = await broker.discover_agents(max_age_seconds=120)
        assert len(agents) == 1
        assert agents[0]['name'] == 'fresh-agent:host:456'

    @pytest.mark.asyncio
    async def test_stale_cleanup_removes_from_registry(
        self, broker, make_agent_card
    ):
        """Stale agents should be cleaned up from internal registries."""
        await broker.start()

        card = make_agent_card('stale-agent:host:789')
        await broker.register_agent(card)

        # Verify registered
        assert 'stale-agent:host:789' in broker._agents

        # Backdate to make stale
        broker._agent_last_seen['stale-agent:host:789'] = (
            datetime.utcnow() - timedelta(seconds=200)
        )

        # First discover should filter and cleanup
        agents = await broker.discover_agents(
            max_age_seconds=120, cleanup_stale=True
        )
        assert len(agents) == 0

        # Second discover should confirm agent is gone
        assert 'stale-agent:host:789' not in broker._agents
        assert 'stale-agent:host:789' not in broker._agent_last_seen

    @pytest.mark.asyncio
    async def test_heartbeat_refresh_keeps_agent_alive(
        self, broker, make_agent_card
    ):
        """Refreshing heartbeat should keep agent visible in discovery."""
        await broker.start()

        card = make_agent_card('heartbeat-agent:host:abc')
        await broker.register_agent(card)

        # Backdate slightly (but still within TTL)
        broker._agent_last_seen['heartbeat-agent:host:abc'] = (
            datetime.utcnow() - timedelta(seconds=100)
        )

        # Refresh heartbeat
        result = await broker.refresh_agent_heartbeat(
            'heartbeat-agent:host:abc'
        )
        assert result is True

        # Should now be fresh
        agents = await broker.discover_agents(max_age_seconds=120)
        assert len(agents) == 1

    @pytest.mark.asyncio
    async def test_heartbeat_unknown_agent_returns_false(self, broker):
        """Refreshing heartbeat for unknown agent should return False."""
        await broker.start()

        result = await broker.refresh_agent_heartbeat('nonexistent-agent')
        assert result is False


class TestAgentDiscoveryByRole:
    """Tests for role-based discovery."""

    @pytest.mark.asyncio
    async def test_discover_by_role(self, broker, make_agent_card):
        """discover_agents_by_role should return only agents with matching role."""
        await broker.start()

        # Register agents with different roles
        await broker.register_agent(make_agent_card('code-reviewer:host-a:1'))
        await broker.register_agent(make_agent_card('code-reviewer:host-b:2'))
        await broker.register_agent(make_agent_card('test-runner:host-c:3'))

        # Query by role
        reviewers = await broker.discover_agents_by_role('code-reviewer')
        runners = await broker.discover_agents_by_role('test-runner')

        assert len(reviewers) == 2
        assert len(runners) == 1
        assert all(a['role'] == 'code-reviewer' for a in reviewers)
        assert all(a['role'] == 'test-runner' for a in runners)

    @pytest.mark.asyncio
    async def test_discover_by_role_excludes_stale(
        self, broker, make_agent_card
    ):
        """discover_agents_by_role should exclude stale agents."""
        await broker.start()

        await broker.register_agent(make_agent_card('code-reviewer:host-a:1'))
        await broker.register_agent(make_agent_card('code-reviewer:host-b:2'))

        # Make one stale
        broker._agent_last_seen['code-reviewer:host-a:1'] = (
            datetime.utcnow() - timedelta(seconds=200)
        )

        reviewers = await broker.discover_agents_by_role('code-reviewer')
        assert len(reviewers) == 1
        assert reviewers[0]['name'] == 'code-reviewer:host-b:2'


class TestClockSkewTolerance:
    """Tests for clock skew tolerance."""

    @pytest.mark.asyncio
    async def test_future_timestamp_treated_as_fresh(
        self, broker, make_agent_card
    ):
        """Agents with future last_seen (clock skew) should be treated as fresh."""
        await broker.start()

        card = make_agent_card('future-agent:host:123')
        await broker.register_agent(card)

        # Simulate clock skew: worker clock is 30s ahead of server
        broker._agent_last_seen['future-agent:host:123'] = (
            datetime.utcnow() + timedelta(seconds=30)
        )

        # Should still be included (not filtered as stale)
        agents = await broker.discover_agents(max_age_seconds=120)
        assert len(agents) == 1
        assert agents[0]['name'] == 'future-agent:host:123'


class TestReRegistration:
    """Tests for re-registration scenarios."""

    @pytest.mark.asyncio
    async def test_reregister_updates_last_seen(self, broker, make_agent_card):
        """Re-registering same agent should update last_seen."""
        await broker.start()

        card = make_agent_card('reregister-agent:host:123')

        # Initial registration
        await broker.register_agent(card)
        initial_last_seen = broker._agent_last_seen['reregister-agent:host:123']

        # Wait a tiny bit
        await asyncio.sleep(0.01)

        # Re-register
        await broker.register_agent(card)
        new_last_seen = broker._agent_last_seen['reregister-agent:host:123']

        assert new_last_seen > initial_last_seen

    @pytest.mark.asyncio
    async def test_reregister_no_duplicate_entries(
        self, broker, make_agent_card
    ):
        """Re-registering same agent should not create duplicates."""
        await broker.start()

        card = make_agent_card('unique-agent:host:456')

        await broker.register_agent(card)
        await broker.register_agent(card)
        await broker.register_agent(card)

        agents = await broker.discover_agents(max_age_seconds=0)
        assert len(agents) == 1
