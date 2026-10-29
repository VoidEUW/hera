"""One person's mind: their own repository, with the instance's policy read from the template.

With accounts, ``~/.hera/mind`` is the **template** an admin edits, and each person has a mind of
their own under ``~/.hera/users/<id>/mind``, cloned from it the first time it is needed
(ADR 28). Most regions are theirs from then on. A few are not: they are what the instance
requires of her, and a person's copy that could be edited would be a way to take them out.
Those are read from the template for everybody, and this class is the one place that decides,
region by region, which repository answers.
"""

from __future__ import annotations

from typing import Protocol

from hera_profiles.errors import RegionShared
from hera_profiles.mind import MindRepository, RegionVersion
from hera_profiles.regions import MindRegion, region

SHARED_REGIONS: frozenset[str] = frozenset({"safety", "tool_usage", "developer"})
"""Regions read from the template for everybody.

``safety`` and ``tool_usage`` are the instance's policy (ADR 28). ``developer`` is "standing
instructions from whoever runs this deployment", which is the instance by definition — a copy per
person would be the operator's instructions edited by somebody who is not the operator.
``about_you`` is owner-fixed too, and is *not* here: it is about the person, so it is theirs.
"""


class Mind(Protocol):
    """What a prompt builder reads from: the region texts, and which regions there are."""

    @property
    def regions(self) -> tuple[MindRegion, ...]: ...

    def read(self, region_id: str) -> str: ...

    def read_all(self) -> dict[str, str]: ...


class PersonalMind:
    """A person's repository and the template, composed region by region."""

    def __init__(
        self,
        own: MindRepository,
        template: MindRepository,
        *,
        shared: frozenset[str] = SHARED_REGIONS,
    ) -> None:
        self.own = own
        self.template = template
        self.shared = shared

    @property
    def regions(self) -> tuple[MindRegion, ...]:
        return self.template.regions

    def is_shared(self, region_id: str) -> bool:
        return region(region_id).id in self.shared

    def ensure(self) -> None:
        """Clone the template on first use, then seed any region added since. Idempotent."""
        self.own.clone_from(self.template)
        self.own.ensure()

    # -- reading -----------------------------------------------------------------------

    def read(self, region_id: str) -> str:
        return self._answering(region_id).read(region_id)

    def read_all(self) -> dict[str, str]:
        return {item.id: self.read(item.id) for item in self.regions}

    def history(self, region_id: str, *, limit: int | None = None) -> list[RegionVersion]:
        return self._answering(region_id).history(region_id, limit=limit)

    def generation(self, region_id: str) -> int:
        return self._answering(region_id).generation(region_id)

    def show(self, region_id: str, ref: str) -> str:
        return self._answering(region_id).show(region_id, ref)

    # -- writing -----------------------------------------------------------------------

    def write(
        self, region_id: str, text: str, *, message: str = "", origin: str = "manual"
    ) -> str | None:
        """The person's door. A shared region raises :class:`RegionShared`: that text is the
        template's, and an admin changes it there."""
        return self._own(region_id).write(region_id, text, message=message, origin=origin)

    def propose(self, region_id: str, text: str, *, origin: str, message: str = "") -> str | None:
        """The dreamer's door, with the template's tiers *and* the shared regions refused."""
        return self._own(region_id).propose(region_id, text, origin=origin, message=message)

    def revert(self, region_id: str, ref: str, *, origin: str = "manual") -> str | None:
        return self._own(region_id).revert(region_id, ref, origin=origin)

    # -- internals ---------------------------------------------------------------------

    def _answering(self, region_id: str) -> MindRepository:
        return self.template if self.is_shared(region_id) else self.own

    def _own(self, region_id: str) -> MindRepository:
        if self.is_shared(region_id):
            raise RegionShared(region_id)
        return self.own
