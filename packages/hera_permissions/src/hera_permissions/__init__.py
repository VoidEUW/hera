"""Whether a tool call may run.

Pure policy over tool *names*. It holds no registry of tools that exist, performs no I/O, and
never dispatches anything -- ``hera_tools`` asks, this answers, and the two stay separable
because of it.
"""

from __future__ import annotations

from hera_permissions.errors import InvalidPattern, PermissionsError
from hera_permissions.matching import matches, specificity
from hera_permissions.policy import Decision, Outcome, PermissionSet, Policy, Rule

__all__ = [
    "Decision",
    "InvalidPattern",
    "Outcome",
    "PermissionSet",
    "PermissionsError",
    "Policy",
    "Rule",
    "matches",
    "specificity",
]
