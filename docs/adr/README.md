# Architecture decisions

One file per decision that changes the shape of the system: the context it was taken in, the
decision itself, and what it costs. Numbered, and not edited after the fact — a decision that
turns out wrong gets a new record that supersedes the old one, so the reasoning stays readable
later.

| # | Decision | Status |
|---|---|---|
| [1](0001-uv-workspace-monorepo.md) | A uv-workspace monorepo, with two foundation libraries kept outside | accepted · layout superseded by [9](0009-one-application-package.md) |
| [2](0002-qwen-only-target-model.md) | Qwen3.6-35B is the only target model | accepted |
| [3](0003-emotions-as-tool-calls.md) | Emotion cards are tool calls with an open vocabulary | accepted |
| [4](0004-mcp-as-the-tool-layer.md) | MCP is the tool layer | accepted |
| [5](0005-deterministic-skill-routing.md) | Skills are selected by code, not by the model | accepted |
| [6](0006-spa-over-json-sse-api.md) | A SvelteKit application over a JSON and SSE API | accepted · layout superseded by [9](0009-one-application-package.md) |
| [7](0007-fresh-start-no-legacy-import.md) | Start from an empty `~/.hera/` | accepted |
| [8](0008-github-flow-and-required-checks.md) | GitHub Flow, protected `main`, required checks | accepted |
| [9](0009-one-application-package.md) | One application package, `hera-core` at `apps/core/` | accepted |
| [10](0010-chat-events-wrap-the-provider-union.md) | The persisted stream wraps the provider union rather than extending it | accepted |
