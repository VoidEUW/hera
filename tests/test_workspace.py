"""Guards on the shape of the workspace itself.

These catch the failure modes that only appear once a second package exists: a member that is
not wired into the type checker, or two test modules that shadow each other.
"""

from __future__ import annotations

import re
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


def _config(package: Path) -> Any:
    return tomllib.loads((package / "pyproject.toml").read_text(encoding="utf-8"))


def _root_config() -> Any:
    return _config(ROOT)


def _requirement_names(package: Path) -> list[str]:
    """Distribution names a package depends on, stripped of version and marker syntax."""
    requirements: list[str] = _config(package).get("project", {}).get("dependencies", [])
    return [
        re.split(r"[<>=!~\[; ]", requirement, maxsplit=1)[0].strip() for requirement in requirements
    ]


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


def test_internal_dependencies_have_a_workspace_source() -> None:
    """Every member another member depends on needs `{ workspace = true }` in the root.

    Without it `uv sync` fails outright, and — less obviously — an outside project depending on
    one package through a git subdirectory cannot resolve that package's internal dependencies
    from the same commit. See CONTRIBUTING.md, "Using one package somewhere else".
    """
    member_names = {_table(_config(m), "project", "name") for m in _members()}
    declared = set(_root_config().get("tool", {}).get("uv", {}).get("sources", {}))

    missing: dict[str, list[str]] = {}
    for member in _members():
        required = member_names & set(_requirement_names(member))
        if gaps := sorted(required - declared):
            missing[_table(_config(member), "project", "name")] = gaps

    assert not missing, (
        "add to [tool.uv.sources] in the root pyproject.toml as `{ workspace = true }`: "
        f"{missing}"
    )


def test_test_modules_do_not_shadow_each_other() -> None:
    """Test module basenames must be unique across the whole workspace.

    Test directories carry no `__init__.py`, so pytest puts each one on `sys.path` and imports
    its modules by bare name. Two `test_router.py` files in different packages would resolve to
    one module and pytest would abort collection with an import-file-mismatch. `conftest.py` is
    exempt: pytest handles those by path.

    mypy has no such exemption -- it derives the module name from the file name and refuses to
    check either of two files that collide. That is why `[tool.mypy] exclude` drops
    `tests/conftest.py`; the two facts belong next to each other.
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
