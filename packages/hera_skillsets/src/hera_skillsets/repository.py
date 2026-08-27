"""Usage counts for skills.

The only thing about a skill that belongs in a database. The skill itself is a folder — giving
it a row would create a second opinion about which skills exist, and the two would disagree the
first time someone deleted one.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlmodel import Session, col

from hera_skillsets.models import SkillUsage
from hera_storage import Repository, utcnow


class SkillUsageRepository(Repository[SkillUsage]):
    """How often each skill has actually reached a turn, per owner."""

    def __init__(self, session: Session) -> None:
        super().__init__(SkillUsage, session)

    def for_owner(self, owner_id: UUID) -> dict[str, SkillUsage]:
        """Usage keyed by skill id, for the settings screen's "sort by last used"."""
        return {row.skill_id: row for row in self.list(SkillUsage.owner_id == owner_id)}

    def record(self, owner_id: UUID, skill_ids: Sequence[str]) -> list[SkillUsage]:
        """Count one turn's worth of selections.

        Called after a turn is built, not after it succeeds: the question this answers is
        "was this skill chosen", and a skill that was injected into a turn the model then
        failed was still chosen. Conflating the two would make the number useless for judging
        retrieval, which is the reason it is kept.
        """
        if not skill_ids:
            return []
        existing = self.for_owner(owner_id)
        now = utcnow()
        touched: list[SkillUsage] = []
        for skill_id in dict.fromkeys(skill_ids):
            row = existing.get(skill_id)
            if row is None:
                row = self.add(SkillUsage(owner_id=owner_id, skill_id=skill_id))
            row.hits += 1
            row.last_used_at = now
            touched.append(row)
        self.session.flush()
        return touched

    def forget(self, owner_id: UUID, skill_id: str) -> None:
        """Drop the counts for one skill.

        Hard delete rather than a revoke: this row is a tally, not a record of something that
        happened, and a revoked tally that still has to be filtered out of every sum is a cost
        with no benefit.
        """
        for row in self.list(SkillUsage.owner_id == owner_id, col(SkillUsage.skill_id) == skill_id):
            self.session.delete(row)
        self.session.flush()
