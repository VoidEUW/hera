"""Showing, making, changing and removing permission rules (#109).

The operations behind Settings → Permissions and behind "always" on a confirmation card, so the
two can never disagree about what survives a restart. A rule changes in three places and they
move together here: the file (``permission_rules``), the policy the tool layer is asking, and the
orchestrator holding that tool layer. Nothing else in the application swaps a policy.

The policy in force is read from the registry, not rebuilt from the file: that is what the turn
is actually asking, and a container assembled with its own policy (a test, a deployment with
rules of its own) keeps them. The file only records what a person added on top.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from hera_core import permission_rules
from hera_core.permission_rules import RuleSource, StoredRule
from hera_home import user_permissions_path
from hera_permissions import Decision, Policy, Rule, matches

if TYPE_CHECKING:
    from hera_core.wiring import Services
    from hera_tools import ToolRegistry

__all__ = [
    "BuiltInRule",
    "NoSuchRule",
    "NoToolLayer",
    "RuleExists",
    "RuleView",
    "add",
    "change",
    "fallback",
    "matching",
    "remember",
    "remove",
    "rules",
    "set_fallback",
]


class NoSuchRule(LookupError):
    """There is no rule on exactly that pattern."""


class RuleExists(ValueError):
    """There already is a rule on exactly that pattern; change it instead."""


class BuiltInRule(ValueError):
    """A rule Hera ships with. It can be changed, not removed."""


class NoToolLayer(RuntimeError):
    """Nothing is asking a policy in this deployment, so there is nothing to change."""


class RuleView(BaseModel):
    """A rule as the screen shows it."""

    model_config = ConfigDict(frozen=True)

    pattern: str
    decision: Decision
    reason: str = ""
    name: str = ""
    source: RuleSource | Literal["profile"]
    profile: str | None = None


def fallback(container: Services) -> Decision:
    """What a tool no rule covers gets."""
    return container.registry.policy.fallback if container.registry is not None else Decision.ASK


def rules(container: Services) -> list[RuleView]:
    """Every rule in force, by pattern — the set is unordered by design (rules resolve by
    specificity, not position), and insertion order would suggest an authority a pattern lacks."""
    if container.registry is None:
        return []
    policy = container.registry.policy
    stored = permission_rules.load()
    views = [_view(rule, container.default_policy, stored) for rule in policy.base.rules]
    for profile, rule_set in policy.profiles.items():
        views.extend(
            RuleView(
                pattern=rule.pattern,
                decision=rule.decision,
                reason=rule.reason,
                name=rule.name,
                source="profile",
                profile=profile,
            )
            for rule in rule_set.rules
        )
    return sorted(views, key=lambda view: (view.pattern, view.profile or ""))


def matching(pattern: str, tools: Sequence[str]) -> list[str]:
    """Which of ``tools`` the pattern covers — the same matcher the policy uses."""
    return [tool for tool in tools if matches(pattern, tool)]


def add(
    container: Services, *, pattern: str, decision: Decision, name: str = "", reason: str = ""
) -> RuleView:
    """Make a rule. A pattern that already has one is refused rather than replaced: replacing
    would change what a rule decides on the strength of a form that looked like a new one."""
    registry = _registry(container)
    rule = Rule(
        pattern=pattern.strip(), decision=decision, name=name.strip(), reason=reason.strip()
    )
    with permission_rules.LOCK:
        if registry.policy.base.get(rule.pattern) is not None:
            raise RuleExists(rule.pattern)
        stored = permission_rules.load()
        permission_rules.save(stored.with_rule(_stored(rule, "you")))
        _swap(container, registry.policy.with_rule(rule))
    return _view(rule, container.default_policy, permission_rules.load())


def change(
    container: Services,
    pattern: str,
    *,
    name: str | None = None,
    decision: Decision | None = None,
    reason: str | None = None,
) -> RuleView:
    """Change what a rule is called, decides, or says. Never its pattern: that is its identity,
    and a different pattern is a different rule."""
    registry = _registry(container)
    with permission_rules.LOCK:
        current = registry.policy.base.get(pattern)
        if current is None:
            raise NoSuchRule(pattern)
        changed = current.model_copy(
            update={
                "name": current.name if name is None else name.strip(),
                "decision": current.decision if decision is None else decision,
                "reason": current.reason if reason is None else reason.strip(),
            }
        )
        stored = permission_rules.load()
        existing = stored.get(pattern)
        # A shipped rule that is changed becomes the person's own on that pattern; a card rule
        # that is edited stays a card rule, because that is still where it came from.
        source = existing.source if existing is not None else "you"
        permission_rules.save(stored.with_rule(_stored(changed, source)))
        _swap(container, registry.policy.with_rule(changed))
    return _view(changed, container.default_policy, permission_rules.load())


def remove(container: Services, pattern: str) -> None:
    """Delete a rule. Its tools go to the next most specific rule, ultimately the fallback; a
    rule that overrides a shipped one puts the shipped one back."""
    registry = _registry(container)
    with permission_rules.LOCK:
        if registry.policy.base.get(pattern) is None:
            raise NoSuchRule(pattern)
        stored = permission_rules.load()
        shipped = container.default_policy.base.get(pattern)
        if stored.get(pattern) is None and shipped is not None:
            raise BuiltInRule(pattern)
        policy = registry.policy.without_rule(pattern)
        if shipped is not None:
            policy = policy.with_rule(shipped)
        permission_rules.save(stored.without(pattern))
        _swap(container, policy)


def set_fallback(container: Services, decision: Decision) -> Decision:
    """Change what a tool no rule covers gets. Setting it back to the built-in one forgets the
    choice, so a later improvement to the built-in still reaches this install."""
    registry = _registry(container)
    with permission_rules.LOCK:
        stored = permission_rules.load()
        chosen = None if decision is container.default_policy.fallback else decision
        permission_rules.save(stored.model_copy(update={"fallback": chosen}))
        _swap(container, registry.policy.with_fallback(decision))
    return decision


def remember(owner: UUID, tools: Sequence[str], *, allow: bool) -> None:
    """Turn "always" on a confirmation card into one person's rules, kept across restarts.

    **The person's file, not the instance's** (ADR 28): ``users/<id>/permissions.json``, a layer
    over everything an admin decided. So the answer can settle an *ask* for them and can never
    loosen a *deny* — :meth:`hera_permissions.Policy.check` sees to that, at the card and at the
    dispatch alike. Nothing is swapped here: a person's rules are read for every turn.

    Written against the **exact tool name**, not a pattern derived from it. A card about
    ``fs__write_file`` answered with "always" must not quietly permit ``fs__delete_file``; if
    somebody wants the broader rule they can widen it on the Permissions screen, where they can
    see what they are doing.
    """
    if not tools:
        return
    decision = Decision.ALLOW if allow else Decision.DENY
    path = user_permissions_path(str(owner))
    with permission_rules.LOCK:
        stored = permission_rules.load(path)
        for tool in sorted(set(tools)):
            rule = Rule(
                pattern=tool,
                decision=decision,
                reason="answered on a confirmation card",
                name=permission_rules.card_name([tool], allow=allow),
            )
            stored = stored.with_rule(_stored(rule, "card"))
        permission_rules.save(stored, path)


def _registry(container: Services) -> ToolRegistry:
    if container.registry is None:
        raise NoToolLayer
    return container.registry


def _swap(container: Services, policy: Policy) -> None:
    """Put a new policy where the turn asks it. The same servers; no reconnect."""
    assert container.registry is not None
    container.registry = container.registry.with_policy(policy)
    container.orchestrator.registry = container.registry


def _stored(rule: Rule, source: Literal["you", "card"]) -> StoredRule:
    return StoredRule(
        pattern=rule.pattern,
        decision=rule.decision,
        reason=rule.reason,
        name=rule.name,
        source=source,
    )


def _view(rule: Rule, shipped: Policy, stored: permission_rules.StoredPermissions) -> RuleView:
    kept = stored.get(rule.pattern)
    source: RuleSource = (
        kept.source
        if kept is not None
        else ("default" if shipped.base.get(rule.pattern) else "you")
    )
    return RuleView(
        pattern=rule.pattern,
        decision=rule.decision,
        reason=rule.reason,
        name=rule.name,
        source=source,
    )


# -- a person's own rules (ADR 28) -------------------------------------------------------------


def mine(owner: UUID) -> list[StoredRule]:
    """One person's own rules, sorted by pattern for the reason the instance's are."""
    stored = permission_rules.load(user_permissions_path(str(owner)))
    return sorted(stored.rules, key=lambda rule: rule.pattern)


def change_mine(owner: UUID, pattern: str, decision: Decision) -> StoredRule:
    """Flip one of a person's rules. Their own, so nobody else's file is reachable from here."""
    path = user_permissions_path(str(owner))
    with permission_rules.LOCK:
        stored = permission_rules.load(path)
        current = stored.get(pattern)
        if current is None:
            raise NoSuchRule(pattern)
        changed = current.model_copy(update={"decision": decision})
        permission_rules.save(stored.with_rule(changed), path)
    return changed


def forget_mine(owner: UUID, pattern: str) -> None:
    """Remove one of a person's rules: the instance's decision on that tool applies again."""
    path = user_permissions_path(str(owner))
    with permission_rules.LOCK:
        stored = permission_rules.load(path)
        if stored.get(pattern) is None:
            raise NoSuchRule(pattern)
        permission_rules.save(stored.without(pattern), path)
