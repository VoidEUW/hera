"""Canonical JSON encoding, shared by every fingerprint in the library.

Determinism is a contract: the same object must always hash to the same digest, so
keys are sorted at every level and the separators are fixed.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    """Encode ``payload`` with sorted keys and no incidental whitespace."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_hex(payload: Any) -> str:
    """Return the SHA-256 hex digest over the canonical JSON encoding of ``payload``."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
