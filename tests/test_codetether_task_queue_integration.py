"""Opt-in integration tests against a live CodeTether deployment.

These tests are intentionally skipped unless explicitly enabled, because they
create real tasks on a live server.

Enable with:
  CODETETHER_INTEGRATION=1

Optional configuration:
  CODETETHER_BASE_URL=https://api.codetether.run
  CODETETHER_CODEBASE_ID=<codebase_id>

If CODETETHER_CODEBASE_ID is not provided, the test will pick the first codebase
returned by /v1/agent/codebases/list.

The tests use the worker's lightweight agent_type='echo'/'noop' so they do not
require CodeTether/LLM credentials.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

import httpx
import pytest


def _enabled() -> bool:
    return os.environ.get("CODETETHER_INTEGRATION") == "1"


def _base_url() -> str:
    return os.environ.get("CODETETHER_BASE_URL", "https://api.codetether.run").rstrip("/")


async def _pick_codebase_id(client: httpx.AsyncClient) -> str:
    configured = os.environ.get("CODETETHER_CODEBASE_ID")
    if configured:
        return configured

    resp = await client.get("/v1/agent/codebases/list")
    resp.raise_for_status()
    codebases: List[Dict[str, Any]] = resp.json()
    if not codebases:
        raise RuntimeError("No codebases returned by /v1/agent/codebases/list")
    return str(codebases[0]["id"])


async def _poll_task(client: httpx.AsyncClient, task_id: str, timeout_s: float = 60.0) -> Dict[str, Any]:
    deadline = asyncio.get_event_loop().time() + timeout_s
    last: Optional[Dict[str, Any]] = None

    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"/v1/agent/tasks/{task_id}")
        resp.raise_for_status()
        last = resp.json()

        status = last.get("status")
        if status in ("completed", "failed", "cancelled"):
            return last

        await asyncio.sleep(1.0)

    raise TimeoutError(f"Task {task_id} did not complete within {timeout_s}s; last={last}")


@pytest.mark.asyncio
async def test_task_queue_echo_roundtrip():
    if not _enabled():
        pytest.skip("CODETETHER_INTEGRATION!=1")

    async with httpx.AsyncClient(base_url=_base_url(), timeout=30.0) as client:
        codebase_id = await _pick_codebase_id(client)

        create = await client.post(
            f"/v1/agent/codebases/{codebase_id}/tasks",
            json={
                "title": "integration: echo",
                "prompt": "worker ok",
                "agent_type": "echo",
            },
        )
        create.raise_for_status()
        task = create.json()["task"]

        final = await _poll_task(client, task["id"], timeout_s=90.0)

        assert final["status"] == "completed", final
        assert final["result"] == "worker ok"


@pytest.mark.asyncio
async def test_task_queue_noop_roundtrip():
    if not _enabled():
        pytest.skip("CODETETHER_INTEGRATION!=1")

    async with httpx.AsyncClient(base_url=_base_url(), timeout=30.0) as client:
        codebase_id = await _pick_codebase_id(client)

        create = await client.post(
            f"/v1/agent/codebases/{codebase_id}/tasks",
            json={
                "title": "integration: noop",
                "prompt": "ignored",
                "agent_type": "noop",
            },
        )
        create.raise_for_status()
        task = create.json()["task"]

        final = await _poll_task(client, task["id"], timeout_s=90.0)

        assert final["status"] == "completed", final
        assert final["result"] == "ok"
