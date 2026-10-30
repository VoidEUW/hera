"""Users, passwords, sessions and one-time tokens, against a real database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from argon2 import PasswordHasher
from sqlmodel import Session, select

from hera_accounts import (
    AccountError,
    Accounts,
    EmailTaken,
    LastAdmin,
    OneTimeToken,
    Password,
    Purpose,
    Role,
    SignIn,
    digest,
    normalise_email,
)

# Cheap parameters: what is being tested is the bookkeeping, not argon2's cost.
FAST = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)


class Clock:
    def __init__(self) -> None:
        self.at = datetime(2026, 10, 29, 12, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.at


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def accounts(session: Session, clock: Clock) -> Accounts:
    return Accounts(session, hasher=FAST, now=clock)


def test_an_email_is_one_person_whatever_its_case(accounts: Accounts) -> None:
    created = accounts.create(" Ana@Example.com ", name="Ana")
    assert created.email == "ana@example.com"
    assert accounts.by_email("ANA@example.COM") == created
    with pytest.raises(EmailTaken):
        accounts.create("ana@example.com")


def test_something_that_is_not_an_address_is_refused() -> None:
    with pytest.raises(AccountError):
        normalise_email("ana")


def test_a_password_is_stored_as_argon2id_and_never_as_itself(
    accounts: Accounts, session: Session
) -> None:
    user = accounts.create("ana@example.com", password="correct horse")
    stored = session.exec(select(Password)).one()
    assert stored.user_id == user.id
    assert stored.hash.startswith("$argon2id$")
    assert "correct horse" not in stored.hash


def test_verify_answers_none_for_every_way_of_being_wrong(accounts: Accounts) -> None:
    user = accounts.create("ana@example.com", password="correct horse")
    accounts.create("ben@example.com")  # no password at all

    assert accounts.verify("ana@example.com", "correct horse") == user
    assert accounts.verify("ana@example.com", "wrong horse") is None
    assert accounts.verify("nobody@example.com", "correct horse") is None
    assert accounts.verify("ben@example.com", "") is None

    accounts.create("cy@example.com", role=Role.ADMIN)
    accounts.set_disabled(user, True)
    assert accounts.verify("ana@example.com", "correct horse") is None


def test_a_short_password_is_refused(accounts: Accounts) -> None:
    with pytest.raises(AccountError, match="at least"):
        accounts.create("ana@example.com", password="short")


def test_verify_rehashes_a_password_stored_with_older_parameters(
    session: Session, clock: Clock
) -> None:
    Accounts(session, hasher=FAST, now=clock).create("ana@example.com", password="correct horse")
    stronger = PasswordHasher(time_cost=2, memory_cost=16, parallelism=1)
    assert Accounts(session, hasher=stronger, now=clock).verify("ana@example.com", "correct horse")
    assert not stronger.check_needs_rehash(session.exec(select(Password)).one().hash)


def test_any_credential_is_what_says_the_instance_is_claimed(accounts: Accounts) -> None:
    user = accounts.create("ana@example.com", role=Role.ADMIN)
    assert not accounts.any_credential()
    accounts.set_password(user.id, "correct horse")
    assert accounts.any_credential()
    assert accounts.has_password(user.id)


def test_a_session_token_is_stored_only_as_its_digest(accounts: Accounts, session: Session) -> None:
    user = accounts.create("ana@example.com")
    token, sign_in = accounts.open_session(user.id, user_agent="Firefox")
    assert sign_in.token_hash == digest(token)
    assert token not in {row.token_hash for row in session.exec(select(SignIn))}
    assert accounts.resolve(token) == (user, sign_in)
    assert accounts.resolve("not-a-token") is None
    assert accounts.resolve("") is None


def test_a_session_that_is_used_stays_and_one_that_is_not_expires(
    accounts: Accounts, clock: Clock
) -> None:
    user = accounts.create("ana@example.com")
    token, sign_in = accounts.open_session(user.id, lifetime=timedelta(days=30))

    clock.at += timedelta(days=20)
    assert accounts.resolve(token, lifetime=timedelta(days=30)) is not None
    assert sign_in.last_seen_at == clock.at
    clock.at += timedelta(days=20)
    assert accounts.resolve(token, lifetime=timedelta(days=30)) is not None

    clock.at += timedelta(days=31)
    assert accounts.resolve(token) is None
    assert accounts.sessions(user.id) == []


def test_last_seen_is_not_written_on_every_request(accounts: Accounts, clock: Clock) -> None:
    user = accounts.create("ana@example.com")
    token, sign_in = accounts.open_session(user.id)
    opened = sign_in.last_seen_at
    clock.at += timedelta(minutes=1)
    accounts.resolve(token)
    assert sign_in.last_seen_at == opened


def test_a_disabled_account_has_no_session(accounts: Accounts) -> None:
    accounts.create("admin@example.com", role=Role.ADMIN)
    user = accounts.create("ana@example.com")
    token, _ = accounts.open_session(user.id)
    accounts.set_disabled(user, True)
    assert accounts.resolve(token) is None
    assert accounts.sessions(user.id) == []


def test_signing_out_is_a_deleted_row(accounts: Accounts) -> None:
    user = accounts.create("ana@example.com")
    first, _ = accounts.open_session(user.id)
    second, kept = accounts.open_session(user.id)
    third, _ = accounts.open_session(user.id)

    accounts.close_session(first)
    assert accounts.resolve(first) is None
    assert accounts.close_sessions(user.id, keep=kept.id) == 1
    assert accounts.resolve(third) is None
    assert accounts.resolve(second) is not None
    assert accounts.close_sessions(user.id) == 1


def test_one_person_cannot_revoke_anothers_session(accounts: Accounts) -> None:
    ana = accounts.create("ana@example.com")
    ben = accounts.create("ben@example.com")
    _, bens = accounts.open_session(ben.id)
    assert not accounts.revoke(ana.id, bens.id)
    assert not accounts.revoke(ana.id, uuid4())
    assert accounts.revoke(ben.id, bens.id)


def test_the_last_admin_cannot_be_demoted_or_disabled(accounts: Accounts) -> None:
    admin = accounts.create("admin@example.com", role=Role.ADMIN)
    with pytest.raises(LastAdmin):
        accounts.set_role(admin, Role.USER)
    with pytest.raises(LastAdmin):
        accounts.set_disabled(admin, True)

    other = accounts.create("ana@example.com")
    accounts.set_role(other, Role.ADMIN)
    accounts.set_role(admin, Role.USER)
    assert admin.role == Role.USER


def test_update_keeps_emails_unique(accounts: Accounts) -> None:
    ana = accounts.create("ana@example.com")
    accounts.create("ben@example.com")
    with pytest.raises(EmailTaken):
        accounts.update(ana, email="BEN@example.com")
    accounts.update(ana, name=" Ana ", email="ana@example.org")
    assert (ana.name, ana.email) == ("Ana", "ana@example.org")
    accounts.update(ana, email="ana@example.org")


def test_the_first_admin_can_take_a_given_id(accounts: Accounts) -> None:
    fixed = uuid4()
    assert accounts.create("ana@example.com", role=Role.ADMIN, user_id=fixed).id == fixed


def test_a_one_time_token_works_once_for_its_purpose(
    accounts: Accounts, session: Session, clock: Clock
) -> None:
    token = accounts.issue(Purpose.SETUP, lifetime=timedelta(hours=1))
    assert session.exec(select(OneTimeToken)).one().token_hash == digest(token)

    assert accounts.redeem(Purpose.INVITE, token) is None
    assert accounts.redeem(Purpose.SETUP, token) is not None
    assert accounts.redeem(Purpose.SETUP, token) is None
    assert accounts.redeem(Purpose.SETUP, "") is None

    late = accounts.issue(Purpose.SETUP, lifetime=timedelta(hours=1))
    clock.at += timedelta(hours=2)
    assert accounts.redeem(Purpose.SETUP, late) is None


def test_withdrawing_a_purpose_leaves_spent_tokens_alone(accounts: Accounts) -> None:
    spent = accounts.issue(Purpose.SETUP, lifetime=timedelta(hours=1))
    accounts.redeem(Purpose.SETUP, spent)
    waiting = accounts.issue(Purpose.SETUP, lifetime=timedelta(hours=1))
    accounts.issue(Purpose.INVITE, lifetime=timedelta(hours=1))
    assert accounts.withdraw(Purpose.SETUP) == 1
    assert accounts.redeem(Purpose.SETUP, waiting) is None


def test_a_crafted_address_is_refused_quickly() -> None:
    """The pattern behind CodeQL's polynomial-ReDoS alert: ``!@!.`` and ``!.`` over and over. It
    took seconds before; it is refused at once now, and so is a domain with an empty label."""
    import time

    started = time.perf_counter()
    with pytest.raises(AccountError):
        normalise_email("!@!." + "!." * 5000 + "@")
    assert time.perf_counter() - started < 0.1
    for broken in ("ana@example", "ana@.com", "ana@example..com", "ana@example.com."):
        with pytest.raises(AccountError):
            normalise_email(broken)
    assert normalise_email(" Ana@Mail.Example.co.uk ") == "ana@mail.example.co.uk"
