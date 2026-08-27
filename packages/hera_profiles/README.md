# hera-profiles

Who she is.

Her character, role, tone, conduct and the rest are **mind regions** — one Markdown file each,
in a real git repository at `$HERA_HOME/mind`. A **profile** is a row that selects from them:
which regions apply, what any of them says instead for this profile, and a handful of scalar
behaviour traits. `PromptBuilder` compiles the two into a `hera_prompts.Prompt`.

```python
from hera_profiles import MindRepository, PromptBuilder, ProfileRepository

mind = MindRepository()
mind.ensure()                       # git init, seed any region without a file

builder = PromptBuilder(mind)
prompt = builder.build(profile)     # or build() for the bare mind

result = prompt.render(
    bindings={"tools": catalogue_text, "skills": skill_text},
    registry=hera_profiles.BEHAVIOUR_TRAITS,
)
result.messages                     # the frame; history goes in the middle
```

## The three ideas

**Regions are files in git.** Every change to who she is has an author, a timestamp, a diff and
a way back, and you can read all of it with `git log -p` while this application is switched
off. When `hera_promptevo` starts proposing rewrites, that history is how you tell evolution
from drift. `generation()` is a commit count, not a column — which is why a region id is never
renamed.

**Owner-fixed vs. evolvable is enforced at the write.** `write()` is the person's door and opens
every region, including `safety`. `propose()` is everything else's door and raises
`RegionLocked` on an owner-fixed one. Two doors rather than one door plus a filter on what gets
offered, so a bug in a proposer cannot become a bug in her conduct.

**A profile owns no text.** It disables regions, overrides individual ones, sets traits. One
copy of her character lives on disk, and a coding profile is a small diff against it rather than
a second full mind.

## Slots

The builder produces a prompt with named holes in it. This package may not know what a tool, a
skill, a memory or a project is, so it does not try:

| Slot | Filled by | When |
|---|---|---|
| `tools` | the rendered `hera_tools` catalogue | every turn with tools configured |
| `skills` | whatever `hera_skillsets` routed in (ADR 5) | when the router selected something |
| `memories` | `hera_memories` | v0.2 |
| `project` | the project's instructions | when the chat lives in a project |

An unbound slot renders as nothing — not as an empty tag. A Hera with no MCP servers does not
tell the model about an empty tool list.

## What it is not

It does not render, does not stream, and does not know what a chat is. It answers *who she
is*; a **project** answers *what we are working on*, and that lives in `hera_chats`.
`docs/frontend.md` holds the line between the two.
