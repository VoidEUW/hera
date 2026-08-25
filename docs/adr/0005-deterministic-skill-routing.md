# 5. Skills are selected by code, not by the model

- Status: accepted
- Date: 2026-08-26

## Context

Skills are `SKILL.md` packages: a Markdown file with frontmatter (`name`, `description`) and a
body of instructions for a particular kind of task. The format is worth adopting as-is — it is
what Claude Code uses, and the `hera-skills` repository is already written in it.

The usual mechanism around that format is **progressive disclosure**: the prompt lists only names
and one-line descriptions, and the model calls a tool to load a skill's body when it judges the
skill relevant. The previous version implemented exactly this as `import_skills`, and the
`hera-skills` repository contains a `hera-skill-router` skill whose entire content is an
instruction to remember to look for skills — a prompt-level attempt to fix a behaviour problem.

Testing against the target model showed it does not reliably notice that a skill applies. The
same weakness appears with that model in Claude Code. A mechanism that only works when the model
volunteers is not a mechanism.

## Decision

Skill selection happens **server-side, before the model sees the turn**, in
`hera_skillsets.SkillRouter.select()`, in this order:

1. **Pinned** — skills attached to the active profile or project are always injected. No
   judgment involved.
2. **Explicit** — a `/skill-name` invocation typed in the composer is resolved before the turn
   is built, the way a slash command works in Claude Code.
3. **Retrieved** — cosine similarity between the turn and each skill's `description`, with
   keyword overlap as the fallback when embeddings are unavailable, above a floor and capped by
   token budget.

Selected skills are injected **in full** into the `skills` prompt slot.

The `hera__skill(name)` tool stays available, and the prompt still lists the catalogue, so a
model that *does* reach for a skill mid-task can get one. Nothing depends on it happening.

## Consequences

- Skills cost prompt tokens whether or not they turn out to be relevant. The cap and the floor
  are the controls; a 35B model's context is large enough that one or two full skills is not a
  problem.
- Retrieval quality now depends on the `description` field, which becomes the most important line
  in a `SKILL.md`. This should be said in the skill-authoring documentation.
- `hera-skill-router/SKILL.md` is retired — its job is code now.
- Skills remain portable in both directions: the same directory can be pointed at by Claude Code,
  and skills written for Claude Code work here unmodified.
