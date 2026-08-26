"""Rules, sets of rules, and the policy that decides between them.

Pure logic: no I/O, and no registry of tools that actually exist. A policy answers questions
about names, and a name it has never heard of gets the same treatment as any other.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hera_permissions.errors import InvalidPattern
from hera_permissions.matching import matches, specificity


class Decision(StrEnum):
    """What may happen to a tool call.

    ``ASK`` is the interesting one: it is the generalisation of the previous version's
    confirm-before-write card, which was the one piece of that tool layer worth keeping. It
    surfaces as a confirmation, and the answer can be turned into a rule -- see
    :meth:`PermissionSet.with_rule`.
    """

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


_SEVERITY: dict[Decision, int] = {Decision.ALLOW: 0, Decision.ASK: 1, Decision.DENY: 2}


class Rule(BaseModel):
    """One pattern and what to do with the calls it covers."""

    model_config = ConfigDict(frozen=True)

    pattern: str
    decision: Decision
    reason: str = ""
    """Shown with the confirmation, or with the refusal. Worth filling in: "why can I not do
    this" is otherwise a question only the configuration file can answer."""

    @model_validator(mode="after")
    def _validate_pattern(self) -> Rule:
        if not self.pattern.strip():
            raise InvalidPattern("a rule pattern cannot be empty")
        return self

    def covers(self, tool: str) -> bool:
        return matches(self.pattern, tool)


class PermissionSet(BaseModel):
    """An unordered pool of rules.

    Unordered on purpose. Rules are resolved by specificity, not by position, so two sets can
    be merged without either one having to be "first" -- which is what makes a per-profile
    override composable with the base configuration instead of replacing it wholesale.
    """

    model_config = ConfigDict(frozen=True)

    rules: list[Rule] = Field(default_factory=list)

    @classmethod
    def of(
        cls,
        *,
        allow: Sequence[str] = (),
        ask: Sequence[str] = (),
        deny: Sequence[str] = (),
    ) -> PermissionSet:
        """Build from three lists of patterns -- the shape a configuration file has."""
        return cls(
            rules=[
                *(Rule(pattern=p, decision=Decision.ALLOW) for p in allow),
                *(Rule(pattern=p, decision=Decision.ASK) for p in ask),
                *(Rule(pattern=p, decision=Decision.DENY) for p in deny),
            ]
        )

    def with_rule(self, rule: Rule) -> PermissionSet:
        """A new set with ``rule`` added, replacing any existing rule on the same pattern.

        This is "always allow" from a confirmation card: answer once, persist the result,
        and the same question is not asked again. Replacing rather than appending keeps the
        set idempotent under repeated answers.
        """
        kept = [existing for existing in self.rules if existing.pattern != rule.pattern]
        return PermissionSet(rules=[*kept, rule])

    def without(self, pattern: str) -> PermissionSet:
        """A new set with every rule on ``pattern`` removed."""
        return PermissionSet(rules=[rule for rule in self.rules if rule.pattern != pattern])


class Outcome(BaseModel):
    """The answer, and enough of the reasoning to show a person."""

    model_config = ConfigDict(frozen=True)

    tool: str
    decision: Decision
    rule: Rule | None = None
    """The rule that decided it, or ``None`` when nothing matched and the fallback applied."""

    profile: str | None = None
    """The profile the deciding rule came from, or ``None`` for a base rule."""

    @property
    def allowed(self) -> bool:
        return self.decision is Decision.ALLOW

    @property
    def reason(self) -> str:
        return self.rule.reason if self.rule is not None else ""


class Policy(BaseModel):
    """Base rules, optional per-profile rules, and what to do when nothing matches.

    Resolution takes every matching rule from both layers and picks one, in this order:

    1. **more specific wins** -- ``fs__read`` beats ``fs__*`` beats ``*``;
    2. **the profile wins** over the base at equal specificity, which is the entire point of
       having a profile;
    3. **the stricter decision wins** within one layer, so a set that says both ``allow`` and
       ``deny`` for the same pattern denies.

    Specificity outranking the profile layer is deliberate: a profile whose broad ``*: allow``
    could switch off a pointed ``shell__*: deny`` from the base would make the base rule
    decorative. A profile that means to loosen a specific rule has to be specific about it.
    """

    model_config = ConfigDict(frozen=True)

    base: PermissionSet = Field(default_factory=PermissionSet)
    profiles: dict[str, PermissionSet] = Field(default_factory=dict)
    fallback: Decision = Decision.ASK
    """What an unmatched tool gets. ``ASK`` by default -- a tool nobody has an opinion about
    is exactly the case a person should see once."""

    def check(self, tool: str, *, profile: str | None = None) -> Outcome:
        """Decide whether ``tool`` may run."""
        candidates: list[tuple[Rule, str | None]] = [
            (rule, None) for rule in self.base.rules if rule.covers(tool)
        ]
        if profile is not None and profile in self.profiles:
            candidates.extend(
                (rule, profile) for rule in self.profiles[profile].rules if rule.covers(tool)
            )

        if not candidates:
            return Outcome(tool=tool, decision=self.fallback)

        rule, source = max(candidates, key=_rank)
        return Outcome(tool=tool, decision=rule.decision, rule=rule, profile=source)

    def with_rule(self, rule: Rule, *, profile: str | None = None) -> Policy:
        """A new policy with ``rule`` added to the base, or to one profile."""
        if profile is None:
            return self.model_copy(update={"base": self.base.with_rule(rule)})
        existing = self.profiles.get(profile, PermissionSet())
        return self.model_copy(
            update={"profiles": {**self.profiles, profile: existing.with_rule(rule)}}
        )


def _rank(candidate: tuple[Rule, str | None]) -> tuple[int, int, int, int]:
    rule, source = candidate
    exact, literal = specificity(rule.pattern)
    return (exact, literal, 1 if source is not None else 0, _SEVERITY[rule.decision])
