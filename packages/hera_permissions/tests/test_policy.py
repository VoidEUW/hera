"""Resolution: which rule wins, and what happens when none does."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hera_permissions import (
    Decision,
    InvalidPattern,
    PermissionSet,
    Policy,
    Rule,
)


def rule(pattern: str, decision: Decision, reason: str = "") -> Rule:
    return Rule(pattern=pattern, decision=decision, reason=reason)


# -- the fallback -------------------------------------------------------------------------


def test_a_tool_nobody_has_an_opinion_about_is_asked_about() -> None:
    """A new MCP server appearing should surface once, not run silently and not fail."""
    outcome = Policy().check("newserver__dothing")

    assert outcome.decision is Decision.ASK
    assert outcome.rule is None
    assert not outcome.allowed


def test_the_fallback_can_be_tightened() -> None:
    policy = Policy(fallback=Decision.DENY)

    assert policy.check("anything__at_all").decision is Decision.DENY


def test_a_policy_answers_about_names_it_has_never_heard_of() -> None:
    """No registry of tools that exist lives here; an unknown name is just an unmatched one."""
    policy = Policy(base=PermissionSet.of(allow=["hera__*"]))

    assert policy.check("hera__invented_yesterday").allowed


# -- specificity --------------------------------------------------------------------------


def test_the_more_specific_rule_wins() -> None:
    policy = Policy(base=PermissionSet.of(allow=["fs__*"], deny=["fs__delete"]))

    assert policy.check("fs__read").decision is Decision.ALLOW
    assert policy.check("fs__delete").decision is Decision.DENY


def test_the_answer_does_not_depend_on_the_order_rules_were_written_in() -> None:
    """Order independence is what makes two rule sets mergeable rather than one replacing
    the other."""
    forwards = Policy(
        base=PermissionSet(rules=[rule("fs__*", Decision.ALLOW), rule("fs__rm", Decision.DENY)])
    )
    backwards = Policy(
        base=PermissionSet(rules=[rule("fs__rm", Decision.DENY), rule("fs__*", Decision.ALLOW)])
    )

    assert forwards.check("fs__rm") == backwards.check("fs__rm")


def test_the_stricter_decision_wins_a_tie_within_one_layer() -> None:
    """A set that says both allow and deny for the same pattern is a configuration mistake;
    resolving it towards deny is the answer that cannot cause harm."""
    policy = Policy(
        base=PermissionSet(rules=[rule("fs__*", Decision.ALLOW), rule("fs__*", Decision.DENY)])
    )

    assert policy.check("fs__read").decision is Decision.DENY


# -- profiles -----------------------------------------------------------------------------


def test_a_profile_rule_beats_a_base_rule_of_equal_specificity() -> None:
    """That is the entire point of having a profile."""
    policy = Policy(
        base=PermissionSet.of(ask=["fs__*"]),
        profiles={"coding": PermissionSet.of(allow=["fs__*"])},
    )

    assert policy.check("fs__read", profile="coding").decision is Decision.ALLOW
    assert policy.check("fs__read").decision is Decision.ASK


def test_a_broad_profile_rule_cannot_switch_off_a_pointed_base_rule() -> None:
    """Specificity outranks the profile layer on purpose: if `*: allow` in a profile could
    undo `shell__*: deny`, the base rule would be decorative. A profile that means to loosen
    a specific rule has to be specific about it."""
    policy = Policy(
        base=PermissionSet.of(deny=["shell__*"]),
        profiles={"coding": PermissionSet.of(allow=["*"])},
    )

    assert policy.check("shell__exec", profile="coding").decision is Decision.DENY
    assert policy.check("other__thing", profile="coding").decision is Decision.ALLOW


def test_a_specific_profile_rule_does_loosen_a_broad_base_rule() -> None:
    policy = Policy(
        base=PermissionSet.of(deny=["shell__*"]),
        profiles={"coding": PermissionSet.of(allow=["shell__git"])},
    )

    assert policy.check("shell__git", profile="coding").allowed


def test_an_unknown_profile_falls_through_to_the_base() -> None:
    policy = Policy(base=PermissionSet.of(allow=["hera__*"]))

    assert policy.check("hera__note", profile="does-not-exist").allowed


def test_an_outcome_names_the_profile_its_rule_came_from() -> None:
    policy = Policy(profiles={"coding": PermissionSet.of(allow=["fs__*"])})

    assert policy.check("fs__read", profile="coding").profile == "coding"
    assert Policy(base=PermissionSet.of(allow=["fs__*"])).check("fs__read").profile is None


# -- what the outcome carries ---------------------------------------------------------------


def test_an_outcome_carries_the_reason_so_a_refusal_can_explain_itself() -> None:
    """Why a call cannot run should not be a question only the config file can answer."""
    policy = Policy(base=PermissionSet(rules=[rule("shell__*", Decision.DENY, "not on this box")]))

    outcome = policy.check("shell__exec")

    assert outcome.reason == "not on this box"
    assert outcome.tool == "shell__exec"


def test_an_unmatched_outcome_has_no_reason_to_give() -> None:
    assert Policy().check("x__y").reason == ""


# -- editing a policy -----------------------------------------------------------------------


def test_always_allow_turns_a_confirmation_into_a_rule() -> None:
    """Answering an ask once and persisting the result is how the question stops being asked."""
    policy = Policy(base=PermissionSet.of(ask=["*"]))

    answered = policy.with_rule(rule("fs__read", Decision.ALLOW))

    assert answered.check("fs__read").allowed
    assert answered.check("fs__write").decision is Decision.ASK
    assert policy.check("fs__read").decision is Decision.ASK


def test_answering_the_same_question_twice_does_not_grow_the_rule_set() -> None:
    once = PermissionSet().with_rule(rule("fs__read", Decision.ALLOW))
    twice = once.with_rule(rule("fs__read", Decision.DENY))

    assert twice.rules == [rule("fs__read", Decision.DENY)]


def test_a_rule_can_be_added_to_one_profile() -> None:
    policy = Policy().with_rule(rule("fs__read", Decision.ALLOW), profile="coding")

    assert policy.check("fs__read", profile="coding").allowed
    assert policy.check("fs__read").decision is Decision.ASK


def test_adding_to_a_profile_keeps_the_rules_already_there() -> None:
    policy = Policy(profiles={"coding": PermissionSet.of(allow=["fs__*"])})

    extended = policy.with_rule(rule("shell__git", Decision.ALLOW), profile="coding")

    assert extended.check("fs__read", profile="coding").allowed
    assert extended.check("shell__git", profile="coding").allowed


def test_a_rule_can_be_withdrawn() -> None:
    permissions = PermissionSet.of(allow=["fs__*"], deny=["shell__*"])

    assert permissions.without("fs__*").rules == [rule("shell__*", Decision.DENY)]


# -- construction ---------------------------------------------------------------------------


def test_a_set_can_be_built_from_the_three_lists_a_config_file_has() -> None:
    permissions = PermissionSet.of(allow=["hera__*"], ask=["fs__*"], deny=["shell__*"])

    policy = Policy(base=permissions)
    assert policy.check("hera__emotion").decision is Decision.ALLOW
    assert policy.check("fs__read").decision is Decision.ASK
    assert policy.check("shell__exec").decision is Decision.DENY


def test_an_empty_pattern_is_rejected_where_it_is_written() -> None:
    """It would match nothing and silently do nothing; better to fail at the config, loudly."""
    with pytest.raises(InvalidPattern):
        Rule(pattern="   ", decision=Decision.ALLOW)


def test_a_policy_survives_a_json_round_trip() -> None:
    """It is loaded from configuration and shown in the interface, so it has to travel."""
    policy = Policy(
        base=PermissionSet.of(allow=["hera__*"], deny=["shell__*"]),
        profiles={"coding": PermissionSet.of(allow=["fs__*"])},
        fallback=Decision.DENY,
    )

    assert Policy.model_validate_json(policy.model_dump_json()) == policy


def test_a_policy_is_frozen() -> None:
    """Every edit returns a new object, so a policy handed to a turn cannot change underneath
    it."""
    policy = Policy()

    with pytest.raises(ValidationError):
        policy.fallback = Decision.ALLOW  # type: ignore[misc]  # the assignment failing is the test
