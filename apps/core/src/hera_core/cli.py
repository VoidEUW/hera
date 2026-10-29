"""``hera`` on the command line.

A handful of verbs, no framework. ``argparse`` is in the standard library, this is not a
general-purpose tool, and a dependency whose value is nicer ``--help`` output is not worth a
line in the lockfile.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Sequence

from hera_core import __version__
from hera_core.boot import DatabaseAhead, LegacyHome
from hera_core.settings import CoreSettings


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a status code rather than calling ``sys.exit``, so it is testable."""
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (LegacyHome, DatabaseAhead) as exc:
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

    # Accounts, from the host (ADR 27). Having a shell here is the credential, which is what
    # makes `reset-password` the way back in for an admin who forgot theirs.
    user = commands.add_parser("user", help="manage accounts").add_subparsers(
        dest="verb", required=True
    )
    user.add_parser("list", help="every account, with its role")
    create = user.add_parser("create", help="make an account; asks for its password")
    create.add_argument("email")
    create.add_argument("--name", default="")
    create.add_argument("--role", choices=("admin", "user"), default="user")
    create.add_argument("--password-stdin", action="store_true", help="read it from stdin")
    reset = user.add_parser("reset-password", help="set a new password and sign out everywhere")
    reset.add_argument("email")
    reset.add_argument("--password-stdin", action="store_true", help="read it from stdin")
    role = user.add_parser("set-role", help="make an account an admin, or not")
    role.add_argument("email")
    role.add_argument("role", choices=("admin", "user"))
    return parser


def _run(args: argparse.Namespace) -> int:
    settings = CoreSettings()
    if args.command == "serve":
        return _serve(settings, host=args.host, port=args.port, reload=args.reload)
    if args.command == "init":
        return _init(settings)
    if args.command == "user":
        from hera_core.users import run

        return run(args, settings, read_password=lambda: _password(args.password_stdin))
    return _check(settings)


def _serve(settings: CoreSettings, *, host: str | None, port: int | None, reload: bool) -> int:
    import uvicorn

    from hera_core.app import prepare_home

    # Prepared before the server binds, so a broken data directory is a message on the way up
    # rather than a 500 on the first request.
    code = prepare_home(settings)

    host = host or settings.host
    port = port or settings.port
    print(f"Hera is at http://{host}:{port}")
    if code is not None:
        _print_setup_code(code)
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

    code = prepare_home(settings)
    print(f"Ready. Your data is in {home()}.")
    if code is not None:
        _print_setup_code(code)
    return 0


def _print_setup_code(code: str) -> None:
    from hera_home import setup_code_path

    print(
        f"Nobody can sign in yet. Open Hera to set it up; from another machine it will ask for\n"
        f"this setup code (also in {setup_code_path()}):\n\n    {code}\n",
        flush=True,
    )


def _password(from_stdin: bool) -> str:
    """Asked for twice at a terminal; read once from stdin for a script. Never an argument —
    an argument is in the shell's history and in every process listing."""
    if from_stdin:
        return sys.stdin.readline().rstrip("\n")
    first = getpass.getpass("New password: ")
    if getpass.getpass("Once more: ") != first:
        raise PasswordMismatch("the two passwords were not the same")
    return first


class PasswordMismatch(ValueError):
    pass


def _check(settings: CoreSettings) -> int:
    from hera_core.boot import check_home
    from hera_home import home

    check_home()
    print(f"{home()} looks fine.")
    return 0
