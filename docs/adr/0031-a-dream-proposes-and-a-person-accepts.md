# 31. A dream proposes and a person accepts; training is scored by a judge and checked by a person

- Status: proposed
- Date: 2026-10-29

## Context

Dreaming was v0.2.0's fifth milestone, moved out, and it is back in v0.3.0
([#251](https://github.com/VoidEUW/hera/issues/251)). The aim is better results the next time a kind
of task comes back. Two ways of getting there were asked for: learning from what happened in a
person's own chats, and learning from a dataset somebody chose on purpose. In both, what changes is
the **prompt**, meaning a person's mind regions and memories. The model's weights do not change.

The seams are already in place:
- `MindRepository.propose()` refuses an owner-fixed region, while `write()` is the person's path.
- `Hera-Origin` is a commit trailer with `dream:<uuid>` already documented.
- `hera_promptevo` has an allow-list in `test_layering.py` and no code.
- Every memory is a file that `forget` switches off rather than deletes
  ([ADR 16](0016-a-memory-is-a-file-and-all-of-them-are-in-the-prompt.md)).

[ADR 28](0028-what-belongs-to-a-person.md) gives each person their own mind and memories, so a
dream reads one person's chats and proposes to that person.

The prototype dreamed, and `docs/prototype.md` keeps what it learned:
- **Variants, chosen by the person:** "the model mutates, the user selects".
- **Rejections as counter-examples:** they came back in the next dream.
- **Compaction:** a merged memory with a list of what it replaces.
- **A dream log.**

It also recorded what it deliberately did **not** build:
- **The model scoring itself on generic test questions.** That rewards length and confidence and
  says nothing about whether a change suits the person.
- **Automatic acceptance above a threshold.**
- **Random string mutation.**

Its conclusion was that without a metric, a claimed quality gain means nothing.

A further risk applies to any system that improves itself from its own output: it drifts toward
its own summaries. Each pass of a summary has less in it than the one before, and the mind gets
blander and longer. The prototype saw the start of this, since accepted proposals coloured every
later dream.

## Decision

**Dreaming and training both produce proposals, and nothing is applied until a person accepts it.
In a dream, the person selects between variants. In training, a dataset measures, a judge applies
the measure, and the person checks a sample of the judge's verdicts.**

### Dreaming: consolidation and experience
- **It reads:**
  - the person's chats since the last dream, as visible text, tool calls and results;
  - signals from those chats: failed tool results, `hera__ask` questions, *Try again*, cancelled or
    failed turns, and corrections;
  - all of the person's memories, including switched-off ones;
  - the evolvable regions;
  - the last three rejections per target.
- **It proposes four kinds of change:**
  - **Compacted memories.** The originals are switched off and kept, and the new memory records
    `merged_from`.
  - **New memories**, for patterns that only show across several chats.
  - **Region rewrites**, through `propose()`.
  - **Skill drafts.** An admin accepts these, because skills are instance-wide.
- **Up to three variants per idea.** Each variant's card shows its diff, its token change and a
  **replay**: a real past question answered under the current prompt and under the variant, side
  by side. The person picks one, edits one, or rejects them all. There is no numeric score; the
  person is the measure.

### Training: a dataset chosen on purpose
- **The dataset** is JSONL in chat format (`{"messages": [...]}`). The final assistant message is
  the target, and an optional `rubric` says what a good answer must do.
- **The split** is a fixed 80/20. Failures on the training part are what variants are mutated
  from, and only the held-out part scores them.
- **A judge model pre-scores** answers against the target and the rubric. It defaults to the
  active model, and an admin can pick a stronger one.
- **The person checks afterwards.** They see the score change and about five items: the ones the
  judge was least sure of, or the ones where variants disagreed. A disagreement is stored and goes
  back to the judge as a calibration example, so later runs need fewer checks.

### Against collapse
Dreams recombine real experience rather than feeding on their own summaries.
1. **Material is real, then mutated.** Replays and training variants start from real questions and
   dataset items, perturbed. A dream's own output is never the input of another.
2. **No summary of a summary.** Compaction reads back to `merged_from`.
3. **An anchor.** A variant is always compared with the accepted version. The person's own version
   (generation 0) is always restorable through `revert()`.
4. **Growth is explained.** A rewrite that makes a region more than about 20% longer says why on
   its card.
5. **Variety.** Variants overlapping at 0.8 or more are merged, and rejections come back as
   counter-examples.

### Where it lives
- **`hera_promptevo`** holds run planning, proposals, mutation prompts and scoring.
  - Transcripts arrive through a port the application fills from `hera_chats`, because
    `hera_chats` is not on the allow-list.
  - Tables are prefixed `evo_`.
- **Accepted changes** are commits with `Hera-Origin: dream:<run>` or `training:<run>`. Memories
  gain `source = "dream"`.
- **Runs** are background tasks in `apps/core`, started by hand (*Dream now*) or on a per-person
  schedule.
- **Cost** is recorded in the usage ledger
  ([ADR 25](0025-usage-is-a-ledger.md)) with source `dream` or `training`.

## Consequences

- **The tab finally has something behind it.** Settings → Dreaming stops being a disabled tab, and
  the promise in `README.md` that she offers changes to herself is kept.
- **Training costs real tokens.** The estimated cost (examples × variants × calls) is shown before
  a run starts.
- **A judge can be wrong in a consistent way.** The person's check is what catches it, and the
  calibration examples are what make that check cheaper over time rather than a permanent chore.
- **A rejected idea will come back reworded.** The prototype found rewordings of known things to be
  the main source of dismissed cards. The coverage filter (0.8 of a known entry's significant
  tokens) is carried over.
- **The prompt changes, not the model.** Fine-tuning weights is a different project, and nothing
  here prepares for it.
