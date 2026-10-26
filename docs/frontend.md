# The interface

The design language of `apps/core/web`: what it feels like, what it is made of, and how a turn
is put on screen.

**Status:** first pass, written from the initial brief — and now **built**, so the argument can
start. Treat the *direction* as settled and the *values* as proposals: every hex code and
typeface below is a recommendation with a reason attached, and reasons can be argued with.

Everything structural in this document exists in `apps/core/web`: the rail with projects
disclosing their chats, the start screen, settings as a modal with its own left nav, the ocellus
at all three sizes, the activity gutter with a reason on every skill, the question and permission
cards inline, dark and light, and the mobile sheet. What is *not* built is listed under **Open**
at the bottom.

**Last updated:** 2026-08-27 · **Built:** yes — `uv run hera serve`

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
- **The exact palette.** Not the accent — the accent was never in danger, because rose, teal and
  gold together are nobody's but hers. It is the **neutrals**: a cream ground under white cards
  is the thing a person recognises from across a room, and no amount of unfamiliar accent on top
  of it changes that. The *temperature* is worth keeping and the *hue* had to come from her, so
  the ground is a red-warm plaster rather than a yellow-warm oatmeal. See **Colour**.

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
| 16–22 px | Her thinking indicator | Motion: she is looking |

The activity gutter used to be the third size — an 8 px eye beside every event, the hundred eyes
of Argus. Since [ADR 21](adr/0021-a-theme-is-imported-data.md) a gutter row is a small dot in the
row's state colour beside a mono-capital verb: what a reader needs from the column is *what state
each row is in*, and the verb already says what kind of thing happened. Nothing else in the
interface may use concentric circles.

## Colour

**The values are not here.** A theme is imported from a Hera Theme Builder export
([ADR 21](adr/0021-a-theme-is-imported-data.md)); the exports live in [`themes/`](themes/), and
the shipped one is [Heaven](themes/hera-theme-heaven.md) — pale sky and cloud, sun-gold, a clear
blue for anything alive, a dawn rose for her. What stays here is what every theme has to honour.

The three accents are not interchangeable — each one means something, and using the wrong one is
a bug:

| Token | Means | Used for |
|---|---|---|
| `brass` | **her authority** | The leading colour: the mark's ring, highlighted buttons, toggles and chips that are on, the check on a chosen row, question and permission cards |
| `laurel` | **her attention** | Thinking, a tool running, the ocellus iris, live state, progress, the active chat's bar, the focus ring |
| `pomegranate` | **her** | The send action and her name — the two places that are *her*, and nothing else |

`danger` is for failures and destructive actions, and is never used for a question or a stance —
a question she can ask is not an error.

The token names are roles, not hues: a theme can make laurel blue and it is still laurel, because
it is still saying *live*. Mapping meaning onto hue is what keeps the palette from being
decoration. If a colour appears somewhere and you cannot say which of the sentences above it is
saying, it does not belong there.

The neutrals are what a person recognises from across a room before they have read a word, which
is why a theme specifies them as precisely as its accents. The previous palette, Parchment &
Laurel, learnt that the hard way — a cream ground under white cards is the most recognisable
arrangement in this whole category — and the lesson outlives the palette.

Three appearance settings: **system**, **light**, **dark**. System is the default, because a
person who has already told their machine wants the same answer here; dark tokens sit on `:root`
so nothing flashes light before the scripts run.

## Typography

Serif to read, sans for chrome. The chat is prose and deserves a book face; buttons and labels
are not prose and should get out of the way.

A theme names four faces — **display** (the wordmark, dialog titles, the start screen), **body**
(her prose, your messages, chat titles), **interface** (every control, label and menu) and
**mono** (code, commands, keyboard hints) — and their sizes; Heaven's are in
[its export](themes/hera-theme-heaven.md#typography). What every theme keeps: interface text is
never the body face, and the body face is never a neutral grotesque, because neutral reads as
cold and that is the one thing the brief rules out.

Measure caps at **68ch**. Longer lines are the fastest way to make a reading interface tiring.
The reading column **is** that measure — `--column`, 68ch of the body face at the prose size with
the webfont actually loaded, measured in the browser rather than computed — so her prose, a user
bubble, the activity gutter, the cards and the composer all sit on one axis. A column wider than the measure is the version of
this that looks broken: only the prose gets capped, so her answer stops short of the edge
everything around it reaches and the message reads as nudged off-centre.

### How prose is set

Her answers are Markdown with TeX in them, and they are typeset rather than shown as source —
[ADR 11](adr/0011-markdown-and-tex-in-the-browser.md). Headings follow the scale above, a fenced
block gets the mono face on `--surface` inside a hairline, a table scrolls inside the column
rather than widening it, and a formula is set by KaTeX in the text colour so it reads as part of
the sentence rather than as an image dropped into it.

`---` is a hairline with air on both sides: a separator when she meant a break in the argument,
a breath when she meant a gap between two parts. It is never a heading — Markdown's setext form
would promote the sentence *above* it, which is the opposite of what she meant by it.

Source is coloured the way an editor colours it — VS Code Dark+ on a dark ground, Light+ on a
light one (`--vs-*` in `app.css`, the theme's file-editor spec) — because code is read by people
whose eyes are trained on those hues, and they are not the theme's to choose.

## Motion

She is *ox-eyed*: wide, calm, unhurried. Nothing flickers and nothing slides in from off-screen.
There is exactly one piece of choreography, and everything else is a fade or a height change.

**The thinking indicator** is that one piece (`hera/thinking`): while she is still without words,
a still ocellus pulses in scale where her answer will begin — small and faint to whole and back,
on the theme's `thinking.loop` — and the word *Thinking* breathes beside it on `thinking.label`.
The plume burst the previous rebuild drew here is gone: the theme names a pulse, and a pulse is
what a reader takes for attention rather than for a spinner. When nothing has arrived for thirty
seconds it becomes the stall box instead — the spinner turned red and breathing, with Wait and
Retry — because a model that is loading or has died looks exactly like one that is thinking, and
only time tells them apart.

Everything else has exactly one **motion slot** — `--motion-<slot>`, a duration and a curve
supplied by the theme ([Heaven's table](themes/hera-theme-heaven.md#motion)) — and a component
reads its slot rather than naming a duration (`--motion-<slot>-d` is the duration alone, for the
few places that multiply one). `prefers-reduced-motion` shows the ocellus still at full opacity
and removes every transition; the interface must be completely usable and completely legible with
all motion off.

## Components

**Every control is a primitive in `lib/components/ui/`, drawn the way the Theme Builder draws it**
and resolved through the export's looks and parts. A feature component composes them and owns no
control markup of its own — `primitives.test.ts` fails on a `<button>`, `<input>`, `<textarea>` or
`<select>` outside `ui/`, and on `--brass` read anywhere the theme does not name. `/design` shows
every one in every state.

| Theme component | Primitive |
|---|---|
| `hera/sidebar`, `-group`, `-entry` | `sidebar/Sidebar`, `SidebarGroup`, `SidebarEntry` |
| `hera/topbar` | `Topbar` |
| `hera/search` | `SearchBar` |
| `hera/selector` (and every menu) | `Selector`, `Menu`, `MenuItem`, `MenuHeading`, `MenuSeparator`, `MenuNote` |
| `hera/segmented` | `Segmented` |
| `hera/tooltip` | the `tooltip` action, built into `IconButton`, `Chip`, `CloseButton` |
| `hera/button` | `Button` (words), `IconButton` (an icon alone), `FileButton` (opens the file chooser) |
| `hera/close-button` | `CloseButton` |
| `hera/auth` | `Auth` (on `/design` until there are accounts) |
| `hera/text-field`, `hera/textarea` | `Input`, `Textarea`, `NumberField`, framed by `Field` |
| `hera/toggles` | `Checkbox` (box or switch), drawn by `Toggle` |
| `hera/collapsible` | `Collapsible` |
| `hera/chips` | `Chip`, `Pill`, `Avatar`, `Kbd` |
| `hera/spinner`, `-stalled` | `Spinner`, `StallBox` |
| `hera/progress-bar` | `ProgressBar` |
| `hera/skeleton` | `Skeleton` |
| `hera/toast` | `Toaster` |
| `hera/modal` | `Modal`, `Scrim` |
| `hera/error-page` | `ErrorPage` |
| `hera/ocellus`, `hera/thinking` | `Ocellus`, `Thinking` |
| `hera/thought-trace`, `hera/tool-call` | `TraceRow` |
| `hera/send-button` | `SendButton` |
| `hera/voice`, `hera/image-gen` | `VoiceCall`, `ImageGen` (on `/design` until there is a backend) |
| `hera/file-editor` | `FileEditor`, `CodeView` |
| Hera amendments | `ContextMeter`, `AttachmentChip`, `NumberField`, `StallBox`, `CodeView`, `Swatches` |

The composer, message, artifact card, side view and the two cards are feature components
(`Composer`, `Message`, `ArtifactCard`, `ArtifactDrawer`, `QuestionCard`, `PermissionCard`) built
only from these. The amendments are written into the theme export itself, under
[Hera amendments](themes/hera-theme-heaven.md#hera-amendments).

## Waiting

**A screen never states its empty state until it has earned it.** An empty list and a list that
has not arrived are the same empty array in the browser, and only one of them is something to say
out loud — the rail spent a milestone telling people with hundreds of conversations that they had
none ([issue #72](https://github.com/VoidEUW/hera/issues/72)). What stands in meanwhile is
`Skeleton`: bars the shape of the rows that are coming, in a step up from whatever they are lying
on, under a slow low-contrast sweep. Height is the point. A screen that draws nothing and then
drops a list into place has moved everything under it.

**It is drawn at once and held half a second**, which is the opposite of the usual advice and is
deliberate. The usual rule — wait 150 ms, so a fast fetch shows no grey — assumes the fetch is
usually slow. Hers is not: she is served by the application she talks to, so the requests land in
well under that on every ordinary load, and a delay means the placeholder never appears at all.
What a person sees then is the thing it was meant to prevent. The floor is honestly an artificial
delay, and it is worth it: half a second of the shape of the list is how the list gets to *arrive*
rather than to appear.

**Where the shape is known, it is used.** The rail remembers how many rows it had last time
(`hera:rail-shape`), so what stands in for it is the right height and the headings do not move
when the real thing lands. A placeholder sized from a guess is the same jump as no placeholder at
all, pointed the other way.

**One beat at a time.** The artifact drawer waits for the conversation and then takes its width
over 240 ms rather than opening in the frame the transcript arrives in — a width change and a
fade, which is the same family as the height changes above, and pointedly not a slide.

**And when nothing answers at all, the application does not draw itself.** `Offline` replaces the
whole shell rather than sitting over it: without that first load there is no rail, no profile, no
endpoint and no conversation, and drawing the chrome anyway invites somebody to click seven things
that cannot work. It says *Hera is not answering* rather than *network error*, because the request
that failed did not cross a network — if the page loaded and `/api/v1` did not, a process is not
running, and the next thing anybody needs is the command that starts it.

It is also the one screen that uses the **name** rather than the pronoun. Everything else in the
interface calls her *she*, which is what § *Voice* below is about; here there is no conversation
and nothing has a voice, and what a person needs to name is the program they are about to restart.

## The screen

Both rooms stand in front of her. A backdrop — her silhouette, masked from
`static/background.svg` and tinted from the theme's text colour — is pinned to the foot of the
start screen and the conversation at a whisper of opacity: present, never busy, and never
a picture pasted over the work. The drawing itself is a placeholder until the real artwork
replaces the file.

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

The rail is resized by its edge and does not fold. Projects disclose their chats inline, as in the reference — it is
genuinely easier to find a chat under the thing it belongs to than in one flat list sorted by
time. Settings sits directly above the profile card at the bottom, where the brief put it.

### Settings, and the profile menu

**Two doors, because there are two questions.** *Settings* is **how she works** — what she runs
on, who she is, what she knows, what she may do. The profile card at the bottom of the rail is
**you and this machine** — appearance, which of her is answering, where your data lives. Mixing
them is how a person ends up scrolling past six model fields to find a light-mode toggle.

Settings is a modal, because the brief says so and the brief is right: it is somewhere you *go
and come back from*, and a modal keeps the conversation visible behind it. Left nav, content on
the right, search at the top. The nav is ordered by what you reach for:

| | |
|---|---|
| **Usage** | Tokens per day for the last thirty days, read and written stacked, and the last 24 hours, 7 and 30 days under it. The newest bar is the one being read until you point at another or move with the arrow keys; its numbers are the line above the chart. Each total adds the cache share and the thinking tokens when the endpoint reports them, and the speed and the wait for the first token, which Hera measures ([ADR 25](adr/0025-usage-is-a-ledger.md)) |
| **Models** | Registered endpoints. First, because nothing else in Hera does anything until she is pointed at one — and because *testing* one belongs here: the endpoint is asked what it has, and the answer either fills a list you can pick from or says plainly why it could not |
| **Skills** | With usage counts, and whatever is wrong with each |
| **Servers** | Every MCP server as a box — hers first, with the ocellus — and its tools inside, each with a checkbox ([ADR 24](adr/0024-the-servers-screen-writes-mcp-json.md)) |
| **Permissions** | allow · deny · ask, with rules from a card marked as such |
| **Mind** | The twelve regions, each with its tier as an icon (a lock when only you may change it, a sprout when she may propose changes — the sentence is its tooltip) and its revision count |
| **Dreaming** | Listed and disabled. A v0.3 feature you can see coming is a promise; one you cannot is a surprise |
| **Memory** | What she knows about you, with a **space-left bar**: every enabled memory is in the prompt, so the ceiling is a thing a person steers by rather than a limit they hit. Disabling one keeps it and gives the space back; the state word sits left of the switch in a fixed slot so the switch never moves, and an entry is one box — the summary and the reason are behind *Summary and reason*, because neither reaches the prompt |

The profile menu is a popover rather than a second modal — four controls do not deserve a sheet
over the conversation.

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

**Servers** is a list of boxes (`Collapsible`, lazy): a mark — the ocellus for hers, a letter in a disc
for the rest — the name, whether it is connected, a wrench with the tool count, and a pen and a bin
for the ones in `mcp.json`. Opening a box asks the server for its tools, each a row with its
description (clamped to three lines — her own are paragraphs of prompt) and a checkbox on the right.
Unchecked is a `deny` rule and she is not offered the tool; when a *wider* rule is what turned it off
the row says which. **New server** opens a sheet: name (read-only once made), *Command* or *Web
address*, arguments one per line, environment or headers as rows whose saved secrets show as *Saved —
type to replace*, and an enabled switch. `$lib/servers.ts` is the form as data.

**Permissions** is the third list, and it has no equivalent in the reference: allow, deny and ask
rules over `server__tool` patterns ([ADR 23](adr/0023-permission-rules-are-kept-over-the-shipped-policy.md)).
One row per rule, in words first — the name a person gave it, or for an unnamed one what its pattern
says (*Every tool from fs*) — with the pattern in mono, the tools it covers today, and where it came
from: **Built in**, **From a card**, or made here. What happens is a three-way switch on the row; a
pen opens the form (name, decision, reason; the pattern is read-only after it is made) and a bin asks
before deleting. **New rule** takes a name, a pattern with a live list of the tools it would cover,
what happens, and why. A rule that ships with Hera can be changed and not deleted; the fallback —
*everything else* — is its own switch at the top. The pattern is described in words by
`$lib/permissions.ts`, which never decides what a pattern covers: the server's matcher answers that.

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
| **Profile** | *Who she is* — voice, stance, behavioural traits | Mind regions, in a git repository | Global. One of her. Changes rarely, and `hera_promptevo` may propose changes to it |
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
and it is designed out (`CLAUDE.md`, ADR 2, ADR 11).

| Event | Renders as |
|---|---|
| `text_delta` | Her prose, `body`, streamed in |
| `thinking_delta` | The reasoning channel — collapsed by default, one line in the gutter per **block** |
| `tool_call_ready` | A gutter row: ocellus, verb, target, and its result when it lands |
| `answer_required` | A **question card**, inline where she asked it. The `hera__ask` call and its eventual result draw nothing — all three events are about one question, and only the card is a thing a person reads |
| `turn_end` | Ends the turn; `reason: cancelled` marks it visibly as interrupted |

At `done`, the client throws away its optimistic view and re-renders from the persisted list. The
live view and a reload therefore cannot disagree, which is worth more than it sounds — it is what
makes every animated state above safe to be wrong about for a second.

### The activity gutter

Everything she did before speaking stacks above the prose as collapsed rows, each with a small
dot in its state colour on a dashed hairline and its verb in mono capitals
([ADR 21](adr/0021-a-theme-is-imported-data.md)). Quiet, in `caption` on `--text-muted`,
expandable. A row carries the
verb, the target, and how long it took:

```
┆◉  thought    61 words                                            Show
┆▤  skill      writing                                   skill · pinned
┆◍  search     kerberos ticket lifetime                          719 ms
┆✎  note       kerberos                                           12 ms
┆🔧 called     Docker mcp find                                   210 ms
```

**Her own tools name what they did; everybody else's name where they came from.** The mark has
already said whose tool it is, so *called **Hera** skill* spends half a short row repeating it —
where a reader wants *which* skill. A foreign tool is the opposite: the server is the most
important thing about `mcp-find`, so it keeps *called **Docker** mcp find* and its wrench. The
mapping from a tool name to a mark lives in `$lib/tools` and reads `hera__*` only; a table that
learned somebody else's server would make one you have not configured look broken beside one you
have.

**A shut block still shows the last two lines of it.** A collapsed row saying *thought · 213
words · Show* is a receipt: it tells you something happened and nothing about what, and following
her reasoning meant opening a panel that grows under your cursor while the turn is still running.
The tail is anchored to the *bottom* of a two-line box, so what you are looking at is the most
recent thing she wrote, with the cut above it faded rather than chopped.

**The gutter is in event order, and reasoning comes in blocks.** She thinks, calls something,
reads the result and thinks again — so that is two rows with the call between them, not one row
that grew. Folding a turn's reasoning into a single row at the top puts the second half of her
thinking above the call that caused it, and the only way to read the turn in order is to scroll
back to a block that has changed since you last looked at it. The rule for where a block ends is
the server's coalescing rule (`hera_chats.coalesce`): anything between two fragments stops the
merge, so the live view and the reload cannot disagree about how many rows there are.

**Skills say why they are there.** ADR 5 selects them in code — pinned, `/slash`, or retrieved by
similarity — and the interface shows which of the three it was. A person needs to be able to tell
"she always has this" from "she went and found this", and it is also the only feedback loop that
tells you when your retrieval is picking the wrong thing.

### The question card

`hera__ask` stops the turn and puts a question on screen. Inline, where she asked it, and drawn
from `answer_required` rather than from the call — the call, the card and the synthesised result
are all about the same question, and drawing three of them would be machinery pretending to be
conversation.

```
╭─────────────────────────────────────────╮
│  ?  she needs you to choose  asked you  │
│     Which deck do you mean?             │
│     ┌─────────────────────────────────┐ │
│     │ Answer…                         │ │
│     └─────────────────────────────────┘ │
│                Enter to send  [ Reply ] │
╰─────────────────────────────────────────╯
```

**Laurel, not brass.** Brass is authority — *this needs a decision*. A question is her turning
towards you, and drawing it in the permission colour would make being asked feel like being
stopped.

`kind` is a **closed set of three** and the label is the *person's* wording, not the tool's
([ADR 17](adr/0017-a-stance-is-a-sentence-and-a-question-stands-alone.md)):

| `kind` | Reads | Colour |
|---|---|---|
| `unsure` | she is unsure | `--text-muted` |
| `blocked` | she cannot go on | `brass` |
| `choice` | she needs you to choose | `--text-muted` |

Only `blocked` is set apart, because it is the one of the three where the turn is genuinely
stopped on the reply. Nothing here may be the danger colour: no question she can ask is an error.

A kind this build does not recognise renders as **nothing** rather than as the raw word. The only
way to get one is a turn persisted before the set was closed, carrying a stance from the emotion
vocabulary ADR 17 removed — and *doubt* on a question card is a puzzle rather than information.

> **Emotion cards were here, and they are gone.** `hera__emotion(kind, text)` drew a stance —
> `◔ doubt` — inline between paragraphs, coloured by tone from a fourteen-word vocabulary a person
> could edit. It was removed by ADR 17 after a version of driving it against a real model: several
> stances fired on the same occasion, one of them had become a tool, and asking a model to
> interrupt its own prose to file a small form is not a shape it complies with honestly. The
> *tone* idea is worth remembering if a stance ever comes back as a field on the answer — four
> tones with a deliberate-looking fallback was the right shape for an open vocabulary, and it was
> the vocabulary that was wrong.

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
  can do is a new variant, never a new regular expression. Typesetting her prose as Markdown and
  TeX is not an exception to this and is not allowed to become one: it draws text as what it is
  and reads no meaning back out of it (ADR 11).
- **The server render is authoritative** at `done`.
- **Every event variant needs a component**, including ones that arrive unknown — degrade
  visibly, never silently.
- **Desktop-shaped, PWA on the phone.** One breakpoint, 780px, shared by the rail, the drawer and
  the gutter rather than each choosing its own. Below it: the rail becomes a sheet over a scrim,
  opened by a menu button that replaces nothing (the rail is still there above 780px, unchanged)
  — a plain fade, the same `animation: fade` Settings already uses for its own sheet, because
  *nothing here slides in from off-screen* is a rule and a rail is not the one exception to it.
  The artifact drawer goes full-bleed instead of squeezing the transcript into whatever is left
  of a phone-width screen, and keeps the no-scrim rule because it already has its own close
  control. The activity gutter collapses each block to one summary row that expands on tap —
  nothing is removed, only the resting state is quieter. Installable: a manifest and a service
  worker that never touches `/api/*`, so it cannot sit between a phone and a streaming turn.
- **Keyboard first.** Visible focus, the composer focused on load, and every chord in
  `lib/keys.ts` — see *Keyboard* below.

## Keyboard

**One rule: a shortcut is a control that also exists on screen.** A feature only a chord reaches is
one nobody discovers — the interface's version of what ADR 5 refuses for skills. So every entry in
the keymap (`lib/keys.ts`) names the `control` it mirrors; the Hotkeys screen (Settings → App) prints
it beside the chord, and a unit test fails on an entry that names none.

- **One place.** The map is data — `{ id, label, group, control, default }` — so rebinding later is a
  screen over it rather than a rewrite. `Mod` is ⌘ on macOS and Ctrl elsewhere. Matching is on
  `event.key`, and Shift counts only for letters, arrows and named keys, so `⌘/` works on a layout
  that reaches `/` with Shift. A guard keeps the map off what the browser owns (⌘N, ⌘T, ⌘W, ⌘C…).
- **Components register, the keymap dispatches.** `keys.on(id, fn)` returns its own undo, so a chat
  chord exists only while the chat screen is mounted. A handler returns `false` to decline, and the
  browser keeps the chord (⌘S answers only when there is something to save).
- **Typing is not stolen.** Chords that a text field edits with (⌘⌫, ⌥↑/↓) do not fire inside one;
  the rest do.
- **One Escape.** A menu closes first, then a dialog (both answer for themselves), then what is
  registered with `keys.onEscape` — the find bar, then the side view. A text field keeps its own
  Escape (clear a search, cancel a rename) and never closes a drawer behind a person's back; an edit
  with unsaved text asks first (`Confirm`).
- **Where the key shows.** Beside the control when it carries a word and has room — a `Kbd` at the end
  of a sidebar row or a menu row. In the tooltip when it is an icon or a button where a key would
  crowd the row: `IconButton` and `Button` take a `keyId`.

| Chord | Does |
|---|---|
| ⌘K | command palette: chats by name, projects, Settings screens, actions |
| ⌘⇧F | the same palette, chats only |
| ⌘, / ⌘/ | Settings / the Hotkeys screen |
| ⌘⇧O | new chat |
| ⌥↑ / ⌥↓ | the chat above / below in the rail |
| ⇧Esc | back to the message field |
| ⌘F | Hera's find, in the chat's top bar |
| ⌘. | the side view |
| ⌘S | save the open file |
| ⌘E / ⌘⌫ | export / delete (asked once) from the chat menu |
| ⌘⇧E | share — listed, not bound: Share is greyed |

The rail does not fold, so there is no chord for it. Opening a chat does not move it in the rail
(only something said does), which is what makes ⌥↑/↓ a walk instead of a bounce.

## Open

Waiting on the maintainer, who has said more of the story is coming:

1. **Her identity as an assistant** — voice, stance, how she behaves in a conversation. Settled
   later and in the mind regions, not here. It may still overturn the pomegranate / peacock /
   brass reading, which is the one part of this document that is about *her* rather than about
   the application.
2. ~~**Display face**~~ — settled by the theme: Heaven sets Cormorant Garamond
   ([ADR 21](adr/0021-a-theme-is-imported-data.md)).
3. **The mark** — does the ocellus land, and should the wordmark be set in the display face or
   drawn?
4. **Where thinking lives** — a gutter row that expands in place, as drawn, or its own column?
5. **Project instructions vs. a project's own profile** — a project can name a default profile
   *and* carry instructions. If that turns out to be one control too many, instructions win and
   the profile becomes a per-chat choice only.

Everything in this document was provisional until there was a build to argue with. There is one
now, so this is the point at which it gets rewritten rather than amended — and the rewrite
should be driven by looking at it, not by reading this.
