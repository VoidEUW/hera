"""Small guards against documentation drifting away from the repository."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADR_DIR = ROOT / "docs" / "adr"
ADR_FILE = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")


def _adrs() -> list[Path]:
    return sorted(p for p in ADR_DIR.iterdir() if ADR_FILE.match(p.name))


def test_every_decision_record_is_indexed() -> None:
    index = (ADR_DIR / "README.md").read_text(encoding="utf-8")
    missing = [p.name for p in _adrs() if p.name not in index]
    assert not missing, f"not listed in docs/adr/README.md: {missing}"


def test_decision_records_are_numbered_without_gaps() -> None:
    numbers = [int(p.name[:4]) for p in _adrs()]
    assert numbers == list(range(1, len(numbers) + 1)), f"numbering is not contiguous: {numbers}"


def test_decision_records_carry_a_status() -> None:
    for adr in _adrs():
        head = adr.read_text(encoding="utf-8")[:400]
        assert "- Status:" in head, f"{adr.name} has no status line"
