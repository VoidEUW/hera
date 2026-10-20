"""The person Hera belongs to: a name, an email and a face.

**A record, not a login.** There is still one owner and no authentication — ``current_user`` is
unchanged. This table exists so the interface has someone to greet and the rail has a card to
draw, and it is keyed by ``owner_id`` so that the login which comes later finds a row already
shaped for it. A profile (``hera_profiles``) is *one of her*; this is the opposite end of the
conversation, and the two do not share a table or a package.

The avatar's bytes live in a file (:func:`hera_home.avatar_path`); the row records only that
there is one and what it is.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field, Session, select

from hera_storage import Entity

ACCOUNT_TABLE = "core_accounts"

AVATAR_TYPES: dict[str, bytes] = {
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
    "image/gif": b"GIF8",
    "image/webp": b"RIFF",
}
"""The picture types an image attachment may be, with the first bytes each one starts with.
The declared type and the bytes have to agree: a file served back with a type it is not is how
an upload becomes something else."""

MAX_AVATAR_BYTES = 12 * 1024 * 1024
"""The same ceiling as an image attachment in the interface."""


class Account(Entity, table=True):
    """One row per owner."""

    __tablename__ = ACCOUNT_TABLE
    __table_args__ = (UniqueConstraint("owner_id"), Index(None, "created_at", "id"))

    owner_id: UUID = Field(index=True)
    name: str = ""
    email: str = ""
    avatar_type: str = ""
    """The media type of the stored avatar, or empty when there is none."""


def account_for(session: Session, owner_id: UUID) -> Account:
    """The owner's row, created empty the first time it is asked for.

    Created on read rather than at boot, so an install that never opens the Account screen
    never has one — and a reader never has to ask whether it exists.
    """
    found = session.exec(select(Account).where(Account.owner_id == owner_id)).first()
    if found is not None:
        return found
    created = Account(owner_id=owner_id)
    session.add(created)
    session.flush()
    return created


def sniffs_as(media_type: str, data: bytes) -> bool:
    """Whether ``data`` begins the way ``media_type`` says it does."""
    magic = AVATAR_TYPES.get(media_type)
    if magic is None or not data.startswith(magic):
        return False
    return media_type != "image/webp" or data[8:12] == b"WEBP"
