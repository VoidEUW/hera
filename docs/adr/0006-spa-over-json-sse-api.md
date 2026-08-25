# 6. A SvelteKit application over a JSON and SSE API

- Status: accepted
- Date: 2026-08-26

## Context

The previous interface was server-rendered Jinja with HTMX and vanilla JavaScript, and no build
step at all. That had real virtues — no toolchain, no `node_modules`, partials that swapped
themselves — and real costs: the streaming path needed a hand-written parser in the browser that
mirrored the server's; out-of-band swaps became the standard way to update anything that was not
the primary target, with a documented habit of firing swaps at elements that might not be on the
screen; and testing meant asserting on HTML strings.

Hera should now feel like a **desktop application** — panes, keyboard navigation, a command
palette — and be reachable from a phone as an installable web app.

## Decision

`apps/api` is a **pure API**: versioned `/api/v1`, typed Pydantic responses, generated OpenAPI,
and Server-Sent Events for the turn stream. It renders no HTML.

`apps/web` is a **SvelteKit** application built with `adapter-static` into the API's static
directory, so one process serves one origin and there is no CORS.

TypeScript types for the API are **generated from the OpenAPI schema**. A route change breaks
the build rather than the browser.

## Consequences

- A Node toolchain enters the project, along with `npm ci` in CI and a build before release.
- Testing splits cleanly: `vitest` for stores and the event reducer, Playwright for the whole
  path from login to a rendered emotion card, `httpx` against the ASGI app for API contracts.
- The same API serves the browser, the phone, a future desktop shell and a command-line client
  without any of them being a special case.
- The server render stays authoritative for message content: the client renders optimistically
  while streaming, then replaces its view with the persisted event list at `done`, so live view
  and reload cannot disagree. That property came from the previous version and is worth keeping.
- Server-Sent Events, not WebSockets: the stream is one-directional, SSE reconnects on its own,
  and cancelling is closing the connection.
