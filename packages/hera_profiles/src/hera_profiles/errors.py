"""What this package raises.

All of it descends from :class:`ProfilesError`, so an application can catch the package
without catching everything.
"""

from __future__ import annotations

from collections.abc import Sequence


class ProfilesError(Exception):
    """Base class for every error raised by ``hera_profiles``."""


class UnknownRegion(ProfilesError):
    """A region id that is not in the registry.

    Carries the known ids, because the caller that got this wrong -- a stale profile, a
    hand-typed URL -- is exactly the caller that needs to be told what was available.
    """

    def __init__(self, region_id: str, known: Sequence[str]) -> None:
        self.region_id = region_id
        self.known = list(known)
        super().__init__(f"unknown mind region {region_id!r}; known regions: {', '.join(known)}")


class RegionLocked(ProfilesError):
    """An owner-fixed region was offered a change by something that is not a person.

    Raised by :meth:`hera_profiles.MindRepository.propose`, never by ``write``. The
    distinction is the entire safety story: a person may edit ``safety``, and
    ``hera_promptevo`` may not, and the two go through different doors so that a bug in the
    proposer cannot become a bug in her conduct.
    """

    def __init__(self, region_id: str) -> None:
        self.region_id = region_id
        super().__init__(f"mind region {region_id!r} is owner-fixed; only a person may change it")


class MindError(ProfilesError):
    """The mind repository could not do what was asked.

    A missing ``git``, a repository that will not initialise, a commit that failed. The
    message carries git's own stderr, because a wrapper's paraphrase of a git error is always
    worse than the error.
    """


class NoSuchVersion(ProfilesError):
    """A commit was named that does not touch this region's file."""

    def __init__(self, region_id: str, ref: str) -> None:
        self.region_id = region_id
        self.ref = ref
        super().__init__(f"no version {ref!r} of mind region {region_id!r}")
