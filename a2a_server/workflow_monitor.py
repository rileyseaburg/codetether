from datetime import datetime, timezone
from typing import Any, Dict

from . import workflow_monitor_builders as build
from . import workflow_monitor_sql as sql
from .workflow_monitor_types import parse_repo_filters


async def load_tetherscript_workflows(
    pool: Any,
    repos: str | None,
    limit: int,
    tenant_id: str | None = None,
) -> Dict[str, Any]:
    repo_filters = parse_repo_filters(repos)
    row_limit = max(1, min(limit, 1000))
    async with pool.acquire() as conn:
        counts = await conn.fetch(sql.COUNTS_SQL, repo_filters, tenant_id)
        workflows = await conn.fetch(
            sql.WORKFLOWS_SQL, repo_filters, tenant_id, row_limit
        )
        tasks = await conn.fetch(sql.TASK_ROWS_SQL, repo_filters, tenant_id, row_limit)
        runs = await conn.fetch(sql.RUN_ROWS_SQL, repo_filters, tenant_id, row_limit)
    return build_response(repo_filters, counts, workflows, tasks, runs)


def build_response(
    repo_filters: list[str],
    count_rows: Any,
    workflow_rows: Any,
    task_rows: Any,
    run_rows: Any,
) -> Dict[str, Any]:
    tasks = [build.task(row) for row in task_rows]
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'repos': repo_filters,
        'counts_by_repo': build.counts_by_repo(count_rows),
        'totals': build.totals(count_rows),
        'route_states': build.route_states(tasks),
        'failure_classes': build.failure_classes(tasks),
        'workflows': [build.workflow(row) for row in workflow_rows],
        'tasks': tasks,
        'runs': [build.run(row) for row in run_rows],
    }
