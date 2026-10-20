# 21. A theme is imported data, and it changes tokens rather than structure

- Status: accepted
- Date: 2026-10-20

## Context

The interface's look lived in three places that each restated part of the others: the values in
`apps/core/web/src/app.css`, the rationale in `docs/frontend.md`, and comments in the components
that used them. Every open design issue (#100–#117, #121, #140/#141, #158, #171) was about to
re-derive a piece of a foundation that did not exist — a button, a toast, a motion duration — and
each would have done it slightly differently ([#182](https://github.com/VoidEUW/hera/issues/182)).

The Hera Theme Builder now exports a complete theme as one Markdown file with a picture beside it
(`docs/themes/hera-theme-heaven.md`, schema `hera-theme/1`): the palette in both modes, four type
faces, shape and density, an icon specification, a duration and curve for every moving part, and
— on top of the tokens — a structural "look" for each component (`open`, `soft`, `float`) plus
per-part overrides. The export also shows that Heaven is one of a family (Earth, Moon, Parchment &
Laurel, Aegean, Hearth, …), so whatever reads a theme has to expect more than one.

## Decision

**A theme is data that is imported, not CSS that is written.** `npm run theme:import <export.md>`
in `apps/core/web` reads a builder export and writes everything the interface needs from it:

- `src/lib/themes/<id>.css` — the export's own token block, scoped to
  `:root[data-palette='<id>']`; the default theme is emitted on bare `:root` as well, so the page
  has tokens before any script runs;
- `src/lib/themes/<id>.fonts.css` — the `@fontsource-variable` imports for its four faces;
- `src/lib/themes/registry.json` — id, name, description, the two ground colours (the PWA chrome
  needs them before the page paints) and which theme is the default.

The export in `docs/themes/` is the source; the generated files are never edited by hand, and
re-running the import on an unchanged export must produce no diff. Adding a theme is running the
script on another export. **Heaven is the only theme shipped**, and the default.

**A theme changes tokens, not structure.** Colour, faces, sizes, radii, density, icon stroke and
every motion slot come from the theme; the structure of each component is Heaven's, whatever theme
is active. The export's `styles` and `parts` are recorded and not read. Making structure switchable
is a later decision, and nothing here prevents it.

**Components read tokens and nothing else.** No literal colour, font, radius or duration in a
component; a guard test fails on one, and a second guard fails when a component reads a token that
some registered theme does not define.

**The gutter is a dot, not a picture.** Heaven's trace draws a 7 px dot in the row's state colour
beside a small mono-capital verb. The per-kind marks (scroll, globe, quill, brain, stele, wrench)
are retired; the ocellus stays the wordmark and the thinking indicator, and is still the only
concentric-circle mark.

Where the export contradicts itself, its own rules decide — "follow the text", and a part override
beats its component's look:

| Question | Answer | Because |
|---|---|---|
| Light-first or dark default? | Dark tokens on `:root`; the stored appearance stays **system** | The rule text says dark is the default; "light-first" is the tagline |
| Where does a toast go? | Top centre, 3000 ms | `parts.toast.place` and the motion slot's `wo` |
| Top-bar title face | The interface face | The look table, which is structure; the component prose is description |
| Question and permission cards | No frame, boxed option keys | `parts.qc.frame` / `qc.keys` override the component's look |

The role tokens keep their names — `--brass` is authority, `--laurel` live state, `--pomegranate`
her — even where a theme makes laurel blue, because a token names what a colour *says*, and that
is the rule `docs/frontend.md` § Colour has always stated.

## Consequences

- One place for values (the export), one for why (`docs/frontend.md`), one for what each component
  is ([#182](https://github.com/VoidEUW/hera/issues/182) and the components themselves).
- The fonts change: Cormorant Garamond, Newsreader, Albert Sans and Fira Code replace Fraunces,
  Source Serif 4, Figtree and IBM Plex Mono. The reading column (`--column`) is a measurement of
  68ch in the body face and is re-measured for it.
- The previous palette, Parchment & Laurel, is no longer shipped. It returns by importing its
  export, like any other theme.
- A theme picker appears in Settings only once more than one theme is registered.

## Alternatives considered

- **Hand-written theme CSS.** Every future theme would be a copy edited by hand, which is how the
  drift this record exists to end began.
- **Switchable looks and parts now.** Three looks for ~28 components plus every part option is a
  large amount of CSS to build and test for themes that do not exist yet; tokens alone already
  make the family possible.
- **Keeping the per-kind gutter marks.** They were drawn one per milestone and never matched each
  other (#100); the spec's dot says what a reader needs — what state the row is in — and the verb
  beside it already says what kind of thing happened.
