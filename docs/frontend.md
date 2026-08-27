# The interface

The design language of `apps/core/web`: what it feels like, what it is made of, and how a turn
is put on screen.

**Status:** first pass, written from the initial brief. It is expected to deepen once there is a
running build to react to — the maintainer has said explicitly that the design language gets
adjusted then. Treat the *direction* as settled and the *values* as proposals: every hex code
and typeface below is a recommendation with a reason attached, and reasons can be argued with.

**Last updated:** 2026-08-27

---

## The brief

In the maintainer's words, condensed:

- The aesthetic reference is **Anthropic's Claude interface**. It is warm. *"ChatGPT's interface
  is too cold for a Greek goddess."*
- Hera is the Greek goddess: she should **embrace the power yet be familiar** — she is the
  goddess of family.
- **Dark and light** both, from day one.
- A **welcoming start screen**: mark, greeting, composer, nothing else.
- **Settings as a modal**, not a page — it feels better.
- A **sidebar with projects that expand into their chats**, so a chat is easy to find. Settings
  sits at the bottom, above the profile card.
- The settings screen for skills and MCP servers is *well-structured* and worth learning from.
- **A thinking animation** of her own.
- **Using a skill or a tool must be visible.** The interface should give as much feedback as
  possible.
- All of it *imitated but with our own design principles, so it gives a special feeling.*

And the principle underneath all of it, in the maintainer's words: *"my own version of my ideal
wish of Claude — something that reminds me of it but feels like my own."*

That is the tie-breaker for every decision in this document and the ones that follow it. Where a
choice is between **familiar** and **clever**, familiar wins: the muscle memory is the feature.
Where it is between **borrowed** and **ours**, ours wins: a copy would remind him of Claude
instead of being his. Most decisions here are one of those two sentences.

## The three qualities

The application has an identity of its own, separate from hers. Hera-the-assistant — her voice,
her stance, how she behaves in a conversation — is deliberately **not** settled here; that comes
later, and it belongs to the mind regions in `hera_profiles` rather than to a stylesheet. What
follows is what the *application* should feel like:

**Familiarity.** You already know how to use it. The layout is borrowed on purpose, muscle memory
is the feature, and no interaction here is novel for its own sake. It is also the domestic half of
her — the goddess of the household is someone you live with, not someone you consult. Concretely:
no invented navigation patterns, no gestures to discover, sentence case everywhere, and nothing
that has to be learned before the first message is sent.

**Openness.** Two senses, and they reinforce each other. She is open about *what she is doing* —
the activity gutter shows every skill she was given and why, every tool she called, every
permission she wanted, every failure she hit, and none of it is hidden behind a summary. And the
system is open: servers come from a JSON file you wrote, skills are Markdown directories you can
read, the mind is a git repository you can `cd` into, and there is nothing in `~/.hera` you cannot
open in an editor. The interface should never be the only way to see something.

**The feeling of power.** She is sovereign, and using her should feel like operating something
capable rather than something cute. That is keyboard-first, `⌘K`, parallel tool calls landing at
once and visibly, profiles you switch between, and any MCP server in the world attachable in four
lines of JSON. It is *not* density for its own sake or an aircraft cockpit — power reads as calm
here. Restraint is what makes capability feel like control instead of noise.

The three pull against each other in useful ways. Familiarity restrains openness from becoming
clutter; openness keeps power honest; power stops familiarity from becoming a toy. When a design
choice is hard, ask which of the three it is serving and which one it is spending.

## What we take, and what has to be ours

The structural patterns are free to adopt, and we adopt them wholesale, because they are simply
good: a collapsible left rail, projects disclosing their chats, a centred reading column, a
composer that stays put, settings in a modal with its own left nav, tool activity as quiet
collapsed rows above the prose, serif for reading and sans for chrome.

Three things cannot be borrowed and should not be:

- **The typeface.** *Anthropic Serif* is a commissioned face and not ours to install. Hera needs
  her own, and the shortlist below picks warmth over prestige.
- **The mark.** The orange starburst is Anthropic's trademark. Hera needs her own, and she has a
  far better one available — see *The signature*.
- **The exact palette.** Copying the clay orange is what would make this read as a Claude
  reskin rather than as Hera. The *temperature* is the thing worth keeping; the hues should come
  from her.

That is not a legal footnote, it is the whole difference between a clone and the "special
feeling" the brief asks for. Take the bones, bring our own blood.

## The story

Two things are true about Hera at once, and the interface has to hold both.

She is **sovereign** — queen of the gods, not an assistant. And she is **domestic** — the goddess
of marriage, family and the household, the one you live with rather than consult. Power and
familiarity. A cold interface gets the first and loses the second; a cute one does the reverse.

The resolution is in her own iconography, and it is almost too neat:

> Argus Panoptes had a hundred eyes and never slept. When he was killed, Hera set his eyes into
> the tail of the peacock, so that she would still see everything.

The brief's single strongest functional requirement is *"the UI should give you as much feedback
as possible."* Hera's own myth is about total, unblinking visibility. The interface that shows
you every skill it selected, every tool it called, every permission it wanted and every failure
it hit is not decorated with peacock eyes — it **is** the hundred eyes. That is the story, and it
is load-bearing rather than ornamental.

Her other attributes stay in reserve: the pomegranate (marriage, family, the hearth), the brass
diadem (sovereignty), and Homer's epithet *boōpis* — "ox-eyed", meaning wide, calm, unhurried
eyes. Calm is a design instruction. Nothing here should flicker.

## The signature

**The ocellus** — a single peacock eye — is the one element the interface is remembered by.

```
        ╭───────────╮          outer      warm ground, so it sits on any surface
      ╭─┤ ╭───────╮ ├─╮        ring       brass — her authority
      │ │ │ ╭───╮ │ │ │        iris       peacock teal — her attention
      │ │ │ │ ● │ │ │ │        pupil      the ground colour, punched through
      ╰─┤ │ ╰───╯ │ ├─╯
        ╰─┤       ├─╯
          ╰───────╯
```

It has to work at three sizes, and each has a job:

| Size | Where | What it does |
|---|---|---|
| 20–28 px | The mark, next to the wordmark on the start screen | Identity |
| 16 px | Her thinking indicator | Motion: she is looking |
| 8 px | The gutter beside every tool call, skill and permission event | The hundred eyes |

The third is the important one. A turn with six tool calls draws six eyes down its left gutter,
joined by a hairline. Activity becomes a **column of eyes** that you read at a glance — how much
she did, and where. Nothing else in the interface may use concentric circles.

## Colour

Warm on both ends. The dark ground is a warm charcoal, never blue-grey; the light ground is warm
paper, never white. The three accents are not interchangeable — each one means something, and
using the wrong one is a bug:

| Token | Means | Used for |
|---|---|---|
| `pomegranate` | **her** | The mark, the send action, the active chat, her name |
| `peacock` | **her attention** | Thinking, a tool running, the ocellus iris, live state |
| `brass` | **her authority** | Skills, permission cards, the ring of the mark, emphasis |

Mapping meaning onto hue is what keeps the palette from being decoration. If a colour appears
somewhere and you cannot say which of the three sentences above it is saying, it does not belong
there.

### Dark (default)

```
--ground            #15100E   the page
--surface           #1E1815   sidebar, composer, cards
--surface-raised    #272019   modal, hover, the settings sheet
--line              #362C26   hairlines, dividers, the activity gutter
--text              #F2E9E1   prose
--text-muted        #A79A90   labels, metadata, collapsed activity
--text-faint        #7A6E66   placeholders, disabled

--pomegranate       #D9636B
--peacock           #35A093
--brass             #C9A24C
--danger            #E0685E   refusals, failed tools
```

### Light

```
--ground            #FBF7F2
--surface           #FFFFFF
--surface-raised    #F4EDE4
--line              #E4D9CD
--text              #1E1613
--text-muted        #6E625A
--text-faint        #968A81

--pomegranate       #A93744
--peacock           #1D6157
--brass             #8E6E27
--danger            #B03A2E
```

Three appearance settings, matching the reference: **system**, **light**, **dark**. System is the
default, because a person who has already told their machine wants the same answer here.

## Typography

Serif to read, sans for chrome. The chat is prose and deserves a book face; buttons and labels
are not prose and should get out of the way.

| Role | Face | Why this one |
|---|---|---|
| Display | **Fraunces** | Variable, with `SOFT` and `WONK` axes. Old-style warmth with a little strangeness in it — antique without being a costume. Set `SOFT` high and `WONK` low. Used sparingly: the greeting, the wordmark, modal titles, empty states. |
| Body | **Source Serif 4** | The face the chat is set in. Warm, drawn for screens, variable, open licence. This is the role *Anthropic Serif* plays in the reference, and this is the honest answer to it. |
| Chrome | **Figtree** | Humanist sans with a soft edge. Deliberately **not Inter** — Inter is the neutral default and neutral reads as cold, which is the one thing the brief rules out. |
| Mono | **IBM Plex Mono** | Code blocks, tool arguments, model names. Warmer than JetBrains Mono and it has an actual voice. |

Alternative worth a look if the classical reading should be stronger: **Cormorant Garamond** for
display. More Greek, more delicate, harder to set well at interface sizes.

```
display-lg   40 / 1.15   Fraunces      the start-screen greeting
display      28 / 1.20   Fraunces      modal titles, empty states
h1           22 / 1.30   Fraunces
h2           18 / 1.35   Source Serif 4
body         17 / 1.65   Source Serif 4    chat prose — generous, unhurried
ui           14 / 1.45   Figtree           sidebar, buttons, labels
caption      12.5 / 1.40 Figtree           timestamps, provenance, metadata
mono         13.5 / 1.55 IBM Plex Mono
```

Measure caps at **68ch**. Longer lines are the fastest way to make a reading interface tiring.

## Motion

She is *ox-eyed*: wide, calm, unhurried. Nothing flickers, nothing bounces, nothing slides in
from off-screen. There is exactly one piece of choreography, and everything else is a fade or a
height change.

**The thinking indicator** is that one piece. The ocellus appears where her answer will begin;
its iris rotates once every four seconds and the brass ring breathes between 60 % and 100 %
opacity on the same cycle. Slow enough to read as attention rather than as a spinner. When the
first `text_delta` arrives it does not disappear — it shrinks to 8 px and takes its place at the
top of the activity gutter, where it stays as the first eye of that turn. The animation becomes
the record.

Everything else: 120 ms fades, 160 ms disclosure heights, `ease-out`. `prefers-reduced-motion`
replaces the rotation with a static ocellus at full opacity and removes every transition; the
interface must be completely usable and completely legible with all motion off.

## The screen

### Start

Mark, greeting, composer. The greeting is the one place the display face gets to be large, and
the one place Hera's voice is heard before she says anything.

```
┌──────────┬──────────────────────────────────────────────────────────┐
│          │                                                          │
│  rail    │                                                          │
│          │                    ◉  Good evening                       │
│          │                                                          │
│          │        ┌────────────────────────────────────────┐        │
│          │        │  What are we doing today?              │        │
│          │        │                                        │        │
│          │        │  ＋   coding ▾                    ↑     │        │
│          │        └────────────────────────────────────────┘        │
│          │                                                          │
└──────────┴──────────────────────────────────────────────────────────┘
```

The dropdown in the composer is the **profile** — the mind region set she is answering from — not
a model picker. There is one model (ADR 2); there are many of her.

### Chat

```
┌───────────────────────┬──────────────────────────────────────────────┐
│ ◉  Hera               │  Kerberos, in the notation from my slides  ▾ │
│                       │                                              │
│ ＋ New chat           │                              ┌─────────────┐ │
│ 🔍 Search        ⌘K   │                              │ you         │ │
│                       │                              └─────────────┘ │
│ PROJECTS          ＋  │                                              │
│  ▾ Hera               │  ┆◉ used  writing            skill · pinned  │
│      Frontend design  │  ┆◉ read  fs__read_file      12 ms           │
│      Tool layer       │  ┆◉ thought for 4s                        ▾  │
│  ▸ Cookbook           │                                              │
│  ▸ ChaOS Web          │  I pulled the exact notation from your        │
│                       │  slides. Here is how Kerberos runs:           │
│ PINNED                │                                              │
│    Minecraft plugins  │  ╭─────────────────────────────────────╮     │
│    Design             │  │ ◔  doubt                            │     │
│                       │  │    Slide 14 contradicts slide 9.    │     │
│                       │  ╰─────────────────────────────────────╯     │
│                       │                                              │
│ ⚙  Settings           │  ┌────────────────────────────────────────┐  │
│ ╭───────────────────╮ │  │  Reply…                                │  │
│ │ LK  Lukas       ▾ │ │  │  ＋   coding ▾                    ↑     │  │
│ ╰───────────────────╯ │  └────────────────────────────────────────┘  │
└───────────────────────┴──────────────────────────────────────────────┘
```

The rail collapses to icons. Projects disclose their chats inline, as in the reference — it is
genuinely easier to find a chat under the thing it belongs to than in one flat list sorted by
time. Settings sits directly above the profile card at the bottom, where the brief put it.

### Settings

A modal, because the brief says so and the brief is right: settings is somewhere you *go and come
back from*, and a modal keeps the conversation visible behind it. Left nav, content on the right,
search at the top.

```
        ┌──────────────────────────────────────────────────────┐
        │  🔍 Search                                        ✕  │
        │────────────┬─────────────────────────────────────────│
        │  General   │  Appearance                             │
        │  Profile   │      ▣ System   ☀ Light   ☾ Dark        │
        │  Mind      │  Chat font       Source Serif 4      ▾  │
        │  Skills    │  Motion          Full                ▾  │
        │  Servers   │                                         │
        │  Permissions│ Language        English              ▾  │
        │  Appearance│                                         │
        └────────────┴─────────────────────────────────────────┘
```

**Skills** and **Servers** get the list treatment from the reference — search, filter, sort by
last used, an add button, and one row per item with its icon, name, source and description. Two
Hera-specific additions: a skill row shows whether it is **pinned** to a profile, and a server row
shows whether it is **connected**, with its failure reason when it is not. `hera_tools` already
reports both — `ToolRegistry.status()` returns exactly `name`, `connected`, `tools` and `failure`
per server, so this screen is a direct rendering of that.

**Permissions** is the third list, and it has no equivalent in the reference: allow, deny and ask
rules over `server__tool` patterns, editable, with the rules that came from answering a
confirmation card marked as such.

## Projects

There are no folders. `hera_chats` owns **projects**, and a project is a container with
behaviour, the way the reference's are: a name, its own **instructions**, its own **files**, its
own **pinned skills**, and the chats that live inside it. A chat outside every project is
normal — that is what the start screen opens.

### Project or profile?

Projects and `hera_profiles` both put words into a prompt, so the line between them has to be
stated once and then held, or every future feature will be arguable in two places:

| | Answers | Lives in | Scope |
|---|---|---|---|
| **Profile** | *Who she is* — voice, stance, behavioural traits, the emotion vocabulary | Mind regions, in a git repository | Global. One of her. Changes rarely, and `hera_promptevo` may propose changes to it |
| **Project** | *What we are working on* — the domain, the conventions, the files that are context | Rows and files under `~/.hera` | This body of work. Many. Changes whenever the work does |

*The coding profile* and *the Hera project* compose: she is the same person in every project, and
she knows different things in each. If a piece of text would still be true in a project about
something else, it is a mind region; if it would not, it is project instructions. A project may
name a **default profile**, which is what the composer's dropdown is pre-set to when you open a
chat inside it.

### What lands when

Projects are the concept from the start, because renaming folders into them later would be a
migration for nothing. The *behaviour* arrives in two steps:

- **v0.1** — name, instructions, pinned skills, default profile. Instructions bind into the
  prompt as a slot. This is enough for a project to feel like one.
- **v0.2** — project files, with retrieval over them. Files need embeddings, which is
  `hera_memories`, which is v0.2. Until then the sidebar shows no files section rather than an
  empty one.

## A turn, rendered

This is the part that matters, because it is where the design meets the data. A turn is **a list
of events**, and the interface renders one component per variant. It never parses her text — that
rule is not a style preference, it is the single largest source of bugs in the previous version
and it is designed out (`CLAUDE.md`, ADR 2, ADR 3).

| Event | Renders as |
|---|---|
| `text_delta` | Her prose, `body`, streamed in |
| `thinking_delta` | The reasoning channel — collapsed by default, one line in the gutter |
| `tool_call_ready` | A gutter row: ocellus, verb, target, and its result when it lands |
| `tool_call_ready` where `name == "hera__emotion"` | An **emotion card**, inline where it was called |
| `turn_end` | Ends the turn; `reason: cancelled` marks it visibly as interrupted |

At `done`, the client throws away its optimistic view and re-renders from the persisted list. The
live view and a reload therefore cannot disagree, which is worth more than it sounds — it is what
makes every animated state above safe to be wrong about for a second.

### The activity gutter

Everything she did before speaking stacks above the prose as collapsed rows, each with its
8 px ocellus on a hairline. Quiet, in `caption` on `--text-muted`, expandable. A row carries the
verb, the target, and how long it took:

```
┆◉  used   writing                                    skill · pinned
┆◉  read   fs__read_file    ~/notes/kerberos.md              12 ms
┆◉  ran    shell__git       status                          210 ms
┆◉  thought for 4s                                              ▾
```

**Skills say why they are there.** ADR 5 selects them in code — pinned, `/slash`, or retrieved by
similarity — and the interface shows which of the three it was. A person needs to be able to tell
"she always has this" from "she went and found this", and it is also the only feedback loop that
tells you when your retrieval is picking the wrong thing.

### Emotion cards

`hera__emotion(kind, text)` renders inline, at the point in the event list where she called it —
between paragraphs, in the flow of the answer, because that is where she meant it.

```
╭─────────────────────────────────────────╮
│  ◔  doubt                               │
│     Slide 14 contradicts slide 9.       │
╰─────────────────────────────────────────╯
```

`kind` is **free text** (ADR 3) and she is told she may invent one. So the renderer needs a
`kind → icon + tone` map with a **generic fallback** that has to look deliberate rather than
broken — an unfamiliar emotion is her working correctly, not a missing asset. Group the known
kinds into four tones and colour the card's left edge by tone:

| Tone | Kinds | Edge |
|---|---|---|
| Warm | `agree`, `hope`, `excited`, `funny`, `joke` | `pomegranate` |
| Cool | `curious`, `surprised`, `doubt`, `ask` | `peacock` |
| Sharp | `warn`, `disagree`, `judge`, `annoyed` | `brass` |
| Soft | `sorry`, and every unknown kind | `--line` |

`text` may be absent — a card that is only a stance is valid and should render as just the icon
and the kind.

### The permission card

The one moment the interface blocks. An `ask` outcome from `hera_permissions` stops the turn and
puts the decision in front of a person, inline where the call would have happened:

```
╭─────────────────────────────────────────────────────────╮
│  ⬡  Run shell__git?                                     │
│     status --porcelain                                  │
│     Nothing outside this repository is written.          │
│                                                         │
│              [ Allow once ]  [ Always allow ]  [ Deny ] │
╰─────────────────────────────────────────────────────────╯
```

Brass edge — this is authority. The second line is the arguments; the third is `Outcome.reason`
from the rule, and filling that field in is why it exists. **Always allow** writes a rule and
says so afterwards, because a person should never wonder whether a decision stuck.

### When something fails

`hera_tools` never raises past the registry — a failed call is a `ToolResult` with a `Failure`,
which means each of these is a *render*, not an error boundary:

| `Failure` | Row reads | Tone |
|---|---|---|
| `denied` | "not allowed — <reason>" | `danger`, with a link into Permissions |
| `unknown_tool` | "no such tool" | muted; she is correcting herself and it is fine |
| `unavailable` | "<server> is not running" | `danger`, with the server's failure reason |
| `timeout` | "gave up after 60s" | `danger` |
| `tool_error` | The tool's own message | muted; the tool worked and said no |

The distinction between the muted two and the loud three is deliberate. `unknown_tool` and
`tool_error` are the system behaving correctly; alarming a person about them teaches them to
ignore the colour that matters.

Tool results carry content blocks, not just text (`ToolResult.blocks`), so a result can be an
image or a resource link. The expanded row renders them; it does not flatten them to a string.

## Voice

UI strings are **English**, through the i18n layer, so a German locale can be added without
touching a component. (The reference screenshots are in German because that is the reference's
locale, not ours.)

Sentence case. Active voice. A control says what happens: **Send**, not *Submit*. An action keeps
its name all the way through — the button that says **Always allow** produces a confirmation that
says *Always allowed*. Name things by what a person controls: **Servers**, not *MCP client
configuration*.

Failures explain what happened and what to do, in the interface's voice, and they do not
apologise. *"filesystem is not running — check the command in Servers"* beats *"Sorry, something
went wrong."* Empty screens are invitations: an empty Skills list says what a skill is and offers
the button, the way the reference does.

Hera's own voice — the greeting, and anything written as her rather than about her — is warm and
direct and never coy. She is the goddess of the household, not a mascot.

## Constraints the design cannot negotiate with

- **No parser in the browser.** The frontend renders event variants it is handed. A new thing she
  can do is a new variant, never a new regular expression.
- **The server render is authoritative** at `done`.
- **Every event variant needs a component**, including ones that arrive unknown — degrade
  visibly, never silently.
- **Desktop-shaped, PWA on the phone.** On a phone the rail becomes a sheet and the activity
  gutter collapses to a single summary row that expands; nothing is removed.
- **Keyboard first.** Visible focus, `⌘K` for search, the composer focused on load.

## Open

Waiting on the maintainer, who has said more of the story is coming:

1. **Her identity as an assistant** — voice, stance, how she behaves in a conversation. Settled
   later and in the mind regions, not here. It may still overturn the pomegranate / peacock /
   brass reading, which is the one part of this document that is about *her* rather than about
   the application.
2. **Display face** — Fraunces (warm, slightly antique) or Cormorant Garamond (classical, Greek,
   more delicate)?
3. **The mark** — does the ocellus land, and should the wordmark be set in the display face or
   drawn?
4. **Where thinking lives** — a gutter row that expands in place, as drawn, or its own column?
5. **Project instructions vs. a project's own profile** — a project can name a default profile
   *and* carry instructions. If that turns out to be one control too many, instructions win and
   the profile becomes a per-chat choice only.

Everything in this document is provisional until there is a build to argue with, which is the
point at which it gets rewritten rather than amended.
