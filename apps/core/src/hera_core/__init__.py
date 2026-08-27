"""hera-core — the application.

A FastAPI JSON and Server-Sent Events API at ``/api/v1``, and the SvelteKit interface it serves
from the same origin. This is the one package that legitimately imports every library; nothing
may import it back, and ``tests/test_layering.py`` checks that.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
