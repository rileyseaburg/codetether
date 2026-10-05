"""Ordering used when workers claim the next pending task.

A large stale backlog previously starved current work: the queue ordered by
`created_at ASC`, so @codetether always picked the oldest queued item and never
reached a freshly filed issue.
"""

from __future__ import annotations

import pytest

from a2a_server.database import (
    TASK_CLAIM_ORDER_NEWEST,
    TASK_CLAIM_ORDER_OLDEST,
    task_claim_order,
)


def test_newest_first_is_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('CODETETHER_TASK_CLAIM_ORDER', raising=False)

    assert task_claim_order() == TASK_CLAIM_ORDER_NEWEST
    assert 'created_at DESC' in task_claim_order()


@pytest.mark.parametrize('value', ['oldest', 'OLDEST', ' oldest '])
def test_oldest_restores_fifo_drain(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv('CODETETHER_TASK_CLAIM_ORDER', value)

    assert task_claim_order() == TASK_CLAIM_ORDER_OLDEST
    assert 'created_at ASC' in task_claim_order()


@pytest.mark.parametrize('value', ['newest', '', 'unexpected'])
def test_unrecognised_values_keep_newest_first(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv('CODETETHER_TASK_CLAIM_ORDER', value)

    assert task_claim_order() == TASK_CLAIM_ORDER_NEWEST


def test_priority_still_outranks_recency() -> None:
    for order in (TASK_CLAIM_ORDER_NEWEST, TASK_CLAIM_ORDER_OLDEST):
        assert order.startswith('priority DESC')
