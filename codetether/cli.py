"""Console entrypoint for CodeTether.

Goal: `pip install codetether` then run:
- `codetether` (defaults to starting the server)
- `codetether run ...` (passes through)
- `codetether multi` / `codetether examples`

Implementation intentionally wraps the existing `run_server.py` interface
to avoid duplicating server-runner logic.
"""

from __future__ import annotations

import sys


_RUN_SERVER_COMMANDS = {"run", "multi", "examples"}


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
    print(f"CodeTether {v}")
    print("\nOpenCode integration")
    print("- CodeTether integrates with an 'opencode'-compatible CLI for AI coding agents.")
    print("- This project maintains and tests against a fork of OpenCode (see the repo's 'opencode/' directory).")
    print("- You can also point CodeTether at another compatible 'opencode' binary via configuration.")
    print("\nUpstream credit")
    print("- OpenCode: https://opencode.ai (by its upstream authors and contributors)")
    print("- CodeTether is not affiliated with the upstream OpenCode project.")


def _normalize_argv(argv: list[str]) -> list[str]:
    # argv is sys.argv (including program name at [0]).
    args = argv[1:]

    if not args:
        # Most user-friendly: just start a single server.
        return [argv[0], "run"]

    head = args[0]

    # Common friendly aliases.
    if head in {"server", "serve", "start"}:
        return [argv[0], "run", *args[1:]]

    # Allow `codetether --port 8000` etc by defaulting to the run subcommand.
    if head.startswith("-"):
        return [argv[0], "run", *args]

    # Pass-through to existing subcommands.
    if head in _RUN_SERVER_COMMANDS:
        return argv

    # If user typed something else, keep compatibility with run_server's help.
    return argv


def main() -> None:
    # Keep --version machine-friendly (prints only the version string).
    if any(arg in {"--version", "-V"} for arg in sys.argv[1:]):
        print(_get_version())
        return

    # Human-friendly branding + attribution.
    if any(arg == "--about" for arg in sys.argv[1:]) or (len(sys.argv) > 1 and sys.argv[1] in {"about", "info"}):
        _print_about()
        return

    # `run_server` is installed as a top-level module via setup.py (py_modules).
    import run_server  # type: ignore

    sys.argv = _normalize_argv(sys.argv)
    run_server.main()


if __name__ == "__main__":
    main()
