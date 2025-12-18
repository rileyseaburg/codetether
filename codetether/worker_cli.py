"""Console entrypoint for the CodeTether agent worker.

This wraps `agent_worker.worker` so users can run:
- `codetether-worker --config /etc/a2a-worker/config.json`

The worker uses argparse internally; this wrapper just bridges the
async entrypoint for console_scripts.
"""

from __future__ import annotations

import asyncio
import sys


def _get_version() -> str:
    try:
        from importlib.metadata import version

        return version("codetether")
    except Exception:
        try:
            from codetether import __version__

            return __version__
        except Exception:
            return "unknown"


def _print_about() -> None:
    v = _get_version()
    print(f"CodeTether Worker {v}")
    print("\nOpenCode integration")
    print("- The worker executes tasks using an 'opencode'-compatible CLI on the worker machine.")
    print("- This project maintains and tests against a fork of OpenCode (see the repo's 'opencode/' directory).")
    print("\nUpstream credit")
    print("- OpenCode: https://opencode.ai (by its upstream authors and contributors)")
    print("- CodeTether is not affiliated with the upstream OpenCode project.")


def main() -> None:
    if any(arg in {"--version", "-V"} for arg in sys.argv[1:]):
        # Keep --version machine-friendly (prints only the version string).
        print(_get_version())
        return

    if any(arg == "--about" for arg in sys.argv[1:]):
        _print_about()
        return

    from agent_worker.worker import main as async_main  # async def main()

    asyncio.run(async_main())


if __name__ == "__main__":
    main()
