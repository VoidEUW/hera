# docs

| File | What it is |
|---|---|
| [adr/](adr/) | Architecture decision records — why the system has the shape it has. Start here. |
| [hera-storage.md](hera-storage.md) | The specification `hera_storage` was built against. A contract, in German, kept as written. |
| [hera-prompts.md](hera-prompts.md) | The specification the `hera_prompts` compiler was built against. A contract, in German, kept as written. |
| [prototype.md](prototype.md) | The guidance file of the previous version of Hera. **Historical.** |

## About `prototype.md`

The prototype was one FastAPI application with Jinja templates, HTMX, a German interface, a
hand-written tool registry and a text call grammar built around GPT-OSS-20B. Everything
structural in that document is obsolete — the layout, the module paths, the tool layer, the
prompt assembly and the frontend have all been replaced. Where it disagrees with
[ARCHITECTURE.md](../ARCHITECTURE.md) or an ADR, it is wrong.

It is kept because it is the only written record of *why* several mechanisms exist, and those
observations were paid for in debugging:

- the emotion vocabulary is open, and the freedom to invent a kind has to be granted at system
  level — a user turn cannot grant it;
- message roles must strictly alternate after a single system message, or the chat template
  returns an empty answer;
- a revert is a new forward commit, never a `git reset` or a checkout of an old SHA;
- memory retrieval budgets are per tier, not shared, so a noisy tier cannot crowd out a
  deliberately small one;
- rejected proposals are information: they come back as counter-examples in the next dream.

Read it before rebuilding a feature it describes. Do not read it for how anything is wired.
