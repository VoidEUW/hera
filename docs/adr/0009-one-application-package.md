# 9. One application package, `hera-core`

- Status: accepted
- Date: 2026-08-27
- Supersedes the layout clause of [1](0001-uv-workspace-monorepo.md) and
  [6](0006-spa-over-json-sse-api.md); everything else in both records stands

## Context

[ADR 1](0001-uv-workspace-monorepo.md) put the application at `apps/api` and the interface at
`apps/web`, and [ADR 6](0006-spa-over-json-sse-api.md) described what each one is. Neither
directory has been created yet — the whole application layer is still ahead of us — so this is
a choice about where to start rather than a migration.

Two directories under `apps/` implied a symmetry that does not exist. They are not two
deliverables: `apps/web` builds with `adapter-static` **into** `apps/api`'s static directory,
so one artefact is an input to the other, one process serves both, and neither is separately
deployable or separately versioned. A tag would have had to release the pair. Meanwhile every
piece of configuration paid for the split twice — workspace members, ruff `src`, pytest
`testpaths`, coverage `source`, two CI path guards, two dependabot entries, two CodeRabbit path
rules — and each of those is a place where the two can be wired up inconsistently.

The split also reads as a layering boundary, which it is not. The API imports every library and
the web app imports none of them; the actual boundary is HTTP, and it is enforced by the API
returning JSON rather than by a directory.

## Decision

The application is **one package, `hera-core`, at `apps/core/`**.

```
apps/core/
  pyproject.toml         name = "hera-core"
  src/hera_core/         FastAPI: /api/v1 JSON + SSE, alembic/, static/
  web/                   SvelteKit, built with adapter-static into src/hera_core/static/
  tests/
```

It stays under `apps/`, not in `packages/`. That is the load-bearing half of this record:
`packages/` means *a library another project can consume by naming its subdirectory* (ADR 1),
and `tests/test_layering.py` scans exactly that directory and demands an explicit allow-list per
member. The application is the one thing that legitimately imports everything, and admitting it
to `packages/` would either weaken the allow-list into a formality or force a special case into
the guard. `hera_core` is above the line the guard draws, and
`test_no_package_imports_the_application` now names it.

**Nothing else from ADR 6 changes.** The API renders no HTML. Types are generated from the
OpenAPI schema. The turn streams over Server-Sent Events. The server render is authoritative at
`done`. One origin, no CORS. Testing still splits into vitest, Playwright and `httpx` against
the ASGI app.

## Consequences

- One workspace member for the application, one CI path guard, one dependabot entry, one
  version. `v1.2.3` releases `hera-core` and that is the whole application.
- `apps/core/web/` is a Node project inside a Python distribution. The wheel ships the built
  assets from `src/hera_core/static/`, never `web/` itself, so the build order is explicit:
  `npm run build` before `uv build`.
- Migrations live in `apps/core` for the reason they were going to live in `apps/api` — it is
  the only place that imports every package, so it is the only place `alembic autogenerate`
  sees the whole schema.
- The name is `hera-core`, not `hera-api`, because the package is no longer only the API.
  Nothing may import it; if a library needs something from it, the dependency is inverted and
  the answer is a port in the library, the way `hera_tools.ports` is.
