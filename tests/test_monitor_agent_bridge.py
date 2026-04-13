import os

os.environ.setdefault(
    'DATABASE_URL',
    'postgresql://postgres:postgres@localhost:5432/a2a_server',
)

from a2a_server import agent_bridge, monitor_api


def test_monitor_api_uses_shared_agent_bridge(monkeypatch):
    async def fake_deduplicate():
        return {}

    monitor_api._agent_bridge = None
    monitor_api._agent_bridge_initialized = False
    agent_bridge._bridge = None
    monkeypatch.setattr(
        monitor_api.db,
        'db_deduplicate_all_workspaces',
        fake_deduplicate,
    )

    bridge = monitor_api.get_agent_bridge()

    assert bridge is agent_bridge.get_agent_bridge()
