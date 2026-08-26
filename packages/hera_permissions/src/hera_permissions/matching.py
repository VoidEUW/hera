"""Which patterns match a tool name, and which of several matches is the more specific.

Kept apart from the policy itself because it is the part with an opinion in it: "most
specific wins" is a choice, and a choice that is easy to state is worth being able to test on
its own.
"""

from __future__ import annotations

from fnmatch import fnmatchcase

WILDCARDS = "*?["
"""``*`` and ``?`` are the intended tools. ``[seq]`` works because :mod:`fnmatch` supports it,
and is counted as a wildcard so a character class never outranks a literal name."""


def matches(pattern: str, tool: str) -> bool:
    """Whether ``pattern`` covers ``tool``.

    Case-sensitive: tool names are ``server__tool`` identifiers, not filenames, and two
    servers differing only in case is a collision worth seeing rather than smoothing over.
    """
    return fnmatchcase(tool, pattern)


def specificity(pattern: str) -> tuple[int, int]:
    """How specific a pattern is, as a key that sorts ascending.

    An exact name beats any pattern containing a wildcard, and among wildcard patterns the
    one that pins down more characters wins -- so ``fs__read`` beats ``fs__*`` beats ``*``.

    Ordering by this instead of by declaration order is what makes rule sets *mergeable*: a
    profile's rules and the base rules are evaluated as one pool, and the answer does not
    depend on which list happened to be concatenated first.
    """
    literal = sum(1 for character in pattern if character not in WILDCARDS)
    exact = 0 if any(character in WILDCARDS for character in pattern) else 1
    return (exact, literal)
