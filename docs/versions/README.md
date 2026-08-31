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

*Before* the tag is cut it is still the plan, and a plan that changes says so in place: v0.2.0 lost
**two** of its five milestones mid-version — dreaming to v0.3.0 and the redesign to v0.2.1 — and
both sentences explaining that are in v0.2.0, next to the three that are left. It also keeps the
milestone *numbers*, so M4 still means memory: renumbering after the fact would make every commit
message and status entry that says M4 wrong. Dropping a milestone silently is what turns *we decided
not to* into *we forgot*.

| | |
|---|---|
| [v0.2.0](v0.2.0.md) | The deepening pass: projects, a scratchpad, artifacts, memory |
| [v0.2.1](v0.2.1.md) | The polish pass: `read_resource`, the redesign, hotkeys, the emotion vocabulary |
| [v0.3.0](v0.3.0.md) | The widening pass: dreaming, moved out of v0.2 · a sandbox · `hera-code` |

v0.1.0 has no document here — it was planned in `docs/status.md` and in the eleven decision records
before this convention existed. [`CHANGELOG.md`](../../CHANGELOG.md) is its record.
