"""What a person's picture may be.

The person themselves is a ``hera_accounts.User`` (ADR 27); what is left here is the part that
is about bytes arriving over HTTP. The avatar lives in a file (:func:`hera_home.avatar_path`)
and the user row records only that there is one and what type it is.
"""

from __future__ import annotations

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


def sniffs_as(media_type: str, data: bytes) -> bool:
    """Whether ``data`` begins the way ``media_type`` says it does."""
    magic = AVATAR_TYPES.get(media_type)
    if magic is None or not data.startswith(magic):
        return False
    return media_type != "image/webp" or data[8:12] == b"WEBP"
