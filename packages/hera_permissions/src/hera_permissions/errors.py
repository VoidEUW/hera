"""Error hierarchy of the library.

These do not derive from ``ValueError`` on purpose: raised inside a pydantic validator, a
``ValueError`` comes back wrapped in a ``ValidationError`` and the actual complaint is buried.
A malformed rule should say it is a malformed rule.
"""

from __future__ import annotations


class PermissionsError(Exception):
    """Base class for every error raised by ``hera_permissions``."""


class InvalidPattern(PermissionsError):
    """A rule was given a pattern that can never match anything useful."""
