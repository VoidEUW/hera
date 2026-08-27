"""Types the skillsets fixtures hand out.

Not in `conftest.py`, and not because it would not fit there: mypy is configured to skip
`tests/conftest.py` outright (two packages' conftests resolve to one module name, and mypy has
no by-path loading the way pytest does). A type alias declared there is invisible to every test
that imports it, so the alias lives in a module mypy does read.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class WriteSkill(Protocol):
    """Writes a skill directory under the temporary skills path and returns it."""

    def __call__(
        self,
        skill_id: str,
        *,
        description: str = ...,
        body: str = ...,
        name: str | None = ...,
        frontmatter: str | None = ...,
        extra: dict[str, str] | None = ...,
    ) -> Path: ...
