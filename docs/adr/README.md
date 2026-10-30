# Architecture decisions

One file per decision that changes the shape of the system: the context it was taken in, the
decision itself, and what it costs. Numbered, and not edited after the fact — a decision that
turns out wrong gets a new record that supersedes the old one, so the reasoning stays readable
later.

| # | Decision | Status |
|---|---|---|
| [1](0001-uv-workspace-monorepo.md) | A uv-workspace monorepo, with two foundation libraries kept outside | accepted · layout superseded by [9](0009-one-application-package.md) |
| [2](0002-qwen-only-target-model.md) | Qwen3.6-35B is the only target model | accepted · target list widened by [19](0019-preferred-models-widen-past-qwen.md) |
| [3](0003-emotions-as-tool-calls.md) | Emotion cards are tool calls with an open vocabulary | **superseded by [17](0017-a-stance-is-a-sentence-and-a-question-stands-alone.md)** |
| [4](0004-mcp-as-the-tool-layer.md) | MCP is the tool layer | accepted |
| [5](0005-deterministic-skill-routing.md) | Skills are selected by code, not by the model | accepted |
| [6](0006-spa-over-json-sse-api.md) | A SvelteKit application over a JSON and SSE API | accepted · layout superseded by [9](0009-one-application-package.md) |
| [7](0007-fresh-start-no-legacy-import.md) | Start from an empty `~/.hera/` | accepted |
| [8](0008-github-flow-and-required-checks.md) | GitHub Flow, protected `main`, required checks | accepted |
| [9](0009-one-application-package.md) | One application package, `hera-core` at `apps/core/` | accepted |
| [10](0010-chat-events-wrap-the-provider-union.md) | The persisted stream wraps the provider union rather than extending it | accepted |
| [11](0011-markdown-and-tex-in-the-browser.md) | Her prose is typeset in the browser, as Markdown and TeX | accepted |
| [12](0012-a-chat-has-a-scratchpad.md) | A chat has a scratchpad, and a tool call carries the chat it is in | accepted |
| [13](0013-an-artifact-is-a-file-she-publishes.md) | An artifact is a file she publishes | accepted |
| [14](0014-skill-resources-are-readable.md) | Skill resources are readable | accepted |
| [15](0015-running-code-in-a-container.md) | Running code happens in a container, and here is which claim that makes | **deferred to v0.4** |
| [16](0016-a-memory-is-a-file-and-all-of-them-are-in-the-prompt.md) | A memory is a file, and every enabled one is in the prompt | accepted |
| [17](0017-a-stance-is-a-sentence-and-a-question-stands-alone.md) | A stance is a sentence, and a question stands on its own | accepted · supersedes [3](0003-emotions-as-tool-calls.md) |
| [18](0018-a-model-may-carry-request-options.md) | A model may carry request options, and Hera does not know what they mean | accepted |
| [19](0019-preferred-models-widen-past-qwen.md) | Preferred models widen past Qwen, and a model may decline tool calling | accepted |
| [20](0020-the-stable-part-of-the-prompt-goes-first.md) | The stable part of the prompt goes first, and what changes goes last | accepted |
| [21](0021-a-theme-is-imported-data.md) | A theme is imported data, and it changes tokens rather than structure | accepted |
| [22](0022-the-changelog-is-the-release-notes.md) | The changelog is the release notes, written from the commits | accepted |
| [23](0023-permission-rules-are-kept-over-the-shipped-policy.md) | Permission rules are kept in a file, laid over the policy Hera ships with | accepted |
| [24](0024-the-servers-screen-writes-mcp-json.md) | The Servers screen writes `mcp.json`, and a tool that is switched off is not offered | accepted |
| [25](0025-usage-is-a-ledger.md) | What a turn cost is kept in a ledger, not read back out of the messages | accepted |
| [26](0026-a-question-may-come-in-threes.md) | One question card may hold up to three questions | accepted |
| [27](0027-an-account-is-a-session-and-a-role.md) | An account is a server-side session and a role | proposed |
| [28](0028-what-belongs-to-a-person.md) | What belongs to a person, and what belongs to the instance | proposed |
| [29](0029-the-desktop-app-is-a-shell-over-a-frozen-hera.md) | The desktop app is a Tauri shell over a frozen `hera` | proposed |
| [30](0030-git-is-bundled-not-assumed.md) | Git is bundled with the desktop app, not assumed | proposed |
| [31](0031-a-dream-proposes-and-a-person-accepts.md) | A dream proposes and a person accepts; training is scored by a judge and checked by a person | proposed |
| [32](0032-what-a-person-says-is-encrypted-at-rest.md) | What a person says is encrypted at rest, with the instance's key | proposed |
