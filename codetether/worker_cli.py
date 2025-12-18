"""Console entrypoint for the CodeTether agent worker.

This wraps `agent_worker.worker` so users can run:
- `codetether-worker --config /etc/a2a-worker/config.json`

The worker uses argparse internally; this wrapper just bridges the
async entrypoint for console_scripts.
"""

from __future__ import annotations

import asyncio
import sys


def main() -> None:
    if any(arg in {"--version", "-V"} for arg in sys.argv[1:]):
        try:
            from importlib.metadata import version

            print(version("codetether"))
        except Exception:
            try:
                from codetether import __version__

                print(__version__)
            except Exception:
                print("unknown")
        return

    from agent_worker.worker import main as async_main  # async def main()

    asyncio.run(async_main())


if __name__ == "__main__":
    main()
