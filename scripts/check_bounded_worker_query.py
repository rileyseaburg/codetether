"""Execute the deployed bulk query and report aggregate bounds, never payloads."""
import ast
import asyncio
import json
import os
from pathlib import Path
import asyncpg


async def main():
    source = ast.parse(Path('/app/a2a_server/database.py').read_text())
    function = next(node for node in source.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'db_list_workers')
    query = next(node.value.value for node in ast.walk(function)
                 if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                 and any(isinstance(t, ast.Name) and t.id == 'query' for t in node.targets))
    assert "CASE WHEN last_seen" in query
    conn = await asyncpg.connect(os.environ['DATABASE_URL'], timeout=15)
    try:
        rows = await conn.fetch(query)
        persisted = await conn.fetchrow("SELECT count(*) AS workers, sum(octet_length(models::text)) AS bytes FROM workers")
        returned_bytes = sum(len(row['models'] or '') for row in rows)
        assert len(rows) == persisted['workers']
        assert returned_bytes < 5_000_000
        print(json.dumps({'workers_preserved': len(rows), 'stored_model_bytes': persisted['bytes'],
                          'bulk_model_bytes': returned_bytes, 'bounded': True}, default=str))
    finally:
        await conn.close()


asyncio.run(main())



