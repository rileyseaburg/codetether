"""Read-only aggregate storage diagnostics; no worker payloads or credentials printed."""
import asyncio
import json
import os
import asyncpg


async def main():
    connection = await asyncpg.connect(os.environ['DATABASE_URL'], timeout=15)
    try:
        rows = await connection.fetch("""
            SELECT (last_seen >= NOW() - INTERVAL '24 hours') AS recent,
                   count(*) AS workers,
                   coalesce(sum(octet_length(models::text)), 0) AS model_json_bytes,
                   coalesce(max(octet_length(models::text)), 0) AS largest_catalog_bytes
            FROM workers GROUP BY recent
        """)
        print(json.dumps([dict(row) for row in rows], default=str))
        table = await connection.fetchrow("""
            SELECT count(*) AS workspaces,
                   coalesce(sum(octet_length(agent_config::text)), 0) AS config_bytes
            FROM workspaces
        """)
        print(json.dumps(dict(table), default=str))
    finally:
        await connection.close()


asyncio.run(main())