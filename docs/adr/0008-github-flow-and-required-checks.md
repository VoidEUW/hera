# 8. GitHub Flow, protected `main`, required checks

- Status: accepted
- Date: 2026-08-26

## Context

The previous project had no test suite in the repository. Verification scripts existed — dozens
of them, `verify_auth`, `verify_dream`, `verify_memory2` and so on — but they lived in session
scratchpads, and a later refactor broke their import paths, so a suite of roughly thirty scripts
became unrunnable in one commit and nobody noticed until it was needed. Everything was committed
straight to `main`.

## Decision

**GitHub Flow.** `main` is always releasable and protected. Work happens on short-lived branches
(`feat/`, `fix/`, `chore/`, `docs/`, `refactor/`), reaches `main` through a pull request, and is
squash-merged. Linear history, no direct pushes, branches deleted on merge. Commit subjects follow
Conventional Commits.

**Required status checks**: `lint`, `types`, `test`, `web`, `e2e`. Conversation resolution
required. Force-push and deletion blocked on `main`.

**Required approvals: zero.** This is a single-maintainer repository; a one-approval rule would
lock the maintainer out of their own project, and CodeRabbit reviews as a bot — a bot review
cannot satisfy an approval requirement. The gate here is CI plus a machine reviewer, not a human
signature.

**CodeRabbit** reviews every pull request, configured in `.coderabbit.yaml` with the layering
rules from `ARCHITECTURE.md` as explicit path instructions.

**Tests live in the repository.** Coverage gate at 90 %, matching the foundation libraries.
Model behaviour is tested against `FakeProvider`; anything needing a live endpoint is marked
`live` and never runs in CI.

## Consequences

- Every change costs a branch and a pull request, including one-line fixes. That is the price of
  a reviewed, bisectable history, and squash-merging keeps it cheap.
- Branch protection is configured through the GitHub API and is not represented in this
  repository. The ruleset is described here so it can be recreated.
- A red check blocks a merge. Flaky end-to-end tests would therefore be genuinely expensive,
  which is why the suite runs against a fake provider and never a real model.
