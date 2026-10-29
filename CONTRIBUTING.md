# Contributing

## Setup

You need Python 3.12+, [uv](https://docs.astral.sh/uv/) and Node 24.

```bash
git clone https://github.com/VoidEUW/hera.git
cd hera
uv sync --all-packages
cd apps/core/web && npm ci && cd ../..
uv run playwright install chromium        # only for the browser tests
pre-commit install                        # the fast half of the loop, before every commit
uv run hera serve                         # http://localhost:8756
```

`hera serve` serves the interface from `apps/core/src/hera_core/static/`; after changing anything
under `apps/core/web` run `npm run build` there (or use `npm run dev`, which proxies to a running
server). One checkout, one sync. Every library is a workspace member under `packages/`, so an edit in one
is visible to the others immediately with no reinstall.

## The loop

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run coverage run -m pytest && uv run coverage report   # gate: 90 %
cd apps/core/web && npm run check && npm run lint && npm run test:unit
npm run build                                             # the browser tests drive this build
cd ../.. && uv run pytest -m e2e                          # Playwright against a scripted model
```

`-m "not e2e and not live"` is the fast loop. `live` marks anything that needs a real model
endpoint and never runs in CI. `uv run python tests/e2e/capture_preview.py <dir>` drives the
interface and writes screenshots and a console log — what the CI **capture** job does for every
pull request, and the way to look at a UI change before asking anybody else to.

## Branching — GitHub Flow

`main` is always releasable and protected. Everything else is a short-lived branch off `main`:

| Prefix | For |
|---|---|
| `feat/` | new behaviour |
| `fix/` | a bug |
| `chore/` | tooling, dependencies, CI |
| `docs/` | documentation only |
| `refactor/` | structure, no behaviour change |

Open a pull request using the template, let CI and CodeRabbit run, squash-merge, delete the branch.
No long-running branches, no direct pushes to `main`, no merge commits — history stays linear.
Issues have forms for a feature and for a bug; say *what is wrong and why it matters* before how
to fix it.

### Commit titles and release notes

Commit messages — and so **pull request titles**, because a squash-merge takes the title — follow
[Conventional Commits](https://www.conventionalcommits.org/): `feat(chats): stream tool results as
events`. There is no changelog file to update. The release notes *are* the changelog, and they are
written from these titles when a tag is pushed ([ADR 22](docs/adr/0022-the-changelog-is-the-release-notes.md)):

| Type | Appears as |
|---|---|
| `feat` | Features |
| `fix` | Fixes |
| `perf` | Performance |
| `refactor` | Refactoring |
| `docs` | Documentation |
| `chore`, `ci`, `build`, `test`, `style`, `revert` | Maintenance |
| `feat!:` or a `BREAKING CHANGE:` footer | Breaking changes, first |

Write the title for a reader of the release page: what changed, in the present tense, with the
scope in brackets (`web`, `chats`, `ci`…). Dependency bumps are folded into one line. A title that
is not conventional lands under *Other*, and CI says so on the pull request. The reasoning that
does not fit a title goes in the pull request description or an ADR, not in a file nobody opens.

The old hand-written changelog is kept, frozen, as
[docs/changelog-history.md](docs/changelog-history.md).

## Writing code here

- **Imports point downwards.** See the table in [ARCHITECTURE.md](ARCHITECTURE.md). A package
  importing from a package above it is a bug, and CodeRabbit is told to flag it.
- **Typed, strictly.** `mypy --strict` passes with no `# type: ignore` that lacks a reason on the
  same line. `from __future__ import annotations` at the top of every module.
- **A theme is imported, and a component reads tokens only** ([ADR 21](docs/adr/0021-a-theme-is-imported-data.md)).
  Colour, type, shape and motion come from `src/lib/themes/`, which `npm run theme:import` writes and
  nobody edits by hand. No literal colour, font, radius or duration in a component, and every
  control is a primitive in `lib/components/ui/` — a feature component may not open a `<button>`,
  `<input>`, `<textarea>` or `<select>`, nor read `--brass` where the theme does not name it.
  Guard tests fail on each. A new component is added to `/design` and to the theme's *Hera
  amendments*.
- **A shortcut is a control that also exists on screen** (#112). Chords live in
  `apps/core/web/src/lib/keys.ts` as data that names the control each mirrors; the screen that owns
  the control registers the handler and shows the key. A chord-only feature is the interface's
  version of what [ADR 5](docs/adr/0005-deterministic-skill-routing.md) refuses for skills.
- **Everything is English** — code, comments, docstrings, commit messages, UI strings, prompts
  and stored content. User-visible text goes through the i18n layer so a German locale can be
  added without touching components.
- **New table?** Prefix `__tablename__` with your package's prefix and add an Alembic revision in
  `apps/core`. Cross-package references are bare `UUID` columns, never `ForeignKey`.
- **New model capability?** One new variant in the `hera_providers` event union, one branch where
  it is persisted, one branch where it renders. If you are writing a parser, stop and check
  whether it should be a tool call instead.
- **Tests are not optional.** A package without a test for the behaviour you added does not
  reach 90 % and CI fails. LLM behaviour is tested against `FakeProvider`, never a live model —
  anything needing a real endpoint is marked `@pytest.mark.live` and stays out of CI.

## The two foundation packages

`hera_storage` and `hera_prompts` live in `packages/` like everything else, but they are held to
a stricter contract: **no domain concept, and no import of any other `hera_*` package — not even
each other.** `hera_storage` has no table and no chat; `hera_prompts` does not know what a tool,
a memory or a skill is. If you catch yourself typing "chat" in either, something is wrong.

Both must stay liftable into a project that has nothing to do with Hera.
`tests/test_layering.py` gives them an empty allow-list, so a stray import fails the build. See
[ADR 1](docs/adr/0001-uv-workspace-monorepo.md).

## Using one package somewhere else

Every member of `packages/` is a real distribution with its own name, version and build
backend, so another project — `hera-code`, say — can depend on exactly one of them without
cloning the workspace or pulling in anything else:

```toml
# in the other project's pyproject.toml
[project]
dependencies = ["hera-skillsets"]

[tool.uv.sources]
hera-skillsets = { git = "https://github.com/VoidEUW/hera", subdirectory = "packages/hera_skillsets", tag = "hera-skillsets-v0.1.0" }
```

That is the whole declaration. If the package depends on other members — `hera_skillsets`
needs `hera_storage` — uv resolves those from the **same commit and subdirectory** on its own,
because the root declares them as workspace sources. The consumer names one package and gets a
consistent set; nothing else in the workspace is fetched, built or imported.

The prerequisite lives here, not there: every member that another member depends on needs an
entry in the root `[tool.uv.sources]` as `{ workspace = true }`. Miss one and `uv sync` fails
with *"included as a workspace member, but is missing an entry"*.
`tests/test_workspace.py::test_internal_dependencies_have_a_workspace_source` keeps that list
honest.

Pin a **tag**, not a branch — a branch means the consumer silently moves whenever this
repository does.

## Tags are the moving point

Nothing ships off a branch. A tag is the only thing that causes a release, and a release is the
only thing that gets deployed:

| Tag | Releases | Consumed by |
|---|---|---|
| `v1.2.3` | the application | the deployment |
| `hera-skillsets-v0.1.0` | one package, wheel attached | other projects, e.g. `hera-code` |

`release.yml` refuses **any** tag whose version disagrees with the `pyproject.toml` it belongs
to — `packages/<name>/` for a package, `apps/core/` for the application — so a consumer can never
be pinned to a lie and the interface can never show the version of the release before it.
`main` being green means it is *releasable*, not released.

**One version per releasable thing, declared once.** `pyproject.toml` is where it is written and
packaging is where it is read back: `hera_core.__version__` asks `importlib.metadata` for the
installed distribution rather than repeating the number, `/api/v1/health` reports that, and the
interface shows it from `workspace.version`. To display it somewhere new, read that field —
do not add a constant.

### Cutting an application release

1. Open a `chore(release): bump hera-core to 1.2.3` pull request that changes `version` in
   `apps/core/pyproject.toml` (and the matching line in `uv.lock`, which `uv lock` rewrites) and
   merge it once green — `main` is protected, so the bump goes through a pull request like
   everything else.
2. Tag the merge commit and push the tag: `git tag -a v1.2.3 -m v1.2.3 && git push origin v1.2.3`.

`release.yml` does the rest. It publishes a **GitHub release** whose notes are written from the
commit titles, and builds the Docker image.

| Tag | Published as | Notes cover | Image tags |
|---|---|---|---|
| `v1.2.3-rc1` | pre-release, never "latest" | since the previous tag, rc or not | `1.2.3-rc1` and `rc` (moves to the newest) |
| `v1.2.3` | release, the repository's "latest" | everything since the previous *release*, so all of its candidates | `1.2.3` and `latest` |

To see the notes before tagging, run the **Release** workflow by hand from the Actions tab with the
tag name (`v1.2.3`, and `HEAD` as the commit if the tag does not exist yet): it prints them into the
job summary and publishes nothing.

While developing both sides at once, point at the checkout instead:

```toml
hera-prompts = { path = "../hera/packages/hera_prompts", editable = true }
```

To cut a *package* release, bump `version` in its `pyproject.toml` and tag:

```bash
git tag hera-prompts-v0.1.3 && git push origin hera-prompts-v0.1.3
```

`uv build --package hera-prompts` produces the wheel, identical to what a standalone repository
would have built — publishing to an index later needs no restructuring.

**Skills are not Python packages.** A `SKILL.md` directory is content: consume it with a git
clone or a sparse checkout, or let `hera_skillsets` sync it into `~/.hera/skills/`. The same
directory can be pointed at by Claude Code.

## Dependency updates and security patches

Dependabot opens one pull request per bump. Do not merge them one by one into `main`: each was cut
from `main` and carries its own lockfile hunk, so the second one conflicts with the first and
nothing proves the set works together.

1. **Triage.** A bump that fails CI blocks only itself. Read the real error before deciding: a
   failure in the install step is usually a peer-dependency constraint (hold the bump back and say
   why in the pull request), and a timeout in an unrelated test is usually a flake (re-run it, and
   run the suite locally before believing either).
2. **Branch from the last tag, not from `main`.** Name it `chore/security-patch-X.Y.Z`. If `main`
   has nothing past the tag but documentation, the two are the same commit and you may branch from
   `main`. If `main` has moved for real, branch from the tag (`release/X.Y`) so the patch contains
   the bumps and nothing else; a bump that only works with code newer than the tag belongs to the
   next minor version instead.
3. **Apply the bumps by hand.** Edit the version floors in the `pyproject.toml` files and
   `package.json`, then regenerate the lockfiles (`uv lock`, `npm install --package-lock-only`)
   instead of merging the Dependabot branches. Check that the lockfile diff names only the
   packages you meant to change.
4. **Prove the behaviour did not change.** Run the whole loop — ruff, mypy, coverage, `pytest -m
   e2e`, and in `apps/core/web` the check, lint, unit tests and build. Then confirm that the diff
   against the tag touches only manifests and lockfiles:
   `git diff vX.Y.Z HEAD --stat -- packages apps ':!*.lock' ':!*pyproject.toml' ':!*package*.json'`
   must show nothing but comments and documentation.
5. **One pull request, titled `chore(deps): ...`.** List every bump in the description, and the
   ones held back with their reason. Close the Dependabot pull requests it supersedes.
6. **Release it.** A bump that fixes an advisory, or that changes a runtime dependency, ships as a
   patch version through *Cutting an application release* above. Development tooling alone does
   not need a release. When the branch came from a tag rather than `main`, merge the tag forward
   into `main` afterwards and resolve lockfile conflicts by keeping the newer versions.

Check the repository's Dependabot security alerts at the same time; an advisory with no pull request
is still an open one.

## Architecture decisions

Anything that changes the shape of the system gets a file in [docs/adr/](docs/adr/): the context,
the decision, the consequences. Numbered, never edited after the fact — superseded instead.
