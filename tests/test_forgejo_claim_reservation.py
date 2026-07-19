import pytest

from a2a_server import forgejo_claim_reservation as reservation


class Connection:
    def __init__(self) -> None:
        self.status = 'pending'
        self.worker_id = None

    async def execute(self, _query: str, _task_id: str, worker_id: str) -> str:
        if self.status == 'pending' and self.worker_id is None:
            self.status = 'running'
            self.worker_id = worker_id
            return 'UPDATE 1'
        return 'UPDATE 0'

    async def fetchrow(self, _query: str, _task_id: str) -> dict[str, object]:
        return {'status': self.status, 'worker_id': self.worker_id}


class Context:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection

    async def __aenter__(self) -> Connection:
        return self.connection

    async def __aexit__(self, *_args: object) -> None:
        return None


class Pool:
    def __init__(self) -> None:
        self.connection = Connection()

    def acquire(self) -> Context:
        return Context(self.connection)


@pytest.mark.asyncio
async def test_only_one_worker_can_reserve_a_verified_task(monkeypatch):
    pool = Pool()
    monkeypatch.setattr(reservation.db, 'get_pool', lambda: async_value(pool))
    assert await reservation.reserve('cttask_1', 'worker-1') == 'acquired'
    assert await reservation.reserve('cttask_1', 'worker-2') == 'unavailable'
    assert await reservation.reserve('cttask_1', 'worker-1') == 'owned'


async def async_value(value: object) -> object:
    return value
