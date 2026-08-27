# hera-skillsets

`SKILL.md` packages on disk, and the router that picks them **in code**.

```python
from hera_skillsets import SkillLibrary, SkillRouter, render

router = SkillRouter(SkillLibrary())
routing = router.select("/tdd how do I test this streaming loop?", pinned=["writing"])

routing.text          # "how do I test this streaming loop?" — the command is stripped
routing.selections    # [Selection(skill=writing, reason=pinned), Selection(skill=tdd, ...)]
render(routing)       # the string for hera_profiles' `skills` slot
```

## Why the router exists

ADR 5. The target model does not reliably notice that a skill applies, and a mechanism that
only works when the model volunteers is not a mechanism. So selection is server-side, in three
passes, before the model sees the turn:

| Pass | Chosen by | Reason shown |
|---|---|---|
| Pinned | the profile or the project | `pinned` |
| Explicit | a `/skill-name` in the composer | `slash` |
| Retrieved | the skill's `description`, scored | `retrieved` |

Every selection carries **why**. The activity gutter shows "she always has this" separately
from "she went and found this", and that difference is the only feedback loop that tells you
retrieval is picking the wrong thing.

## Retrieval without an endpoint

ADR 5 names cosine similarity over embeddings, with **keyword overlap as the fallback when
embeddings are unavailable**. The fallback is what runs by default, and it is not a
placeholder: a skill that silently stops arriving because a model endpoint is down looks
exactly like a skill that was not relevant, which is the one confusion this design exists to
avoid. Wire an `Embedder` to improve it; nothing breaks when you do not.

The fallback weights each term by how few skills contain it, so a match on "kerberos" outweighs
a match on "using". A skill is scored on how much of *its own* description the turn covered —
scoring the turn's coverage instead would reward whichever description was longest.

## The format is Claude Code's

Unchanged, on purpose: the same directory can be pointed at by Claude Code, and skills written
for Claude Code work here.

```
~/.hera/skills/tdd/
  SKILL.md          ---\nname: tdd\ndescription: …\n---\n<markdown>
  mocking.md        named in the prompt, not read by this package
```

**The directory name is the identifier**, not the frontmatter `name`. It is what `/slash`
addresses and what survives someone editing the file's first lines; a frontmatter name that
disagrees is reported as a problem rather than honoured, because two sources of truth for an
identifier is how a skill becomes unreachable under the name it appears with.

## Nothing raises for bad content

A skill with unparseable YAML, no description, or an empty body still loads, carrying
`problems` written for a person to read. A directory with no `SKILL.md` at all comes back as a
`BrokenSkill` in `Catalogue.broken`. A Hera that refuses to boot over a stray colon in
someone's YAML is worse than one skill marked broken on the settings screen.

## What it does not do

It does not write to the skills directory — syncing is somebody else's job, and a package that
rewrites the folder you point it at is one you cannot safely point at your own. It does not
know what a profile or a project is: pins arrive as a list of names, already merged.
