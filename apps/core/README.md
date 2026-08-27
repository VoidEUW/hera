# hera-core

The application: a FastAPI JSON and Server-Sent Events API at `/api/v1`, and the SvelteKit
interface it serves from the same origin.

```bash
uv run hera init     # prepare ~/.hera: schema, mind repository, one profile
uv run hera check    # is the data directory usable?
uv run hera serve    # http://127.0.0.1:8756
```

This is the one package that legitimately imports every library, which is why it lives under
`apps/` and not in `packages/` — see [ADR 9](../../docs/adr/0009-one-application-package.md).
Nothing may import it back.

## Layout

```
src/hera_core/
  wiring.py        every package joined up; the seam a test replaces
  boot.py          refuse a pre-v0.1 ~/.hera (ADR 7), then make a fresh install usable
  deps.py          current_user — the multi-user seam
  schemas.py       what the API sends; the browser's types are generated from it
  sse.py           a turn on the wire
  api/             one router per screen
  migrations/      alembic; the only place that sees the whole schema
  static/          the built interface, written here by `npm run build`
web/               SvelteKit
```

## Two things worth knowing

**Sessions are opened deliberately during a turn.** A `Depends`-provided session lives as long
as the response, and a streaming response lives as long as the model takes — which would hold a
SQLite write transaction open across a minute of generation. So the turn endpoint prepares in
one short unit of work, commits, streams holding nothing, and opens a second one at the end to
record.

**Cancellation is a supported outcome.** When the browser goes away, Starlette closes the
generator, `hera_chats` closes the turn as `cancelled` with the text that did arrive, and the
`finally` block persists it. Navigating away mid-answer keeps the half you read.

## The `done` frame

Every `ChatEvent` goes out as an SSE frame named by its own `type`. When the turn ends, one
more frame — `done` — carries the **persisted** message. The client throws away everything it
rendered optimistically and re-renders from that, which is what makes the server render
authoritative: live view and reload cannot disagree.

## Building the interface

```bash
cd web && npm ci && npm run build     # writes ../src/hera_core/static/
```

The wheel ships `src/hera_core/static/`, never `web/` itself, so the order is explicit:
`npm run build` before `uv build`.
