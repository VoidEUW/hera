"""The ``db`` and ``session`` fixtures come from the installed pytest11 plugin.

This conftest only makes sure the dummy models are imported before any fixture runs, so
``create_all()`` sees their tables.
"""

from __future__ import annotations

import models  # noqa: F401
