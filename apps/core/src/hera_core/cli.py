"""``hera`` on the command line.

Four verbs, no framework. ``argparse`` is in the standard library, this is not a
general-purpose tool, and a dependency whose value is nicer ``--help`` output is not worth a
line in the lockfile.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from hera_core import __version__
from hera_core.boot import LegacyHome
from hera_core.settings import CoreSettings


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a status code rather than calling ``sys.exit``, so it is testable."""
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except LegacyHome as exc:
        # Not a traceback. This is a person being told to move a directory, and a stack trace
        # buries the one line that matters (ADR 7).
        print(str(exc), file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hera", description="A self-hosted agentic chat space.")
    parser.add_argument("--version", action="version", version=f"hera {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    serve = commands.add_parser("serve", help="run the application")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--reload", action="store_true", help="restart on a source change")

    commands.add_parser("init", help="prepare ~/.hera without starting the server")
    commands.add_parser("check", help="report whether the data directory is usable")
    return parser


def _run(args: argparse.Namespace) -> int:
    settings = CoreSettings()
    if args.command == "serve":
        return _serve(settings, host=args.host, port=args.port, reload=args.reload)
    if args.command == "init":
        return _init(settings)
    return _check(settings)


def _serve(settings: CoreSettings, *, host: str | None, port: int | None, reload: bool) -> int:
    import uvicorn

    from hera_core.app import prepare_home

    # Prepared before the server binds, so a broken data directory is a message on the way up
    # rather than a 500 on the first request.
    prepare_home(settings)

    host = host or settings.host
    port = port or settings.port
    print(f"Hera is at http://{host}:{port}")
    uvicorn.run(
        "hera_core.app:build_app",
        factory=True,
        host=host,
        port=port,
        reload=reload or settings.reload,
        log_level="info",
    )
    return 0


def _init(settings: CoreSettings) -> int:
    from hera_core.app import prepare_home
    from hera_home import home

    prepare_home(settings)
    print(f"Ready. Your data is in {home()}.")
    return 0


def _check(settings: CoreSettings) -> int:
    from hera_core.boot import check_home
    from hera_home import home

    check_home()
    print(f"{home()} looks fine.")
    return 0
