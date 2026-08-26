# hera-permissions

Whether a tool call may run: **allow**, **deny** or **ask**, decided by pattern and profile.

Pure logic. It holds no registry of tools that exist, performs no I/O, and never dispatches
anything — `hera_tools` asks, this answers, and the two stay separable because of it. A tool
name this package has never heard of is simply an unmatched one.

## Installation

Inside this workspace, depend on it by name — uv resolves it to the member:

```toml
dependencies = ["hera-permissions"]
```

Outside, it installs like any package (`uv add hera-permissions`); pin a compatible range,
`hera-permissions>=0.1,<0.2`.

## Quick start

```python
from hera_permissions import Decision, PermissionSet, Policy

policy = Policy(
    base=PermissionSet.of(
        allow=["hera__*"],          # her own tools need no confirmation
        deny=["shell__*"],
        ask=["*"],                  # anything else, once
    ),
    profiles={"coding": PermissionSet.of(allow=["shell__git"])},
)

outcome = policy.check("shell__git", profile="coding")
outcome.decision is Decision.ALLOW   # True
```

`PermissionSet.of(allow=…, ask=…, deny=…)` is the shape a configuration file has, and a
`Policy` round-trips through JSON, so it loads from configuration and travels to the interface
without a translation layer.

## How a rule wins

Every matching rule from both layers is collected, and one is picked:

1. **more specific wins** — `fs__read` beats `fs__*` beats `*`;
2. **the profile wins** over the base at equal specificity, which is the entire point of
   having a profile;
3. **the stricter decision wins** within one layer, so a set saying both `allow` and `deny` for
   the same pattern denies.

Rules are an unordered pool, not a first-match list. That is what makes two sets *mergeable*:
a profile's rules and the base rules are resolved together, and the answer does not depend on
which list happened to be concatenated first.

**Specificity outranking the profile layer is deliberate.** If a profile's broad `*: allow`
could switch off a pointed `shell__*: deny` from the base, the base rule would be decorative. A
profile that means to loosen a specific rule has to be specific about it.

Patterns are `fnmatch` globs over `server__tool` names — `*` and `?` are the intended tools —
and matching is case-sensitive, because tool names are identifiers rather than filenames and
two servers differing only in case is a collision worth seeing.

## `ask` is the interesting one

It is the generalisation of the previous version's confirm-before-write card, which was the
one piece of that tool layer worth keeping. An `ask` outcome surfaces as a confirmation, and
the answer becomes a rule:

```python
policy = policy.with_rule(Rule(pattern="fs__read", decision=Decision.ALLOW))
```

Every edit returns a new object, so a policy handed to a turn cannot change underneath it, and
adding the same pattern twice replaces rather than appends — answering the same question twice
does not grow the rule set.

The default `fallback` is `ASK`: a new MCP server appearing should surface once, not run
silently and not fail.

## What an outcome carries

```python
outcome.decision   # Decision
outcome.allowed    # decision is ALLOW
outcome.tool       # the name that was checked
outcome.rule       # the rule that decided it, or None when the fallback applied
outcome.profile    # the profile that rule came from, or None for a base rule
outcome.reason     # the rule's reason, for showing with the confirmation or the refusal
```

Filling in `reason` is worth the keystrokes: *why can I not do this* is otherwise a question
only the configuration file can answer.

## What does **not** belong here

No I/O, no configuration loading, no tool catalogue, no dispatch, no audit log, and no
knowledge of what any particular tool does. Argument-level policy — "this tool, but only with
these parameters" — is not here either: this package decides on names.
