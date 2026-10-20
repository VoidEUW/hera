# Hera theme: Heaven

> Light-first. Pale sky and white cloud, sun-gold for authority, a clear blue for anything alive, a dawn rose for her. Airy serif headings, soft blur entrances, a rounded floating composer.

Schema `hera-theme/1` · exported 2026-10-10 from the Hera Theme Builder · picture: `hera-theme-heaven.png` (attach it with this prompt).

## Your task

Apply this theme to Hera's web frontend (`apps/core/web`, SvelteKit + Svelte 5). Replace the colour, type, shape and motion tokens in `src/app.css` with the block below, then make every component listed under **Components** take its colours, fonts, radii, icon spec and motion only from these tokens. Do not add a literal colour, font, radius or duration to any component. Check the result against the picture in both modes. Where the picture and this text disagree, follow the text.

## Rules that hold for every Hera theme

- **Each accent says one thing.** `--brass` is her authority: the active chat, emphasis, highlighted buttons, checkboxes and switches when on, question and permission cards. `--laurel` is her attention: thinking, running tools, progress, live state and the focus ring. `--pomegranate` is hers alone: the send button and her name. `--danger` is for failures and destructive actions. If you cannot say which of these a colour is saying, it does not belong there.
- **The ocellus is the signature.** Brass ring, laurel iris, ground pupil. It is the wordmark mark (20–28px), the thinking indicator (16–22px) and every eye in the activity gutter (8px). Nothing else may use concentric circles.
- **Focus** is a 2px `--laurel` outline with a 2px offset on every interactive element. Never remove it.
- **Dark is the default.** The dark tokens sit on `:root` so nothing flashes light before scripts run.
- **Derived tokens** (`--hover`, the `-soft` tints, `--on-*` colours, `--scrim`, shadows) are computed from the palette. Use them as given; do not invent new tints.
- **Motion**: every moving part has exactly one slot with a preset, a duration and a curve (`--motion-<slot>`). Read the slot variable; never hard-code a duration. `prefers-reduced-motion: reduce` removes every transition and animation; the ocellus then shows still at full opacity and the interface stays fully usable.
- **Icons** are one stroke family on a 24-unit grid (spec below). Do not mix in another icon set.

## Structure: the look of each component

Every component has one of three looks. Looks change structure (fills, borders, corners, label treatment, layout), never colour; every colour still comes from the tokens. Build each component in the look named here.

| Component | Look | What that means |
|---|---|---|
| Sidebar | float | An inset panel floating on the ground: rounded, --surface, a soft shadow and no divider line. |
| Sidebar group | float | Caps label with the count in a small tinted pill. |
| Sidebar entry | soft | Icon and label rows with rounded hover fills. |
| Top bar | open | No bottom rule; the chat title in the interface face at full text colour. |
| Search bar | soft | A filled rounded field. |
| Selector | soft | Filled trigger and a rounded raised menu. |
| Segmented control | soft | A pill track with a raised sliding thumb. |
| Tooltip | soft | Inverted label with rounded corners. |
| Buttons | soft | Filled neutral buttons with rounded corners. |
| Close button | float | A filled round button. |
| Sign in / Register | soft | A centred rounded card. |
| Text field (also Textarea) | open | Transparent outlined inputs, labels at text weight. |
| Checkbox & switch | soft | Round filled switch track. |
| Collapsible box | soft | A filled rounded box. |
| Chips, pills, avatar, keys | soft | Fully rounded pills. |
| Loading bar | soft | A 4px rounded bar. |
| Toast | open | Inverted text-on-ink bar, no border. |
| Dialog | open | Interface-face title, footer separated by a hairline. |
| Thought & action trace (also Tool call, Thought stream) | soft | The eye gutter with plain text rows. |
| Message | soft | Your messages in rounded bubbles, hers as plain prose. |
| Artifact card | soft | A filled rounded card with a brass rail. |
| Side view | soft | A filled --surface panel with ruled header and footer. |
| Composer (also Voice call) | soft | A filled rounded box. |
| Send button | soft | A round button with a spinning ring while running. |
| Question & permission cards | soft | A rounded brass-bordered card with boxed options. |
| Image generation | open | A hairline frame with small corners; caption and steps in mono. |
| File viewer & editor | open | No panel fill: header, body and footer on the ground, a hairline under the header. |
| Error page | soft | A centred filled card with a large mark. |

### Part overrides

These single pieces differ from their component's look. Everything else in the component follows the look.

| Component | Part | Option | What that means |
|---|---|---|---|
| Toast | Position | top | Top centre |
| Thought & action trace | Verb | caps | Small mono capitals |
| Thought & action trace | Gutter line | dashed | A dashed line |
| Thought & action trace | Row marker | dot | A 7px dot in the row's state colour |
| Thought & action trace | Duration | mono | Mono, small |
| Thought & action trace | Shut thought preview | none | No preview; only the word count |
| Tool call | Done mark | check | A --laurel check after the duration |
| Tool call | Failed row | strike | The target struck through in --danger |
| Message | Speaker label | caps | Mono capitals |
| Message | Your message | bubble | A --surface-raised bubble on the right |
| Message | Actions | always | Always shown |
| Artifact card | Frame | card | A bordered --surface card |
| Artifact card | Accent rail | none | No rail |
| Artifact card | Icon / thumbnail | show | Shown |
| Artifact card | Open action | button | A button |
| Side view | Header rule | none | No rule |
| Side view | Footer | hide | Hidden |
| Composer | Keyboard hint | show | “Enter to send” in the corner |
| Question & permission cards | Frame | none | No frame |
| Question & permission cards | Option keys | boxed | Outlined key |

## Tokens (drop-in for `src/app.css`)

```css
/* Hera theme “Heaven” · hera-theme/1 · generated 2026-10-10 by the Hera Theme Builder */

:root {
	--font-display: 'Cormorant Garamond Variable', Georgia, 'Times New Roman', serif;
	--font-body: 'Newsreader Variable', Georgia, 'Times New Roman', serif;
	--font-ui: 'Albert Sans Variable', system-ui, -apple-system, 'Segoe UI', sans-serif;
	--font-mono: 'Fira Code Variable', ui-monospace, Menlo, Consolas, monospace;
	--ui-size: 14px;
	--prose-size: 17.5px;
	--display-weight: 500;

	--radius: 8px;
	--radius-lg: 16px;
	--radius-sm: 5px;
	--border-width: 1px;
	--space: 4.20px; /* density unit: control heights are multiples of it */
	--chip-radius: 999px;
	--focus-width: 2px;

	--icon-size: 16px;
	--icon-stroke: 1.4;
	--icon-linecap: round;
	--icon-linejoin: round;
	/* icon style: outline */

	--ease: cubic-bezier(0.2, 0.7, 0.2, 1);
	--ease-emphasized: cubic-bezier(0.6, 0, 0.3, 1);
	--ease-spring: cubic-bezier(0.3, 1.35, 0.6, 1);
	--fade: 132ms;
	--disclose: 176ms;

	/* One duration + curve per motion slot; the comment is the preset (see the motion table). */
	--motion-sidebar-collapse: 242ms var(--ease); /* width */
	--motion-group-disclose: 176ms var(--ease); /* height-fade */
	--motion-entry-hover: 132ms var(--ease); /* tint */
	--motion-entry-active: 132ms var(--ease); /* bar */
	--motion-topbar-title: 198ms var(--ease); /* crossfade */
	--motion-search-focus: 0ms var(--ease); /* none */
	--motion-field-focus: 132ms var(--ease); /* underline */
	--motion-composer-focus: 242ms var(--ease); /* ring */
	--motion-menu-enter: 198ms var(--ease-spring); /* scale */
	--motion-indicator-move: 242ms var(--ease-emphasized); /* slide */
	--motion-tooltip-enter: 330ms var(--ease); /* fade */
	--motion-modal-enter: 330ms var(--ease); /* zoom */
	--motion-toast-enter: 330ms var(--ease); /* rise */
	--motion-button-hover: 132ms var(--ease); /* lift */
	--motion-button-press: 88ms var(--ease); /* sink */
	--motion-close-hover: 275ms var(--ease); /* scale */
	--motion-switch-toggle: 198ms var(--ease-emphasized); /* slide */
	--motion-collapse-disclose: 220ms var(--ease); /* height-fade */
	--motion-spinner-loop: 1540ms var(--ease-emphasized); /* material */
	--motion-spinner-stall: 3520ms linear; /* fade */
	--motion-bar-indeterminate: 1980ms var(--ease-emphasized); /* shimmer */
	--motion-skeleton-sweep: 1760ms linear; /* sweep */
	--motion-thinking-loop: 3520ms var(--ease-emphasized); /* pulse */
	--motion-trace-disclose: 176ms var(--ease); /* height-fade */
	--motion-thought-stream: 418ms var(--ease-emphasized); /* fade */
	--motion-tool-running: 1320ms var(--ease-emphasized); /* eye */
	--motion-tool-done: 605ms var(--ease-spring); /* draw */
	--motion-prose-stream: 242ms var(--ease); /* blur */
	--motion-stream-caret: 1540ms linear; /* bar */
	--motion-message-enter: 330ms var(--ease); /* fade */
	--motion-message-actions: 132ms var(--ease); /* fade */
	--motion-artifact-enter: 550ms var(--ease); /* fade */
	--motion-card-enter: 242ms var(--ease); /* fade */
	--motion-drawer-open: 264ms var(--ease); /* width */
	--motion-send-morph: 220ms var(--ease-emphasized); /* morph */
	--motion-voice-wave: 990ms var(--ease-emphasized); /* bars */
	--motion-trace-row: 220ms var(--ease); /* fade */
	--motion-trace-line: 462ms var(--ease-emphasized); /* grow */
	--motion-tool-error: 0ms var(--ease); /* none */
	--motion-imagegen-progress: 242ms var(--ease); /* blur */
	--motion-imagegen-reveal: 528ms var(--ease-emphasized); /* unblur */
	--motion-imagegen-error: 330ms var(--ease); /* fade */
	--motion-error-enter: 352ms var(--ease); /* rise */
	--motion-spinner-accent: 0ms linear; /* none */
	--motion-spinner-label: 1540ms linear; /* plain */
	--motion-thinking-label: 1650ms var(--ease-emphasized); /* pulse */
	--motion-settings-switch: 198ms var(--ease); /* fade */
	--motion-sidebar-resize: 154ms var(--ease); /* fade */
}

:root,
[data-theme='dark'] {
	--ground: #0f1824; /* ground */
	--surface: #152132; /* surface */
	--surface-raised: #1d2c41; /* raised */
	--line: #2a3d56; /* line */
	--text: #eaf2fb; /* text */
	--text-muted: #a3b6cb; /* muted */
	--text-faint: #71859b; /* faint */
	--brass: #f2c64e; /* authority */
	--laurel: #6fb3f2; /* live */
	--pomegranate: #ef7aa3; /* signature */
	--danger: #f07a62; /* danger */
	--hover: rgba(234,242,251,0.06);
	--brass-soft: rgba(242,198,78,0.14);
	--brass-line: rgba(242,198,78,0.45);
	--laurel-soft: rgba(111,179,242,0.2);
	--pomegranate-soft: rgba(239,122,163,0.3);
	--danger-soft: rgba(240,122,98,0.15);
	--on-brass: #0f1824;
	--on-pomegranate: #0f1824;
	--on-danger: #0f1824;
	--on-laurel: #0f1824;
	--scrim: rgba(0,0,0,.55);
	--shadow: 0 12px 32px rgba(0,0,0,.42);
	--shadow-sm: 0 2px 8px rgba(0,0,0,.3);
	--skeleton-highlight: #2d3c50;
	color-scheme: dark;
}

[data-theme='light'] {
	--ground: #e5edf6; /* ground */
	--surface: #d7e6f4; /* surface */
	--surface-raised: #dde9f5; /* raised */
	--line: #cbdbea; /* line */
	--text: #0f2338; /* text */
	--text-muted: #475e77; /* muted */
	--text-faint: #7a8fa5; /* faint */
	--brass: #a87400; /* authority */
	--laurel: #2574c4; /* live */
	--pomegranate: #c4416f; /* signature */
	--danger: #c23c26; /* danger */
	--hover: rgba(15,35,56,0.05);
	--brass-soft: rgba(168,116,0,0.12);
	--brass-line: rgba(168,116,0,0.45);
	--laurel-soft: rgba(37,116,196,0.18);
	--pomegranate-soft: rgba(196,65,111,0.3);
	--danger-soft: rgba(194,60,38,0.12);
	--on-brass: #0f2338;
	--on-pomegranate: #e5edf6;
	--on-danger: #e5edf6;
	--on-laurel: #e5edf6;
	--scrim: rgba(15,35,56,0.28);
	--shadow: 0 12px 32px rgba(15,35,56,0.14);
	--shadow-sm: 0 2px 8px rgba(15,35,56,0.1);
	--skeleton-highlight: #d1ddea;
	color-scheme: light;
}

```

## Typography

| Role | Family | Package | Used for |
|---|---|---|---|
| Display | Cormorant Garamond | `@fontsource-variable/cormorant-garamond` | Wordmark, dialog titles, start screen |
| Body | Newsreader | `@fontsource-variable/newsreader` | Her prose, user bubbles, chat titles |
| Interface | Albert Sans | `@fontsource-variable/albert-sans` | Every control, label and menu |
| Mono | Fira Code | `@fontsource-variable/fira-code` | Code, commands, keyboard hints |

Interface text is 14px. Her prose is 17.5px with a 1.65 line height and a 68ch measure. Display weight is 500. Uppercase labels (group and menu headings) are 10.5–11px, weight 600, letter-spacing 0.08–0.09em.

## Shape and density

- Radius 8px for cards and menus, 16px for the composer, user bubbles and dialogs, 5px (`--radius-sm`) for buttons, inputs and rows.
- Borders are 1px in `--line`. Chips are fully rounded pills.
- Density unit `--space` = 4.20px: buttons are 8.5 units tall (7 small, 10.5 large), sidebar rows 8, inputs 9, the top bar 13.

## Icons

- Style **outline**: strokes only.
- Stroke 1.4 on a 24-unit grid, round caps, round joins, drawn at 16px; icons use `currentColor`.
- The set, and where each icon is used:

  - `plus`: New chat, attach, add to group
  - `x`: Close, remove attachment, clear search
  - `search`: Search bar, web search tool
  - `sliders`: Settings
  - `chat`: Chat entries
  - `folder`: Project entries, add from project
  - `file`: Artifacts, attachments
  - `download`: Download artifact
  - `copy`: Copy message/code
  - `edit`: Edit message, note tool
  - `refresh`: Regenerate
  - `more`: Row and message overflow menus
  - `chevD`: Selectors, groups
  - `chevR`: Collapsible boxes
  - `check`: Selected menu item, done states, copied
  - `clip`: Attach file
  - `mic`: Mute toggle in a call
  - `micOff`: Muted
  - `voice`: Voice call
  - `spark`: Skills
  - `plug`: MCP servers
  - `arrowUp`: Send
  - `stop`: Stop generation
  - `wrench`: Foreign tool calls
  - `globe`: Web/network
  - `clock`: Memory, timing
  - `code`: Code view
  - `image`: Image attachments and previews
  - `user`: Account
  - `key`: Passkey sign-in
  - `mail`: Email sign-in
  - `moon`: Dreaming, dark mode
  - `sun`: Light mode
  - `panel`: Toggle sidebar
  - `panelR`: Toggle side view
  - `eye`: Preview
  - `external`: Open in new window
  - `trash`: Delete
  - `alert`: Errors, not responding
  - `shield`: Permissions
  - `cube`: Models
  - `terminal`: Shell tools
  - `pin`: Pinned
  - `book`: Skills library
  - `share`: Share
  - `phone`: End call
  - `info`: Info notices
  - `camera`: Screenshot
  - `chevL`: Previous page
  - `minus`: Zoom out
  - `expand`: Open in a larger view

## Motion

Curves: standard `cubic-bezier(0.2, 0.7, 0.2, 1)`, emphasized `cubic-bezier(0.6, 0, 0.3, 1)`, spring `cubic-bezier(0.3, 1.35, 0.6, 1)`. The global speed (×1.1) is already applied to the durations below.

| Component | Slot | Preset | Duration | Curve | Behaviour |
|---|---|---|---|---|---|
| Sidebar | `sidebar.collapse` | width | 242ms | standard | Width animates down to an icon rail one icon column wide; labels fade out in the first 60% of the duration |
| Sidebar group | `group.disclose` | height-fade | 176ms | standard | grid-template-rows 0fr↔1fr plus opacity 0↔1; chevron rotates -90° |
| Sidebar entry | `entry.hover` | tint | 132ms | standard | Background → --hover tint, text → --text |
| Sidebar entry | `entry.active` | bar | 132ms | standard | 2px --brass bar on the left edge, text --text, faint --hover background |
| Top bar | `topbar.title` | crossfade | 198ms | standard | New title fades in (opacity 0→1) |
| Search bar | `search.focus` | none | 0ms | standard | Border → --laurel, instantly |
| Text field | `field.focus` | underline | 132ms | standard | A 2px --laurel underline inside the bottom edge |
| Composer | `composer.focus` | ring | 242ms | standard | Border → --laurel plus a 3px --laurel-soft ring |
| Selector | `menu.enter` | scale | 198ms | spring | Fades in from scale(.95), origin at the trigger corner |
| Segmented control | `indicator.move` | slide | 242ms | emphasized | The selection thumb slides to the new segment (transform) |
| Tooltip | `tooltip.enter` | fade | 330ms | standard | Opacity 0→1 after a 250ms hover intent delay · show after 1200ms, hide after 0ms |
| Dialog | `modal.enter` | zoom | 330ms | standard | Fades in from scale(.85) |
| Toast | `toast.enter` | rise | 330ms | standard | Fades in from 8px below (bottom-right stack) · stays for 3000ms |
| Buttons | `button.hover` | lift | 132ms | standard | Rises 1px with --shadow-sm |
| Buttons | `button.press` | sink | 88ms | standard | translateY(1px) while pressed |
| Close button | `close.hover` | scale | 275ms | standard | Grows to scale(1.1) |
| Checkbox & switch | `switch.toggle` | slide | 198ms | emphasized | Thumb slides 14px, track fills --brass |
| Collapsible box | `collapse.disclose` | height-fade | 220ms | standard | grid-template-rows 0fr↔1fr plus opacity; chevron rotates 90° |
| Loading circle | `spinner.loop` | material | 1540ms | emphasized | One arc grows and shrinks while it turns |
| Loading circle · not responding | `spinner.stall` | fade | 3520ms | linear | Spinner turns --danger and breathes 100→45% opacity |
| Loading bar | `bar.indeterminate` | shimmer | 1980ms | emphasized | A soft --laurel highlight sweeps across the track |
| Skeleton | `skeleton.sweep` | sweep | 1760ms | linear | A lighter band (--sk-hi) sweeps across each bar |
| Thinking indicator | `thinking.loop` | pulse | 3520ms | emphasized | The still eye pulses in scale |
| Thought & action trace | `trace.disclose` | height-fade | 176ms | standard | Row body opens with grid rows 0fr↔1fr plus opacity |
| Thought stream | `thought.stream` | fade | 418ms | emphasized | Each word fades in |
| Tool call | `tool.running` | eye | 1320ms | emphasized | The row's 8px ocellus pulses (scale .55↔1, opacity .35↔1) |
| Tool call | `tool.done` | draw | 605ms | spring | The check draws its own stroke |
| Message | `prose.stream` | blur | 242ms | standard | Each word fades in from blur(5px) |
| Message | `stream.caret` | bar | 1540ms | linear | A 2px --laurel bar blinking (steps) |
| Message | `message.enter` | fade | 330ms | standard | Opacity only |
| Message | `message.actions` | fade | 132ms | standard | Copy/edit/retry row fades in on hover or focus |
| Artifact card | `artifact.enter` | fade | 550ms | standard | Opacity only |
| Question & permission cards | `card.enter` | fade | 242ms | standard | Opacity only |
| Side view | `drawer.open` | width | 264ms | standard | Takes its width (0→400px) while fading in; the transcript reflows |
| Send button | `send.morph` | morph | 220ms | emphasized | Arrow lifts and shrinks out while the stop square grows in; a --pomegranate ring spins around the button while running |
| Voice call | `voice.wave` | bars | 990ms | emphasized | Twelve 3px bars scale between 25% and 100% height, staggered |
| Thought & action trace | `trace.row` | fade | 220ms | standard | Opacity only |
| Thought & action trace | `trace.line` | grow | 462ms | emphasized | The line grows downward from the first marker |
| Tool call | `tool.error` | none | 0ms | standard | Appears instantly |
| Image generation | `imagegen.progress` | blur | 242ms | standard | The image is visible from the start, blurred and desaturated, sharpening as steps complete |
| Image generation | `imagegen.reveal` | unblur | 528ms | emphasized | Comes out of a 16px blur |
| Image generation | `imagegen.error` | fade | 330ms | standard | The failure panel fades in |
| Error page | `error.enter` | rise | 352ms | standard | Fades in from 8px below |
| Loading circle | `spinner.accent` | none | 0ms | linear | No accent |
| Loading circle | `spinner.label` | plain | 1540ms | linear | Plain --text-muted text |
| Thinking indicator | `thinking.label` | pulse | 1650ms | emphasized | “Thinking” breathing 100→45% opacity |
| Dialog | `settings.switch` | fade | 198ms | standard | The new pane fades in |
| Sidebar | `sidebar.resize` | fade | 154ms | standard | The 2px edge line fades in on hover, focus and while dragging |

Shared motion: every button, icon button and chip uses `button.hover` and `button.press`; every menu and popover uses `menu.enter`; every disclosure animates height with `grid-template-rows: 0fr ↔ 1fr`.

## Components

Each component exists once and is reused wherever it appears: a sidebar in a settings dialog is the same Sidebar as the chat rail. Build them as one parent theme scope (the tokens) with these children.

### Navigation & structure

#### Sidebar · `hera/sidebar`

One component with variants. The shell is always head, scrolling body and an optional foot; a variant only fills the slots. Chat: brand, collapse, search, groups, account foot. Settings: a titled head without collapse, a search, fixed groups, entries without actions, an About foot, a narrower rail; it is the left column of the settings dialog. Every row hangs on two lines: the lead line (icons, brand mark, chevrons, search magnifier) and the label line (title, labels, group labels, placeholder). Never pad a row by hand.

- Tokens: `--surface`, `--line`, `--text`, `--text-muted`
- Parts and states: Resizable (chat only): a separator on the right edge; drag, or arrow keys in 16px steps; Home/End jump to 200/420px; double-click resets to --rail; keep the width per user; variant: chat | settings (class sb-chat / sb-settings on the same nav); Head: lead (mark or icon) + title, optional subtitle, optional actions; Body: search + any number of Sidebar groups (collapsible, or fixed); Foot: one entry (account, or About); Alignment: --sb-pad (edge to row), --sb-ix (row to lead line), --sb-lead (icon column = --icon-size), --sb-gap (lead to label), --sb-ir (right inset); with icons off, --sb-icons:0 and everything starts on the lead line; Collapsed (chat only): a rail exactly one icon column wide, 2 × (--sb-pad + --sb-ix) + --sb-lead
- Motion: `sidebar.collapse` = width, `sidebar.resize` = fade

#### Sidebar group · `hera/sidebar-group`

Separates sets of entries inside a sidebar: an uppercase label that toggles the group, an optional count and an add button.

- Tokens: `--text-faint`, `--line`
- Parts and states: label; count (optional); add action (optional); open / closed; separator variant with a top hairline
- Motion: `group.disclose` = height-fade

#### Sidebar entry · `hera/sidebar-entry`

One row: optional leading icon, label, optional meta, optional trailing settings action. Used for chats, projects, settings sections and the account.

- Tokens: `--text-muted`, `--text`, `--surface-raised`, `--brass`, `--hover`
- Parts and states: icon (hideable); label; meta (time, count); action button: always / on hover / hidden; states: default, hover, active, disabled
- Motion: `entry.hover` = tint, `entry.active` = bar

#### Top bar · `hera/topbar`

Title on the left in the body face, a toolbar on the right. The title animates when a new chat gets its name.

- Tokens: `--ground`, `--line`, `--text-muted`
- Parts and states: title; toolbar: icon buttons, selector chips, separators
- Motion: `topbar.title` = crossfade

#### Search bar · `hera/search`

Leading icon, input, a keyboard hint that becomes a clear button once there is text.

- Tokens: `--ground`, `--line`, `--text-faint`, `--laurel`
- Parts and states: placeholder; shortcut hint; clear button when filled; compact (expand on focus)
- Motion: `search.focus` = none

#### Selector · `hera/selector`

A button that opens a menu of choices. The leading icon is optional; the menu is the same popover every other menu in Hera uses.

- Tokens: `--surface`, `--line`, `--surface-raised`, `--brass`
- Parts and states: leading icon (hideable); label; menu with headings, descriptions, check on the selected item, separators, danger items
- Motion: `menu.enter` = scale

#### Segmented control · `hera/segmented`

Two to four mutually exclusive options with a moving thumb, as in Settings › Appearance and the side view tabs.

- Tokens: `--ground`, `--line`, `--surface-raised`, `--text`
- Parts and states: 2–4 segments; optional icons; small size
- Motion: `indicator.move` = slide

#### Tooltip · `hera/tooltip`

A short label for icon-only buttons, shown after a 250ms hover intent.

- Tokens: `--text`, `--ground`
- Parts and states: above / below
- Motion: `tooltip.enter` = fade

### Actions

#### Buttons · `hera/button`

One shape, six meanings. Neutral for most things, Highlighted (brass) for the one action a screen leads with, Signature (pomegranate) only where it is her, Danger for destructive actions, Ghost for low-emphasis, Grayed out when unavailable.

- Tokens: `--surface`, `--line`, `--brass`, `--pomegranate`, `--danger`, `--text-faint`
- Parts and states: variants: neutral, highlighted, signature, danger, danger-soft, ghost, disabled; sizes: sm, md, lg; leading icon; icon-only button
- Motion: `button.hover` = lift, `button.press` = sink

#### Close button · `hera/close-button`

A round outlined × used by dialogs, side views, chips and toasts.

- Tokens: `--line`, `--text-muted`, `--hover`
- Parts and states: sizes: sm (borderless), md, lg
- Motion: `close.hover` = scale

#### Sign in / Register · `hera/auth`

The sign-in surface Settings › Account is waiting for: email, passkey, and a switch between signing in and registering.

- Tokens: `--surface`, `--line`, `--brass`
- Parts and states: mode: sign in / register; email field; passkey button; primary action highlighted

### Inputs

#### Text field · `hera/text-field`

Label, input, help text. Error state swaps the help for the reason in --danger.

- Tokens: `--surface`, `--line`, `--laurel`, `--danger`, `--text-faint`
- Parts and states: label; placeholder; help; error; disabled
- Motion: `field.focus` = underline

#### Textarea · `hera/textarea`

Same frame as the text field, taller, with an optional counter.

- Tokens: `--surface`, `--line`, `--laurel`
- Parts and states: counter; resizable

#### Checkbox & switch · `hera/toggles`

Both turn brass when on: a setting is her authority being granted.

- Tokens: `--brass`, `--on-brass`, `--surface-raised`, `--text-faint`
- Parts and states: checkbox; switch; with description; disabled
- Motion: `switch.toggle` = slide

#### Collapsible box · `hera/collapsible`

A bordered box with a header that discloses its content. Used for provider cards, model rows and advanced settings.

- Tokens: `--surface`, `--line`, `--text-faint`
- Parts and states: title; subtitle; open / closed
- Motion: `collapse.disclose` = height-fade

#### Chips, pills, avatar, keys · `hera/chips`

Small status and selection marks. Pills carry meaning by role colour; chips are toggles in the composer.

- Tokens: `--hover`, `--brass-soft`, `--laurel-soft`, `--danger-soft`
- Parts and states: chip on/off; pill: neutral, authority, live, danger; avatar: initial or picture; kbd

### Feedback & overlays

#### Loading circle · `hera/spinner`

For a model loading and for the interface waiting. Always --laurel: it is live state.

- Tokens: `--laurel`, `--line`
- Parts and states: sizes 14 / 20 / 28; with label line
- Motion: `spinner.loop` = material, `spinner.accent` = none, `spinner.label` = plain

#### Loading circle · not responding · `hera/spinner-stalled`

What the spinner becomes when nothing has arrived for a while, with the two things a person can do about it.

- Tokens: `--danger`, `--danger-soft`, `--text-faint`
- Parts and states: stalled after N seconds; actions: wait, retry
- Motion: `spinner.stall` = fade

#### Loading bar · `hera/progress-bar`

Determinate for downloads and uploads, indeterminate when there is no number to show.

- Tokens: `--laurel`, `--surface-raised`
- Parts and states: determinate value; indeterminate; thick variant
- Motion: `bar.indeterminate` = shimmer

#### Skeleton · `hera/skeleton`

The shape of rows that are coming, held for at least half a second so lists arrive instead of appearing.

- Tokens: `--surface-raised`, `--skeleton-highlight`
- Parts and states: text bar; line; avatar circle
- Motion: `skeleton.sweep` = sweep

#### Toast · `hera/toast`

A one-line confirmation in the bottom-right corner that leaves on its own after 2.6s.

- Tokens: `--surface-raised`, `--line`, `--laurel`, `--danger`
- Parts and states: success; failure; with action
- Motion: `toast.enter` = rise

#### Dialog · `hera/modal`

Settings and confirmations. Confirmations are a single column. Settings is the Sidebar (settings variant) on the left and a pane on the right: title, description, rows, footer actions. Below 600px the sidebar turns into a horizontal row of entries above the pane.

- Tokens: `--surface`, `--line`, `--scrim`
- Parts and states: title; description; body rows; footer actions; settings: Sidebar settings variant + pane; switching panes plays settings.switch
- Motion: `modal.enter` = zoom, `settings.switch` = fade

#### Error page · `hera/error-page`

What replaces a screen when loading fails: offline, server error, not found, model unreachable. It says what happened, what that means, and the one thing to do next.

- Tokens: `--ground`, `--danger`, `--text-muted`, `--surface`
- Parts and states: kinds: offline, server, not found, model; command or id to copy; primary and secondary action; retry countdown; technical details
- Motion: `error.enter` = rise

### Conversation

#### Ocellus mark · `hera/ocellus`

The signature: a single peacock eye. Brass ring, laurel iris, ground pupil. 20–28px as identity, 16–22px as the thinking indicator, 8px as each eye in the activity gutter. Nothing else may use concentric circles.

- Tokens: `--brass`, `--laurel`, `--ground`
- Parts and states: sizes 28 / 16 / 8

#### Thinking indicator · `hera/thinking`

The one piece of choreography: shown while she is still without words.

- Tokens: `--laurel`, `--brass`, `--text-muted`
- Parts and states: with label; large
- Motion: `thinking.loop` = pulse, `thinking.label` = pulse

#### Thought & action trace · `hera/thought-trace`

The activity gutter above her answer: one row per event in order, each with an 8px eye on a hairline. A shut thought still shows its last two lines.

- Tokens: `--line`, `--text-muted`, `--text-faint`, `--laurel`
- Parts and states: collapsed with tail; opened; rows: thought, skill, search, note, called
- Motion: `trace.disclose` = height-fade, `trace.row` = fade, `trace.line` = grow

#### Thought stream · `hera/thought-stream`

How her reasoning arrives while the thought row is shut: words land at the bottom of the two-line tail and older lines fade upward.

- Tokens: `--text-faint`
- Parts and states: word reveal preset
- Motion: `thought.stream` = fade

#### Tool call · `hera/tool-call`

A gutter row for a call: verb, target, duration. Running, done and failed. Opens to show the input and the result.

- Tokens: `--laurel`, `--danger`, `--text-muted`, `--line`
- Parts and states: running; done; failed; expandable input/result
- Motion: `tool.running` = eye, `tool.done` = draw, `tool.error` = none

#### Message · `hera/message`

Her messages are prose on the ground, no bubble; yours are bubbles on --surface-raised. Actions appear on hover: copy, edit, retry, more.

- Tokens: `--surface-raised`, `--text`, `--text-muted`
- Parts and states: user / assistant; hover actions; edit mode; streaming with caret; interrupted and failed notices
- Motion: `prose.stream` = blur, `stream.caret` = bar, `message.enter` = fade, `message.actions` = fade

#### Artifact card · `hera/artifact-card`

A file she made: icon or thumbnail, name in the body face, type and size, download and Open.

- Tokens: `--surface`, `--line`, `--brass`
- Parts and states: html; markdown; code; image with thumbnail
- Motion: `artifact.enter` = fade

#### Side view · `hera/side-view`

The artifact drawer: opens beside the transcript with a header (name, Preview/Source, copy, download, close) and a body that renders code, markdown, HTML or images.

- Tokens: `--surface`, `--line`, `--text`
- Parts and states: kind: code, markdown, html, image; preview / source tabs; footer meta
- Motion: `drawer.open` = width

#### Composer · `hera/composer`

The chatting box: prompt, attachments, attach menu, skills, MCP servers, voice, model and send.

- Tokens: `--surface`, `--line`, `--laurel`, `--pomegranate`
- Parts and states: attachments with upload progress; attach menu; skill picker; server picker; voice call state; model selector; send button
- Motion: `composer.focus` = ring

#### Send button · `hera/send-button`

Hers: pomegranate. Becomes stop while she works; pressing stop cancels the turn.

- Tokens: `--pomegranate`, `--on-pomegranate`, `--pomegranate-soft`
- Parts and states: disabled; ready; running (stop); cancelling
- Motion: `send.morph` = morph

#### Voice call · `hera/voice`

What the composer becomes during a voice call: waveform, timer, mute and end call.

- Tokens: `--laurel`, `--danger`
- Parts and states: listening; muted
- Motion: `voice.wave` = bars

#### Question & permission cards · `hera/question-card`

When she stops to ask: a brass-bordered card inline where she asked. Permission cards show exactly what will run.

- Tokens: `--brass-line`, `--brass`, `--surface`, `--danger-soft`
- Parts and states: options with keys; free answer; permission: deny / allow once / always allow; answered state
- Motion: `card.enter` = fade

#### Image generation · `hera/image-gen`

An image she is making: queued, generating with live progress, revealed when done, and a failure state that names the reason and offers Retry.

- Tokens: `--surface-raised`, `--laurel`, `--danger`, `--skeleton-highlight`
- Parts and states: states: queued, generating, done, failed; step counter and percentage; prompt caption; retry
- Motion: `imagegen.progress` = blur, `imagegen.reveal` = unblur, `imagegen.error` = fade

#### File viewer & editor · `hera/file-editor`

One component for looking at and changing files: uploaded images (zoom), PDFs (pages), source and Markdown (VS Code colours, line numbers, copy, an Edit switch) and skills (SKILL.md with save and trust state). Inline, in the side view, or as a modal.

- Tokens: `--surface`, `--ground`, `--line`, `--laurel`
- Parts and states: kinds: image, pdf, source, markdown, skill; zoom and page navigation; copy, download, edit switch; modal or inline; read only / unsaved / saved / modified

## Source of truth

```json
{
  "schema": "hera-theme/1",
  "id": "heaven",
  "name": "Heaven",
  "description": "Light-first. Pale sky and white cloud, sun-gold for authority, a clear blue for anything alive, a dawn rose for her. Airy serif headings, soft blur entrances, a rounded floating composer.",
  "color": {
    "dark": {
      "ground": "#0f1824",
      "surface": "#152132",
      "surface-raised": "#1d2c41",
      "line": "#2a3d56",
      "text": "#eaf2fb",
      "text-muted": "#a3b6cb",
      "text-faint": "#71859b",
      "brass": "#f2c64e",
      "laurel": "#6fb3f2",
      "pomegranate": "#ef7aa3",
      "danger": "#f07a62"
    },
    "light": {
      "ground": "#e5edf6",
      "surface": "#d7e6f4",
      "surface-raised": "#dde9f5",
      "line": "#cbdbea",
      "text": "#0f2338",
      "text-muted": "#475e77",
      "text-faint": "#7a8fa5",
      "brass": "#a87400",
      "laurel": "#2574c4",
      "pomegranate": "#c4416f",
      "danger": "#c23c26"
    }
  },
  "type": {
    "display": "Cormorant Garamond",
    "body": "Newsreader",
    "ui": "Albert Sans",
    "mono": "Fira Code",
    "uiSize": 14,
    "proseSize": 17.5,
    "displayWeight": 500
  },
  "shape": {
    "radius": 8,
    "radiusLg": 16,
    "border": 1,
    "density": 1.05,
    "chip": "pill",
    "focus": 2
  },
  "icons": {
    "style": "outline",
    "stroke": 1.4,
    "size": 16,
    "cap": "round"
  },
  "styles": {
    "sidebar": "float",
    "sidebar-group": "float",
    "sidebar-entry": "soft",
    "topbar": "open",
    "search": "soft",
    "selector": "soft",
    "segmented": "soft",
    "tooltip": "soft",
    "button": "soft",
    "close-button": "float",
    "auth": "soft",
    "text-field": "open",
    "toggles": "soft",
    "collapsible": "soft",
    "chips": "soft",
    "progress-bar": "soft",
    "toast": "open",
    "modal": "open",
    "thought-trace": "soft",
    "message": "soft",
    "artifact-card": "soft",
    "side-view": "soft",
    "composer": "soft",
    "send-button": "soft",
    "question-card": "soft",
    "image-gen": "open",
    "file-editor": "open",
    "error-page": "soft"
  },
  "parts": {
    "toast.place": "top",
    "trace.verb": "caps",
    "trace.line": "dashed",
    "trace.marker": "dot",
    "trace.meta": "mono",
    "trace.tail": "none",
    "tool.donemark": "check",
    "tool.error": "strike",
    "msg.label": "caps",
    "msg.user": "bubble",
    "msg.actions": "always",
    "art.frame": "card",
    "art.rail": "none",
    "art.lead": "show",
    "art.open": "button",
    "drw.header": "none",
    "drw.footer": "hide",
    "cmp.hint": "show",
    "qc.frame": "none",
    "qc.keys": "boxed"
  },
  "css": {},
  "motion": {
    "speed": 1.1,
    "curves": {
      "standard": "cubic-bezier(0.2, 0.7, 0.2, 1)",
      "emphasized": "cubic-bezier(0.6, 0, 0.3, 1)",
      "spring": "cubic-bezier(0.3, 1.35, 0.6, 1)"
    },
    "slots": {
      "entry.hover": {
        "p": "tint"
      },
      "entry.active": {
        "p": "bar"
      },
      "button.hover": {
        "p": "lift"
      },
      "button.press": {
        "p": "sink"
      },
      "composer.focus": {
        "p": "ring",
        "d": 220
      },
      "search.focus": {
        "p": "none"
      },
      "field.focus": {
        "p": "underline"
      },
      "message.enter": {
        "p": "fade",
        "d": 300
      },
      "artifact.enter": {
        "p": "fade",
        "d": 500
      },
      "card.enter": {
        "p": "fade"
      },
      "menu.enter": {
        "p": "scale",
        "e": "spring",
        "d": 180
      },
      "toast.enter": {
        "p": "rise",
        "d": 300,
        "wo": 3000
      },
      "close.hover": {
        "p": "scale",
        "d": 250
      },
      "modal.enter": {
        "p": "zoom",
        "d": 300
      },
      "send.morph": {
        "p": "morph"
      },
      "stream.caret": {
        "p": "bar",
        "d": 1400
      },
      "thought.stream": {
        "p": "fade",
        "d": 380,
        "e": "emphasized",
        "kf": "from { opacity: 0; transform: translateY(6px) scale(.98); }\nto { opacity: 1; transform: none; }"
      },
      "prose.stream": {
        "p": "blur"
      },
      "thinking.loop": {
        "p": "pulse",
        "d": 3200,
        "e": "emphasized"
      },
      "spinner.loop": {
        "p": "material",
        "d": 1400,
        "e": "emphasized"
      },
      "bar.indeterminate": {
        "p": "shimmer",
        "d": 1800
      },
      "trace.row": {
        "p": "fade"
      },
      "tool.done": {
        "p": "draw",
        "d": 550
      },
      "tooltip.enter": {
        "d": 300,
        "w": 1200
      },
      "collapse.disclose": {
        "d": 200
      },
      "spinner.accent": {
        "p": "none"
      },
      "spinner.stall": {
        "p": "fade"
      },
      "thinking.label": {
        "p": "pulse",
        "e": "emphasized",
        "d": 1500
      },
      "tool.running": {
        "p": "eye"
      },
      "tool.error": {
        "p": "none"
      }
    }
  }
}
```
