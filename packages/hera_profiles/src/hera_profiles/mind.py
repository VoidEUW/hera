"""The mind: one Markdown file per region, in a real git repository.

``$HERA_HOME/mind`` is a git repository you can ``cd`` into. That is not an implementation
detail chosen for convenience — it is the openness quality from ``docs/frontend.md`` made
concrete. Every change to who she is has an author, a timestamp, a diff and a way back, and
none of it needs this application to be running to be readable.

**Why git rather than a table.** A row with a ``version`` column gives you the current text
and, with effort, the previous one. A repository gives you ``git log -p``, ``git blame``, and
someone else's editor. When ``hera_promptevo`` starts proposing rewrites in v0.2, the question
"what did this region say three generations ago and who changed it" stops being a nice-to-have
and becomes how you tell evolution from drift.

**Synchronous, like ``hera_storage``.** Git is blocking I/O and this package makes no attempt
to hide that. The turn orchestrator runs it in a worker thread; FastAPI does the same for a
plain ``def`` route. An async facade over ``subprocess`` here would be a thread pool wearing a
costume, and it would put ``await`` in front of the one thing in the system that is genuinely
fast — reading twelve small files off a local disk.

**``git`` the binary, not a binding.** No ``pygit2``, no ``GitPython``. The operations needed
are init, add, commit, log, show — five verbs that have been stable for twenty years — and a
binding would be a compiled dependency plus a second thing to keep current, in exchange for
nothing. Every invocation pins its own identity and disables signing, so a machine with no
``user.email`` configured, or with ``commit.gpgsign = true`` set globally, still works.
"""

from __future__ import annotations

import os
import subprocess
import threading
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from hera_home import mind_dir
from hera_profiles.errors import MindError, NoSuchVersion, RegionLocked
from hera_profiles.regions import MIND_REGIONS, MindRegion, Tier, filename, region

COMMITTER_NAME = "Hera"
COMMITTER_EMAIL = "hera@localhost"

ORIGIN_TRAILER = "Hera-Origin"
"""Git trailer recording *what kind of thing* made a change.

``manual`` for a person at the settings screen, ``dream:<uuid>`` for an accepted proposal from
``hera_promptevo``, ``seed`` for the first write of a region. Kept as a trailer rather than
baked into the subject line so ``git log --format`` can pull it out without parsing prose, and
so a human-written commit message stays human-written.
"""

_UNIT = "\x1f"
_RECORD = "\x1e"

_LOG_FORMAT = _UNIT.join(
    ("%H", "%aI", "%s", f"%(trailers:key={ORIGIN_TRAILER},valueonly,separator=%x2c)")
)


class RegionVersion(BaseModel):
    """One commit that touched one region's file."""

    model_config = ConfigDict(frozen=True)

    sha: str
    when: datetime
    message: str
    origin: str = ""
    """Value of the :data:`ORIGIN_TRAILER`, or ``""`` for a commit that carried none."""


class MindRepository:
    """The git repository holding the mind regions.

    One instance per process is enough, and sharing one is safe: writes are serialised behind
    a lock, and reads go straight to the filesystem.
    """

    def __init__(
        self, path: Path | None = None, *, regions: Sequence[MindRegion] = MIND_REGIONS
    ) -> None:
        self.path = path if path is not None else mind_dir()
        self.regions = tuple(regions)
        self._lock = threading.Lock()

    # -- lifecycle ---------------------------------------------------------------------

    @property
    def initialised(self) -> bool:
        """Whether there is a git repository here yet."""
        return (self.path / ".git").is_dir()

    def ensure(self) -> None:
        """Make the repository exist and every region have a file. Idempotent.

        Safe to call on every boot. An existing repository is left alone except for regions
        that have no file yet, which are seeded from the registry and committed together —
        that is also how a region added in a later version arrives on an existing install,
        with no migration and no special case.

        Regions are never *removed* here. A file whose region left the registry stops being
        read and keeps its history, which is the same "leave the old thing alone rather than
        drop it" the rest of this project uses.
        """
        with self._lock:
            self._init_repository()
            missing = [
                item for item in self.regions if not (self.path / filename(item.id)).exists()
            ]
            if not missing:
                return
            for item in missing:
                self._path_of(item.id).write_text(_normalised(item.default), encoding="utf-8")
            self._commit(
                [filename(item.id) for item in missing],
                message=_seed_message(missing),
                origin="seed",
            )

    # -- reading -----------------------------------------------------------------------

    def read(self, region_id: str) -> str:
        """The current text of one region.

        A region whose file does not exist yet falls back to the registry default, so a
        repository that has never been through :meth:`ensure` still renders something. A file
        that exists and is *empty* comes back empty — emptying a region in the editor is a
        decision, and quietly restoring the seed text would undo it invisibly.
        """
        item = region(region_id)
        path = self._path_of(region_id)
        if not path.exists():
            return _normalised(item.default)
        return _normalised(path.read_text(encoding="utf-8"))

    def read_all(self) -> dict[str, str]:
        """Every registered region's current text, keyed by id."""
        return {item.id: self.read(item.id) for item in self.regions}

    # -- writing -----------------------------------------------------------------------

    def write(
        self,
        region_id: str,
        text: str,
        *,
        message: str = "",
        origin: str = "manual",
        when: datetime | None = None,
    ) -> str | None:
        """Set a region's text and commit it. Returns the new sha, or ``None`` if unchanged.

        The owner's door: every region is writable through it, including the owner-fixed
        ones. Editing ``safety`` in the settings screen is the actual mechanism behind
        "add a rule without touching code", and it lands here.

        Writing text identical to what is already there is a no-op rather than an empty
        commit, so a settings screen that saves on blur does not fill the log with noise.

        ``when`` backdates both author and committer date. It exists for replaying an
        existing history onto a renamed region, which is the one migration this design
        needs and which the prototype had to write by hand (``prototype.md:714``).
        """
        region(region_id)  # reject an unknown id before touching the disk
        content = _normalised(text)
        with self._lock:
            self._init_repository()
            path = self._path_of(region_id)
            if path.exists() and _normalised(path.read_text(encoding="utf-8")) == content:
                return None
            path.write_text(content, encoding="utf-8")
            return self._commit(
                [filename(region_id)],
                message=message or f"Update {region_id}",
                origin=origin,
                when=when,
            )

    def propose(self, region_id: str, text: str, *, origin: str, message: str = "") -> str | None:
        """Apply a change that did not come from a person.

        Identical to :meth:`write` except that an owner-fixed region raises
        :class:`~hera_profiles.errors.RegionLocked`. ``hera_promptevo`` calls this one and
        never :meth:`write`, so the tier in the registry is enforced at the write rather than
        by remembering to filter what gets offered — a proposer with a bug still cannot
        rewrite ``safety``.
        """
        if region(region_id).tier is Tier.OWNER_FIXED:
            raise RegionLocked(region_id)
        return self.write(region_id, text, message=message, origin=origin)

    # -- history -----------------------------------------------------------------------

    def history(self, region_id: str, *, limit: int | None = None) -> list[RegionVersion]:
        """Every commit that touched this region, newest first."""
        region(region_id)
        if not self.initialised:
            return []
        args = ["log", f"--format={_LOG_FORMAT}{_RECORD}"]
        if limit is not None:
            args.append(f"--max-count={limit}")
        args += ["--", filename(region_id)]
        return [_parse_version(record) for record in self._git(*args).split(_RECORD) if record]

    def generation(self, region_id: str) -> int:
        """How many times this region has been written.

        The number ``hera_promptevo`` reports as a generation count. It is a property of the
        history rather than a counter someone has to remember to increment, which is why a
        rename would be so expensive: the history *is* the number.
        """
        return len(self.history(region_id))

    def show(self, region_id: str, ref: str) -> str:
        """This region's text as of one commit."""
        region(region_id)
        try:
            return _normalised(self._git("show", f"{ref}:{filename(region_id)}"))
        except MindError as exc:
            raise NoSuchVersion(region_id, ref) from exc

    def revert(self, region_id: str, ref: str, *, origin: str = "manual") -> str | None:
        """Restore an earlier version as a **new** commit on top.

        Never rewrites history: going back is itself a thing that happened, and a log that
        can be edited is not a record. Returns ``None`` when the region already says exactly
        that, which makes reverting twice harmless.
        """
        return self.write(
            region_id,
            self.show(region_id, ref),
            message=f"Revert {region_id} to {ref[:8]}",
            origin=origin,
        )

    # -- internals ---------------------------------------------------------------------

    def _init_repository(self) -> None:
        """Make the directory and the repository exist. Call with the lock held."""
        self.path.mkdir(parents=True, exist_ok=True)
        if not self.initialised:
            self._git("init", "--initial-branch=main")

    def _path_of(self, region_id: str) -> Path:
        return self.path / filename(region_id)

    def _commit(
        self,
        paths: Iterable[str],
        *,
        message: str,
        origin: str,
        when: datetime | None = None,
    ) -> str:
        self._git("add", "--", *paths)
        env: Mapping[str, str] | None = None
        if when is not None:
            stamp = when.isoformat()
            env = {"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
        self._git("commit", "-m", f"{message}\n\n{ORIGIN_TRAILER}: {origin}", env=env)
        return self._git("rev-parse", "HEAD")

    def _git(self, *args: str, env: Mapping[str, str] | None = None) -> str:
        """Run one git command in the repository and return its stdout, stripped.

        The identity flags are passed per invocation rather than written into the
        repository's config: this must work on a machine where git has never been set up,
        and it must not care what the user's global config says about signing.
        """
        command = [
            "git",
            "-C",
            str(self.path),
            "-c",
            f"user.name={COMMITTER_NAME}",
            "-c",
            f"user.email={COMMITTER_EMAIL}",
            "-c",
            "commit.gpgsign=false",
            *args,
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                env=_environment(env),
            )
        except FileNotFoundError as exc:
            raise MindError(
                "git is not installed, and the mind is a git repository. "
                "Install git, or point HERA_HOME somewhere its mind directory already exists."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise MindError(
                f"git {' '.join(args)} failed in {self.path}: {(exc.stderr or '').strip()}"
            ) from exc
        return completed.stdout.strip()


def _environment(extra: Mapping[str, str] | None) -> dict[str, str] | None:
    if extra is None:
        return None
    return {**os.environ, **extra}


def _normalised(text: str) -> str:
    """Strip surrounding whitespace and end with exactly one newline, or be empty.

    Every region goes through this on the way in and on the way out, so a trailing newline
    added by an editor is never a diff, and a region's rendered text never carries blank
    lines into the prompt.
    """
    stripped = text.strip()
    return f"{stripped}\n" if stripped else ""


def _seed_message(regions: Sequence[MindRegion]) -> str:
    if len(regions) == len(MIND_REGIONS):
        return "Seed the mind"
    return f"Seed {', '.join(item.id for item in regions)}"


def _parse_version(record: str) -> RegionVersion:
    sha, when, message, origin = record.strip("\n").split(_UNIT)
    return RegionVersion(
        sha=sha,
        when=datetime.fromisoformat(when),
        message=message,
        origin=origin.strip(),
    )
