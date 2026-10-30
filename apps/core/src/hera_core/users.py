"""Accounts managed by an admin: ``hera user …`` on the host, and removing somebody entirely.

Its own module so the CLI stays a parser. Every verb opens the database the way the server
would — refusing an old directory or a database ahead of this build — and commits only when it
has done all of what it was asked.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Callable
from uuid import UUID

from sqlmodel import Session, col, delete, select

from hera_accounts import AccountError, Accounts, Role, User
from hera_chats import Chat, Message, Project, TurnUsage
from hera_core.boot import check_home, check_revision
from hera_core.chat_files import forget_chat
from hera_core.claim import claim_as_admin, claimed, unclaimed
from hera_core.migrations import upgrade_to_head
from hera_core.settings import CoreSettings
from hera_home import user_dir
from hera_profiles import Profile
from hera_skillsets import SkillUsage
from hera_storage import Database, StorageSettings


def run(
    args: argparse.Namespace, settings: CoreSettings, *, read_password: Callable[[], str]
) -> int:
    check_home()
    database = Database(StorageSettings(url=settings.database_url()))
    try:
        check_revision(database)
        upgrade_to_head(database)
        return _verb(args, settings, database, read_password)
    except (AccountError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        database.dispose()


OWNED = (Message, TurnUsage, Chat, Project, Profile, SkillUsage)
"""Every table with a row a person made. Deleted, not revoked: an admin removing somebody is
removing what they said, and a soft-deleted row is what they said, still on the disk."""


def remove(session: Session, user: User) -> list[UUID]:
    """Delete an account and every row of theirs, in the caller's unit of work. Returns the ids
    of their chats, whose directories :func:`remove_files` takes once that work has committed —
    files go last, because a commit that fails must not have taken them already.

    Refuses the last admin, through :meth:`Accounts.delete`.
    """
    chats = list(session.exec(select(Chat.id).where(Chat.owner_id == user.id)))
    Accounts(session).delete(user)
    for table in OWNED:
        session.exec(delete(table).where(col(table.owner_id) == user.id))
    session.flush()
    return chats


def remove_files(user_id: UUID, chats: list[UUID]) -> None:
    """Their chats' directories and everything under ``users/<id>/`` — the mind, the memories,
    their rules, the picture. Best effort, like :func:`hera_core.chat_files.forget_chat`."""
    for chat_id in chats:
        forget_chat(str(chat_id))
    shutil.rmtree(user_dir(str(user_id)), ignore_errors=True)


def _verb(
    args: argparse.Namespace,
    settings: CoreSettings,
    database: Database,
    read_password: Callable[[], str],
) -> int:
    with database.session() as session:
        accounts = Accounts(session)

        if args.verb == "list":
            users = accounts.users()
            if not users:
                print("No accounts yet. Open Hera to set it up, or: hera user create --role admin")
            for user in users:
                notes = [
                    note
                    for note, applies in (
                        ("disabled", user.disabled),
                        ("no password", not accounts.has_password(user.id)),
                    )
                    if applies
                ]
                sessions = len(accounts.sessions(user.id))
                print(
                    f"{user.email or '(no email)'}\t{user.role}\t{user.name}\t"
                    f"{sessions} signed in{' · ' + ', '.join(notes) if notes else ''}"
                )
            return 0

        if args.verb == "create":
            if unclaimed(session):
                if args.role != "admin":
                    raise AccountError(
                        "nobody can sign in yet, so the first account has to be an admin "
                        "(--role admin)"
                    )
                # The same act as the wizard's first step: the first admin takes the owner id,
                # so an existing install's chats are theirs.
                claim_as_admin(
                    session,
                    settings.owner_id,
                    email=args.email,
                    name=args.name,
                    password=read_password(),
                )
            else:
                accounts.create(
                    args.email, name=args.name, role=Role(args.role), password=read_password()
                )
            print(f"Created {args.email.strip().lower()} as {args.role}.")
            return 0

        account = accounts.by_email(args.email)
        if account is None:
            raise AccountError(f"there is no account for {args.email}")

        if args.verb == "reset-password":
            accounts.set_password(account.id, read_password())
            signed_out = accounts.close_sessions(account.id)
            # Somebody can sign in now, if nobody could before: a setup code must stop working.
            claimed(session)
            print(f"New password set for {account.email}; signed out of {signed_out} session(s).")
            return 0

        accounts.set_role(account, Role(args.role))
        print(f"{account.email} is now {'an admin' if args.role == 'admin' else 'a user'}.")
        return 0
