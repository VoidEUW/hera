# 17. A stance is a sentence, and a question stands on its own

- Status: accepted
- Date: 2026-08-31
- Supersedes: [3](0003-emotions-as-tool-calls.md)

> **ADR 3 was right about the mechanism and wrong about the feature.** It is superseded rather
> than edited, because the thing worth keeping is the argument it made: a stance shown as a *tool
> call* instead of a text grammar deleted a parser from the browser and a parser from the server,
> and that reasoning still holds for every card in the interface. What did not hold is that there
> should be a stance to show at all.

## Context

`hera__emotion(kind, text)` has been in the catalogue since v0.1. Beside her prose she could show
a small card — *agree*, *doubt*, *warn* — drawn from a fourteen-word vocabulary that a person could
edit on Settings → Emotions, rendered into the prompt per turn and used to colour the card, so the
two could not disagree.

Driven against a real endpoint over v0.2, it does not work, and
[`docs/versions/v0.2.1.md`](../versions/v0.2.1.md) § 4 wrote down the observation while it was
fresh: she rarely reaches for a stance at all, and the ones she does reach for look close to
arbitrary — a `curious` where the answer is plainly confident, a `warm` on a correction. That
document listed three explanations and four possible responses, and deliberately decided none of
them.

The three explanations are all real, and they compound.

**Several stances are the same occasion.** `disagree`, `doubt` and `judge` all fire on *I think
this is wrong*; `curious`, `excited` and `hope` all fire on *this is going somewhere*. When several
entries fit, which one gets picked is noise. From outside it looks like the model choosing at
random, because it is.

**One of them had become a tool.** The vocabulary still contained `ask` — *"You need something from
them to go further"* — which is exactly what `hera__ask` does and has done since v0.2 M1. A stance
and a tool competing for the same occasion is the overlap ADR 12 removed between `note` and the
scratchpad, in a place nobody went back to look.

**The feature is shaped against how a model writes.** A stance is described as something to call
*alongside* prose, as often as is honest — a request to interrupt an answer several times to file
a small form. A model that writes fluently either forgets or complies mechanically, and both look
like the same failure on screen.

None of these is fixable by a shorter vocabulary, which is what makes this a decision rather than
a tuning exercise. The occasions overlap because *feelings overlap*; a four-word list has the same
problem with fewer words. And the third explanation is not about the vocabulary at all.

**What the feature was for is worth stating before removing it**, because it is not nothing: the
card gave a person something real, which was openness about how she was holding what she said.
That is the thing being given up, and the reason this option was listed fourth rather than first.

## Decision

Two changes, in this order, because the second depends on the first.

### `hera__ask` stops borrowing the emotion vocabulary

`ask` was already a separate tool with its own description; what coupled it to the emotions was its
`kind` argument, which read from the same `emotions.json` list, was documented in terms of it, and
picked the colour `QuestionCard` was drawn in. Removing the vocabulary under it would have broken a
question card that has nothing to do with stances.

So `kind` becomes a **closed set of three, about the question**: `unsure`, `blocked`, `choice`.
Those are the three occasions the `uncertainty` mind region already describes — a fact only they
have, something that cannot go on without them, two readings that lead somewhere genuinely
different. It is a `Literal` in the tool's input schema, so there is nothing for the model to
invent and nothing for the interface to look up.

`AnswerRequired.kind` stays a plain `str` on the persisted event, for the reason
`ToolResultEvent.failure` is one: `hera_chats` may not learn what `hera__ask`'s schema says, and an
event list is a record of *what happened* — a turn persisted before the set was closed carries a
stance word and still has to load. The card draws a kind it does not recognise as nothing.

### `hera__emotion` is removed, along with everything that fed it

The tool, `DEFAULT_EMOTIONS`, `~/.hera/emotions.json` and its three routes, Settings → Emotions,
`EmotionCard`, the `SLOT_EMOTIONS` prompt slot, and the `emotion_usage` mind region.

**Removed, not left unwired**, which is the opposite of what `note` gets — and the difference is
the argument. An unwired tool is a capability *this deployment* happens not to have, and saying so
beats a model concluding it cannot do the thing and telling the person. There is no deployment in
which showing a stance as a card is the right move, so there is nothing to say.

What replaces it is nothing, and that is the decision rather than an omission. A stance she means
is a sentence she writes: *I think this is wrong, and here is why* is the same information as a
card saying `disagree`, in the place a reader is already looking, at no cost in round trips and
with no vocabulary to pick out of. `tone` and `character` are the mind regions that govern it, they
already exist, and they are editable — which is more control than the card ever offered, since the
card could only ever be shown or not shown.

An `~/.hera/emotions.json` left over from an install that had one is **ignored, never deleted**,
the way `mind/emotion_vocab.md` was. Nothing in this project removes a file somebody may have
edited.

## Consequences

- **One tool fewer, and one screen fewer.** `TOOL_NAMES` loses `emotion`; the settings modal loses
  a tab. `GET /emotions` answers 404, and there is a test asserting it, for the reason the absent
  `artifact_list` and the absent memory-listing tool have one: an absence nobody pinned is an
  absence somebody adds back.
- **The mind is thirteen regions, not fourteen.** `emotion_usage` asked *when is showing a reaction
  worth interrupting an answer for*, which is a question with no mechanism left behind it.
- **A question card is drawn from three kinds this interface owns.** Its label is the *person's*
  wording rather than the tool's — `blocked` is what the model passes, *she cannot go on* is what
  it means to whoever is being asked — and only `blocked` is set apart in colour, because it is the
  one of the three where the turn is genuinely stopped on the reply.
- **The openness the card gave is genuinely lost**, and nothing here pretends otherwise. What
  remains is the activity gutter, which says what she *did*, and her prose, which says what she
  thinks. If the loss turns out to matter, the thing to reach for is not this tool again: it is a
  stance as an optional field on the answer (v0.2.1 § 4, option 3), which costs no round trip and
  has no vocabulary to disagree with — and which needs a real answer to *where does it live when
  the model does not emit one* before it is worth building.
- **ADR 3's mechanism argument is untouched and still binding.** What she did is an event variant,
  never something read back out of prose. Removing the emotion card removes a card; it does not
  reopen the parser question, and nothing in this record should be read as permission to.
