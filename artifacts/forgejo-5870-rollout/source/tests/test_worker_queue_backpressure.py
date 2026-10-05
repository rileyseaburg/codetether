"""Tests for bounded worker SSE queue (Phase 2 backpressure)."""

import asyncio

import pytest

from a2a_server.worker_queue import (
    WORKER_QUEUE_MAXSIZE,
    make_worker_queue,
    try_enqueue,
)


def test_make_worker_queue_is_bounded():
    q = make_worker_queue()
    assert q.maxsize == WORKER_QUEUE_MAXSIZE


@pytest.mark.asyncio
async def test_try_enqueue_succeeds_with_room():
    q = asyncio.Queue(maxsize=2)
    assert try_enqueue(q, {'event': 'progress'}, 'w1') is True
    assert q.qsize() == 1


@pytest.mark.asyncio
async def test_try_enqueue_drops_when_full():
    q = asyncio.Queue(maxsize=1)
    assert try_enqueue(q, {'event': 'progress', 'data': 1}, 'w1') is True
    # second put would block an unbounded queue forever; here it drops
    assert try_enqueue(q, {'event': 'progress', 'data': 2}, 'w1') is False
    assert q.qsize() == 1
    # the retained item is the first one (no overwrite)
    assert q.get_nowait()['data'] == 1
