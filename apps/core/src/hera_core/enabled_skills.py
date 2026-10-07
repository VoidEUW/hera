"""Which skills she is allowed to see.

``hera_skillsets`` reads folders and does only that, so the list of skills a person switched off
(``[skills] disabled`` in ``config.toml``) is applied here, where the router's candidate set is
built. The unfiltered library stays on the container for the settings screen, which has to list
a switched-off skill in order to offer the way back.

The list is read on every call, the way :func:`hera_core.api.system.patch_skill` writes it, so a
switch takes effect on the next turn with nothing to restart.
"""

from __future__ import annotations

from hera_core.config import load as load_config
from hera_mcp import ToolError
from hera_skillsets import Catalogue, SkillLibrary, SkillLibraryPort


def disabled() -> set[str]:
    return set(load_config().skills.disabled)


class EnabledSkills(SkillLibrary):
    """A view of another library with the switched-off skills left out.

    A subclass rather than a wrapper because the router and the turn take a ``SkillLibrary``;
    every lookup — ``get``, ``all``, ``ids``, ``resolve`` — goes through ``catalogue()``, so
    filtering that one method covers a pin, a ``/slash`` and retrieval alike.
    """

    def __init__(self, inner: SkillLibrary) -> None:
        super().__init__(inner.path)
        self.inner = inner

    def catalogue(self) -> Catalogue:
        found = self.inner.catalogue()
        off = disabled()
        if not off:
            return found
        return found.model_copy(
            update={"skills": tuple(skill for skill in found.skills if skill.id not in off)}
        )


class EnabledSkillPort(SkillLibraryPort):
    """``hera__skill`` over the enabled skills, honest about the ones that are off.

    A skill that is switched off is not one that does not exist, and "no skill named …" would
    send a model hunting for a spelling mistake. It gets the same shape of answer as the tools
    that are not available: a failed call that says why.
    """

    def __init__(self, library: SkillLibrary) -> None:
        super().__init__(EnabledSkills(library))
        self.everything = library

    async def load(self, name: str) -> str | None:
        if name in disabled() and self.everything.get(name) is not None:
            raise ToolError(f"skill {name!r} is switched off in Settings")
        return await super().load(name)
