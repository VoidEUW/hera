"""Small guards against documentation drifting away from the repository."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

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


def _table(config: Any, *keys: str) -> Any:
    """Walk into a parsed TOML document. `tomllib` hands back `Any`; keep that at the edge."""
    for key in keys:
        config = config[key]
    return config


def _root_config() -> Any:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _members() -> list[Path]:
    patterns: list[str] = _table(_root_config(), "tool", "uv", "workspace", "members")
    return [match for pattern in patterns for match in sorted(ROOT.glob(pattern))]


def test_workspace_members_resolve() -> None:
    """Every path a member glob matches really is a package."""
    for match in _members():
        assert (match / "pyproject.toml").is_file(), (
            f"{match.relative_to(ROOT)} matches a workspace member glob but is not a package"
        )


def test_mypy_checks_every_package() -> None:
    """mypy's `files` is maintained by hand; this is the reminder when a member is added.

    mypy resolves a glob that matches nothing as a literal path and fails, so `packages/*`
    is not usable while members are still being created one by one.
    """
    checked: list[str] = _table(_root_config(), "tool", "mypy", "files")

    missing = [
        str(member.relative_to(ROOT))
        for member in _members()
        if not any(entry.startswith(str(member.relative_to(ROOT))) for entry in checked)
    ]
    assert not missing, (
        f"add to [tool.mypy] files in pyproject.toml: {[f'{m}/src' for m in missing]}"
    )
