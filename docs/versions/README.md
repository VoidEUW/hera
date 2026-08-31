# Version documents

One file per version, written **before** the work rather than after it: what that version is for,
what lands in it, in what order, and what is deliberately left out.

This is not `docs/status.md` and not `CHANGELOG.md`, and the three are easy to collapse into each
other by accident:

| | Answers | Tense |
|---|---|---|
| `docs/versions/vX.Y.Z.md` | *What are we building, and why in this order* | Future. Frozen once the version ships |
| [`docs/status.md`](../status.md) | *Where does the build stand right now* | Present. A snapshot, rewritten as milestones land |
| [`CHANGELOG.md`](../../CHANGELOG.md) | *What changed, for somebody who was not here* | Past. Append-only |

A version document stops being edited when its tag is cut. If the plan turned out wrong, that is
worth reading later — the reasoning is the point, and a document quietly corrected after the fact
teaches nothing. Corrections go into the next version's document, or into an ADR when they change
the shape of the system.

| | |
|---|---|
| [v0.2.0](v0.2.0.md) | The deepening pass: projects, artifacts, the redesign, memory, dreaming |
| [v0.2.1](v0.2.1.md) | What the emotion vocabulary is for — noted while building v0.2, not scheduled |

v0.1.0 has no document here — it was planned in `docs/status.md` and in the eleven decision records
before this convention existed. [`CHANGELOG.md`](../../CHANGELOG.md) is its record.
