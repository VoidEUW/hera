# 22. The changelog is the release notes, written from the commits

- Status: accepted
- Date: 2026-10-21

## Context

`CHANGELOG.md` was written by hand, per release, in prose. The prose was good and it did not last:
its `[Unreleased]` section stopped being kept up around v0.2.1-rc1, and four release candidates
and the whole interface rework went by without a line in it. A file that has to be remembered is
the thing that gets forgotten ([#200](https://github.com/VoidEUW/hera/issues/200)).

Meanwhile every change already arrives as a squash-merged pull request whose title is a
Conventional Commit, and `release.yml` already built a GitHub release body from `git log` — a flat
list of subjects, limited to `apps/core`, published for a release candidate as if it were a
release.

## Decision

**The changelog is the notes of each GitHub release, and the notes are written from the commit
titles when a tag is pushed.** There is no changelog file to maintain.

- `.github/scripts/release_notes.py` groups the titles — features, fixes, performance, refactoring,
  documentation, maintenance, and *Other* for one that is not a Conventional Commit — puts breaking
  changes first, and folds dependency bumps into one line. It links the pull request behind each
  entry.
- **A release candidate lists what changed since the previous tag**, and a **release lists
  everything since the previous release**, so `v0.2.1` covers all of its candidates in one place.
  The application's notes are every commit in the range; a package's are the ones touching its
  directory.
- A tag with a suffix (`-rc4`) is published as a **pre-release**, is never the repository's
  "latest", and its image is never `:latest` — it is `:rc`, which moves to the newest candidate.
  `:latest` is always the newest release.
- A CI check on the pull request title keeps the input honest. It is advisory: it tells the author
  and does not hold a fix.
- The `Release` workflow run by hand with a tag name prints the notes that tag would get and
  publishes nothing.
- The old file is kept, frozen, as `docs/changelog-history.md`; the root `CHANGELOG.md` is a pointer.

## Consequences

- A release needs no writing, so a release candidate costs a tag. The price is that the notes are
  only as good as the titles, and they say *what changed*, not *why it mattered* — the reasoning
  stays where it already lives: the version documents, `docs/status.md` and the ADRs.
- The prose that used to live in the changelog (why a thing is the way it is) now has to go in the
  pull request description or an ADR, which is where a reader of the code looks anyway.
- A squash-merge title that is not conventional shows up under *Other*. That is visible, and
  fixable by editing the release — it is not silently dropped.
- The notes are a view of history: they can be regenerated for any tag, so a better grouping later
  improves every past release rather than only the next.
