"""hera-core — the application.

A FastAPI JSON and Server-Sent Events API at ``/api/v1``, and the SvelteKit interface it serves
from the same origin. This is the one package that legitimately imports every library; nothing
may import it back, and ``tests/test_layering.py`` checks that.

**One version, read from the installed distribution.** ``pyproject.toml`` declares it, packaging
records it, and this reads it back — so the number in an About box, in ``hera --version`` and on
a built wheel cannot disagree, which is what a hand-maintained ``__version__ = "0.1.0"`` beside
a ``version = "0.1.0"`` eventually does. ``release.yml`` refuses a ``v1.2.3`` tag that does not
match what is declared, so the tag cannot drift from it either.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _installed

DISTRIBUTION = "hera-core"

try:
    __version__ = _installed(DISTRIBUTION)
except PackageNotFoundError:  # pragma: no cover - only when running from an unbuilt tree
    # Not an error worth raising: the API still answers, and "unknown" on an About screen is
    # more honest than a number somebody typed once and stopped maintaining.
    __version__ = "0+unknown"

__all__ = ["DISTRIBUTION", "__version__"]
