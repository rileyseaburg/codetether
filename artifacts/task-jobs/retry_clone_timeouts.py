"""Retry native tasks that failed only because the clone timed out.

Guarded: each native task must be `failed`, be a `fix`, and its issue must be
open. Nothing is retried whose failure was anything other than the bootstrap
timeout; PR/branch state is left to the workflow.
"""

import asyncio
import json
import logging
import os
import sys

from a2a_server.forgejo_webhooks import forgejo_json


logging.disable(logging.CRITICAL)


async def main():
    """Retry only explicitly selected native tasks that are still failed."""
    base = os.environ['FORGEJO_API_URL']
    root = '/repos/riley/spotlessbinco'
    for native in sys.argv[1:]:
        task = await forgejo_json('GET', base, f'{root}/agent/tasks/{native}')
        issue = await forgejo_json(
            'GET', base, f'{root}/issues/{task["issue_index"]}'
        )
        ok = (
            task['status'] == 'failed'
            and task['operation'] == 'fix'
            and issue['state'] == 'open'
        )
        if ok:
            await forgejo_json(
                'POST', base, f'{root}/agent/tasks/{native}/retry', {}
            )
        print(
            json.dumps(
                {
                    'native_task': int(native),
                    'issue': task['issue_index'],
                    'retry_requested': ok,
                }
            )
        )


asyncio.run(main())
