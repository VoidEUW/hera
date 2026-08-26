"""Guards on the shape of the workspace itself.

These catch the failure modes that only appear once a second package exists: a member that is
not wired into the type checker, or two test modules that shadow each other.
"""

from __future__ import annotations

import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


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


def _uncovered_by(entries: list[str]) -> list[str]:
    """Workspace members no entry in `entries` refers to."""
    return [
        str(member.relative_to(ROOT))
        for member in _members()
        if not any(
            entry == str(member.relative_to(ROOT))
            or entry.startswith(f"{member.relative_to(ROOT)}/")
            or str(member.relative_to(ROOT)).startswith(f"{entry}/")
            for entry in entries
        )
    ]


def test_mypy_checks_every_package() -> None:
    """mypy's `files` is maintained by hand; this is the reminder when a member is added.

    mypy resolves a glob that matches nothing as a literal path and fails, so `packages/*`
    is not usable while members are still being created one by one.
    """
    missing = _uncovered_by(_table(_root_config(), "tool", "mypy", "files"))
    assert not missing, (
        f"add to [tool.mypy] files in pyproject.toml: {[f'{m}/src' for m in missing]}"
    )


def test_coverage_measures_every_package() -> None:
    """A member missing from `[tool.coverage.run] source` passes the gate without being read."""
    missing = _uncovered_by(_table(_root_config(), "tool", "coverage", "run", "source"))
    assert not missing, f"add to [tool.coverage.run] source in pyproject.toml: {missing}"


def test_test_modules_do_not_shadow_each_other() -> None:
    """Test module basenames must be unique across the whole workspace.

    Test directories carry no `__init__.py`, so pytest puts each one on `sys.path` and imports
    its modules by bare name. Two `test_router.py` files in different packages would resolve to
    one module and pytest would abort collection with an import-file-mismatch. `conftest.py` is
    exempt: pytest handles those by path.
    """
    by_name: defaultdict[str, list[str]] = defaultdict(list)

    for directory in [ROOT / "tests", *(m / "tests" for m in _members())]:
        if not directory.is_dir():
            continue
        for module in sorted(directory.rglob("*.py")):
            if module.name == "conftest.py":
                continue
            by_name[module.name].append(str(module.relative_to(ROOT)))

    clashes = {name: paths for name, paths in by_name.items() if len(paths) > 1}
    assert not clashes, f"test module names must be unique across the workspace: {clashes}"
