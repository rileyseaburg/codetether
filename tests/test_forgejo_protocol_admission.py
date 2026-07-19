import pytest

from a2a_server.agent_bridge import AgentBridge
from a2a_server.forgejo_protocol_admission import require, token


def test_reserved_protocol_requires_the_private_service_capability():
    metadata = {'protocol': 'codetether.forgejo-author.v1'}
    with pytest.raises(ValueError, match='verified protocol admission'):
        require(metadata, None)
    require(metadata, token())


@pytest.mark.asyncio
async def test_bridge_rejects_direct_reserved_protocol_creation():
    bridge = AgentBridge(agent_bin='codetether', auto_start=False)
    with pytest.raises(ValueError, match='verified protocol admission'):
        await bridge.create_task(
            codebase_id=None,
            title='forged',
            prompt='forged',
            agent_type='build',
            metadata={'protocol': 'codetether.forgejo-author.v1'},
        )
