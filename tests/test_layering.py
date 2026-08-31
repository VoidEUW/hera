"""The layering rule from ARCHITECTURE.md, enforced.

Nothing in a uv workspace physically stops one package from importing another, so the rule
that dependencies point downwards is checked here instead: every `hera_*` import inside a
package's source tree must appear in that package's allow-list below.

Adding an entry to `ALLOWED` is a deliberate act. If a package needs something from a package
above it, the dependency is wrong, not this table.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ROOT / "packages"

ALLOWED: dict[str, frozenset[str]] = {
    # Foundation. The first two are domain-free by contract: they must work unchanged in a
    # project that has nothing to do with Hera, so they import nothing of ours -- not even each
    # other. hera_storage is listed explicitly everywhere it is used rather than treated as
    # universally available, precisely so that this exclusion stays visible.
    "hera_storage": frozenset(),
    "hera_prompts": frozenset(),
    # hera_home is not domain-free -- it says the word "hera" and knows the shape of ~/.hera --
    # but it is below everything, depends on nothing, and answers one question. It sits outside
    # the layering argument the way a constant does.
    "hera_home": frozenset(),
    # The model boundary and pure policy. Neither touches persistence.
    "hera_providers": frozenset(),
    "hera_permissions": frozenset(),
    # Her own MCP server. Not domain-free -- it is entirely about what Hera can do -- but it
    # imports nothing of ours: what it needs from the rest of the system arrives as a port, the
    # way it did when it lived inside hera_tools.
    "hera_mcp": frozenset(),
    # Capability layer. hera_tools mounts whatever in-process server it is handed and does not
    # know that hera_mcp exists; the application is what puts the two together.
    "hera_tools": frozenset({"hera_home", "hera_permissions"}),
    "hera_skillsets": frozenset({"hera_home", "hera_storage"}),
    "hera_memories": frozenset({"hera_home"}),
    # Assembly layer.
    "hera_profiles": frozenset({"hera_home", "hera_storage", "hera_prompts"}),
    # Orchestration.
    "hera_chats": frozenset(
        {
            "hera_home",
            "hera_storage",
            "hera_prompts",
            "hera_providers",
            "hera_permissions",
            "hera_tools",
            "hera_skillsets",
            "hera_profiles",
        }
    ),
    "hera_promptevo": frozenset(
        {"hera_storage", "hera_providers", "hera_profiles", "hera_memories", "hera_skillsets"}
    ),
}


def _packages() -> list[str]:
    if not PACKAGES.is_dir():
        return []
    return sorted(p.name for p in PACKAGES.iterdir() if (p / "pyproject.toml").is_file())


def _hera_imports(source: Path) -> set[str]:
    """Every top-level `hera_*` module name imported by one file."""
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return {name for name in found if name.startswith("hera")}


def test_every_package_has_an_allow_list() -> None:
    """A new package must declare where it sits before its imports can be checked."""
    undeclared = set(_packages()) - set(ALLOWED)
    assert not undeclared, (
        f"{sorted(undeclared)} have no entry in ALLOWED. Add one, and update ARCHITECTURE.md."
    )


@pytest.mark.parametrize("package", _packages())
def test_imports_point_downwards(package: str) -> None:
    permitted = ALLOWED[package] | {package}
    offences: list[str] = []

    for source in sorted((PACKAGES / package / "src").rglob("*.py")):
        for imported in sorted(_hera_imports(source)):
            if imported not in permitted:
                offences.append(f"{source.relative_to(ROOT)} imports {imported}")

    assert not offences, "\n".join(
        [f"{package} may import {sorted(permitted)} and nothing else:", *offences]
    )


@pytest.mark.parametrize("package", _packages())
def test_no_package_imports_the_application(package: str) -> None:
    """apps/core wires the packages together; a package that knows about it is inverted."""
    offences = [
        str(source.relative_to(ROOT))
        for source in sorted((PACKAGES / package / "src").rglob("*.py"))
        if "hera_core" in _hera_imports(source)
    ]
    assert not offences, f"{package} imports the application layer: {offences}"
