#!/usr/bin/env python3
"""Release notes from Conventional Commit titles.

Run by ``release.yml`` when a tag is pushed, and by its dry run before one is. The notes are the
changelog: they are written *from the commits*, so there is no file to keep up and nothing that
can fall behind. That only works while the titles are honest, which is why the pull request title
(it becomes the squash commit) is checked in CI.

Two rules decide what a release contains:

* **A release candidate lists what changed since the previous tag of its family**, rc or not --
  each rc answers *what is new since the last one I tried*.
* **A final release lists everything since the previous final**, so ``v0.2.1`` covers all of its
  release candidates in one place.

The application's notes are every commit in the range. A *package* release
(``hera-prompts-v0.1.3``) is filtered to that package's directory, because the rest of the
repository is not in the wheel.

Standard library only: the runner needs nothing installed to render the notes.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass

#: Heading, in the order they are printed, and the commit types that fall under each.
SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Breaking changes", ()),
    ("Features", ("feat",)),
    ("Fixes", ("fix",)),
    ("Performance", ("perf",)),
    ("Refactoring", ("refactor",)),
    ("Documentation", ("docs",)),
    ("Maintenance", ("chore", "ci", "build", "test", "style", "revert")),
    ("Other", ()),
)

COMMIT = re.compile(
    r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]+)\))?(?P<bang>!)?:\s*(?P<subject>.+?)\s*$"
)
PULL = re.compile(r"\s+\(#(?P<number>\d+)\)\s*$")
TAG = re.compile(
    r"^(?:(?P<package>hera-[a-z0-9-]+)-)?v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<suffix>[0-9A-Za-z.-]+))?$"
)
DEPENDENCY_SCOPES = ("deps", "deps-dev")
BUMP = re.compile(r"^(?:bump|update)\s+\S.*\s(?:from|requirement)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Entry:
    """One commit, read."""

    kind: str
    scope: str | None
    subject: str
    breaking: bool
    number: str | None
    sha: str

    @property
    def dependency(self) -> bool:
        """A bump by Dependabot or by hand: a version moving, nothing of ours changing."""
        if self.kind not in ("chore", "build", "ci"):
            return False
        return self.scope in DEPENDENCY_SCOPES or bool(BUMP.match(self.subject))


def parse_commit(title: str, sha: str, body: str = "") -> Entry:
    """Read a commit title. One that is not a Conventional Commit is kept whole, under *Other*."""
    title = title.strip()
    pull = PULL.search(title)
    number = pull["number"] if pull else None
    if pull:
        title = title[: pull.start()]
    breaking_body = "BREAKING CHANGE" in body
    found = COMMIT.match(title)
    if found is None:
        return Entry("other", None, title, breaking_body, number, sha)
    return Entry(
        kind=found["type"],
        scope=found["scope"],
        subject=found["subject"],
        breaking=bool(found["bang"]) or breaking_body,
        number=number,
        sha=sha,
    )


def _precedence(tag: str) -> tuple[object, ...] | None:
    """A tag's place in version order, or ``None`` if it is not a version tag.

    A release outranks its own release candidates, and ``rc10`` outranks ``rc9``: the suffix is
    split into words and numbers so neither is compared as text.
    """
    found = TAG.match(tag)
    if found is None:
        return None
    suffix = found["suffix"]
    parts: list[object] = []
    for word in (suffix or "").replace("-", ".").split("."):
        for piece in re.findall(r"\d+|[A-Za-z]+", word):
            parts.append((1, int(piece)) if piece.isdigit() else (0, piece))
    return (
        int(found["major"]),
        int(found["minor"]),
        int(found["patch"]),
        1 if suffix is None else 0,
        tuple(parts),
    )


def is_prerelease(tag: str) -> bool:
    found = TAG.match(tag)
    return bool(found and found["suffix"])


def package_of(tag: str) -> str | None:
    found = TAG.match(tag)
    return found["package"] if found else None


def previous_tag(tag: str, tags: list[str]) -> str | None:
    """The tag whose changes this one picks up from.

    Same family only (the application, or one package). For a release candidate that is the
    newest earlier tag of any kind; for a final it is the newest earlier *final*.
    """
    here = _precedence(tag)
    if here is None:
        return None
    family = package_of(tag)
    earlier = [
        (key, other)
        for other in tags
        if other != tag
        and package_of(other) == family
        and (key := _precedence(other)) is not None
        and key < here
        and (is_prerelease(tag) or not is_prerelease(other))
    ]
    return max(earlier, key=lambda pair: pair[0])[1] if earlier else None


def _ref(entry: Entry, repo: str | None) -> str:
    """Where the change came from: its pull request, or failing that the commit."""
    if entry.number and repo:
        return f"[#{entry.number}](https://github.com/{repo}/pull/{entry.number})"
    if entry.number:
        return f"#{entry.number}"
    return f"`{entry.sha}`"


def _line(entry: Entry, repo: str | None) -> str:
    scope = f"**{entry.scope}**: " if entry.scope else ""
    return f"- {scope}{entry.subject} ({_ref(entry, repo)})"


def _heading(entry: Entry) -> str:
    if entry.breaking:
        return "Breaking changes"
    for heading, kinds in SECTIONS:
        if entry.kind in kinds:
            return heading
    return "Other"


def render(
    entries: list[Entry],
    *,
    tag: str,
    previous: str | None,
    repo: str | None,
) -> str:
    """The notes, as Markdown."""
    lines: list[str] = []
    if is_prerelease(tag):
        lines += [f"> **Pre-release.** A release candidate for `{_base(tag)}`; not the latest.", ""]

    # Dependency bumps are real changes and also forty lines of noise, so they are one line with
    # the pull requests behind it. One that breaks something stays where it is.
    dependencies = [entry for entry in entries if entry.dependency and not entry.breaking]
    rows: dict[str, list[str]] = {heading: [] for heading, _ in SECTIONS}
    for entry in entries:
        if entry not in dependencies:
            rows[_heading(entry)].append(_line(entry, repo))
    if dependencies:
        noun = "update" if len(dependencies) == 1 else "updates"
        refs = ", ".join(_ref(entry, repo) for entry in dependencies)
        rows["Maintenance"].append(f"- **deps**: {len(dependencies)} dependency {noun} ({refs})")

    for heading, _ in SECTIONS:
        if rows[heading]:
            lines += [f"### {heading}", "", *rows[heading], ""]
    if not entries:
        lines += ["No changes since the previous tag.", ""]

    if previous and repo:
        lines.append(f"**Full changelog**: https://github.com/{repo}/compare/{previous}...{tag}")
    elif previous:
        lines.append(f"**Full changelog**: {previous}...{tag}")
    return "\n".join(lines).rstrip() + "\n"


def _base(tag: str) -> str:
    found = TAG.match(tag)
    if not found:
        return tag
    prefix = f"{found['package']}-" if found["package"] else ""
    return f"{prefix}v{found['major']}.{found['minor']}.{found['patch']}"


def _git(*arguments: str) -> str:
    return subprocess.run(["git", *arguments], check=True, capture_output=True, text=True).stdout


def collect(tag: str, previous: str | None, path: str | None) -> list[Entry]:
    """The commits in ``previous..tag``, newest first, merges left out."""
    span = f"{previous}..{tag}" if previous else tag
    command = ["log", "--no-merges", "--pretty=format:%h%x1f%s%x1f%b%x1e", span]
    if path:
        command += ["--", path]
    entries = []
    for record in _git(*command).split("\x1e"):
        if not record.strip():
            continue
        sha, title, body = [*record.strip("\n").split("\x1f"), "", ""][:3]
        entries.append(parse_commit(title, sha.strip(), body))
    return entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--previous", help="override the previous tag (default: worked out)")
    parser.add_argument(
        "--rev",
        help="the commit the notes run up to (default: the tag; HEAD for a tag not made yet)",
    )
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    parser.add_argument("--path", help="only commits touching this directory (a package release)")
    args = parser.parse_args()

    previous = args.previous or previous_tag(args.tag, _git("tag", "--list").split())
    notes = render(
        collect(args.rev or args.tag, previous, args.path),
        tag=args.tag,
        previous=previous,
        repo=args.repo,
    )
    sys.stdout.write(notes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
