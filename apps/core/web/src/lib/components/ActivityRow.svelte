<script lang="ts">
	/**
	 * One row in the activity gutter: a mark on a hairline, the verb, the target, and how long
	 * it took. Quiet, expandable, caption type on muted text.
	 *
	 * A turn draws a column of marks down its left gutter, joined by a hairline — activity you
	 * read at a glance. That is the hundred eyes of Argus, and it is why this is a row of its
	 * own rather than a log line.
	 *
	 * The marks split by *what happened*, not by which event carried it. A **thought** keeps the
	 * ocellus. A **skill** gets a scroll — whether the router selected it before the turn or she
	 * reached for it with `hera__skill` mid-task, because those are the same thing to a reader,
	 * and letting the plumbing decide the picture is how a category stops looking like one. Her
	 * own capabilities get their own: a **globe** when she looked outside the machine, a **quill**
	 * when she wrote something down, a **knot** when she kept a fact about you, a **stele** when
	 * she published something for you to read. Everything else
	 * — every foreign server, and anything of hers this build has never heard of — gets a
	 * **wrench**, the shape everybody already reads as "a tool ran". `$lib/tools` holds that
	 * mapping and says why it is allowed to know her names and no others.
	 *
	 * Names are opened up for reading (`$lib/tools`): *called **Docker** fetch content*, with
	 * the qualified name a hover away. The server is set in the text rather than in a chip —
	 * a box behind every row turned a quiet gutter into a form.
	 *
	 * The split between a loud failure and a muted one is deliberate: `unknown_tool` and
	 * `tool_error` are the system behaving correctly, and alarming a person about those teaches
	 * them to ignore the colour that matters.
	 */
	import {
		type SkillSelected,
		type ToolCallReady,
		type ToolCallStarted,
		type ToolResultEvent
	} from '$lib/api/events';
	import { duration, t } from '$lib/i18n';
	import { markOf, subject, toolName } from '$lib/tools';
	import type { Activity } from '$lib/turn';
	import Brain from './Brain.svelte';
	import Globe from './Globe.svelte';
	import Ocellus from './Ocellus.svelte';
	import Prose from './Prose.svelte';
	import Quill from './Quill.svelte';
	import Scroll from './Scroll.svelte';
	import Stele from './Stele.svelte';
	import Wrench from './Wrench.svelte';

	interface Props {
		row: Activity;
		/** Whether this turn is the one currently arriving. Only used to decide whether a block
		 * of reasoning is still being written — see `tailing` below. */
		streaming?: boolean;
	}

	let { row, streaming = false }: Props = $props();
	let open = $state(false);

	/** Failures worth raising your voice about. The other two are her working correctly. */
	const LOUD = new Set(['denied', 'unavailable', 'timeout']);

	const skill = $derived(row.kind === 'skill' ? (row.event as SkillSelected) : null);
	const call = $derived(row.event.type === 'tool_call_ready' ? (row.event as ToolCallReady) : null);
	/** A call she has named and not finished writing. The row is drawn from this until the
	 * arguments land, which on a real endpoint is where a turn spends most of its time — see
	 * `ToolCallStarted`. It becomes the `call` above, in place, in `$lib/turn`. */
	const begun = $derived(
		row.event.type === 'tool_call_started' ? (row.event as ToolCallStarted) : null
	);
	const result = $derived(
		row.result ?? (row.event.type === 'tool_result' ? (row.event as ToolResultEvent) : undefined)
	);
	const thought = $derived(
		row.kind === 'thinking' ? ((row.event as { text?: string }).text ?? '') : ''
	);

	const running = $derived(row.kind === 'tool' && !result);
	const named = $derived(toolName(call?.name ?? begun?.name ?? result?.tool ?? ''));
	/** Which mark this row draws. A `skill_selected` event carries no tool name -- the router
	 * chose it and nothing was called -- but it is the same picture as reaching for one. */
	const shape = $derived(row.kind === 'skill' ? 'skill' : markOf(row.event));
	/** Hers reads as a sentence with the tool's own name as the verb — *skill
	 * rust-best-practices* — because the mark beside the row has already said whose tool it is,
	 * and *called **Hera** skill* then spends half the row saying it again. Foreign tools keep
	 * *called **Docker** mcp find*: where something came from is the most important thing about
	 * it when it is not hers, and noise when it is. */
	const mine = $derived(shape !== 'tool' && !!named.server);
	/** What she did it *to*: which skill, what query. Only knowable from the arguments, so an
	 * orphaned result — half a turn, reloaded — falls back to naming the tool instead. */
	const did = $derived(call ? subject(call.name, call.arguments) : '');
	const loud = $derived(!!result && !result.ok && LOUD.has(result.failure ?? ''));

	const why = $derived.by(() => {
		if (!skill) return '';
		if (skill.reason === 'pinned') return t.activity.pinned;
		if (skill.reason === 'slash') return t.activity.slash;
		return t.activity.retrieved;
	});

	const args = $derived(
		call ? Object.entries(call.arguments).map(([key, value]) => `${key}: ${show(value)}`) : []
	);

	/** Long results are the normal case — a skill body is a whole document — so the panel
	 * scrolls at a fixed height rather than pushing the answer off the screen. Saying how much
	 * there is turns "this is cut off" into "there is more, scroll". */
	const lines = $derived(result?.text ? result.text.split('\n').length : 0);

	const words = $derived(thought.trim().split(/\s+/).filter(Boolean).length);
	/** Whether to preview the last lines of this block. Both halves are needed: `row.live` says
	 * the block was still open when the event list ran out, and `streaming` says the list is
	 * still growing. A reloaded turn satisfies the first and not the second, which is right —
	 * there is nothing to follow along with. */
	const tailing = $derived(!!thought && !open && !!row.live && streaming);
	const expandable = $derived(!!thought || args.length > 0 || !!result?.text);

	const trail = $derived.by(() => {
		if (running) return t.activity.running;
		if (result && !result.ok) {
			const known = t.failure[result.failure as keyof typeof t.failure];
			return known ?? result.text.slice(0, 60);
		}
		if (result) return duration(result.duration_ms);
		return '';
	});

	/** Blocks that are not the text already on screen — an image, a resource link. */
	const others = $derived(
		(result?.blocks ?? []).map((block) => String(block.type)).filter((type) => type !== 'text')
	);

	function show(value: unknown): string {
		return typeof value === 'string' ? value : JSON.stringify(value);
	}
</script>

<div class="row" class:loud>
	<span class="gutter">
		{#if row.kind === 'thinking' || row.kind === 'unknown'}
			<Ocellus size={9} alive={running} muted={!running} />
		{:else if shape === 'skill'}
			<Scroll size={13} alive={running} muted={!running && !loud} />
		{:else if shape === 'search'}
			<Globe size={13} alive={running} muted={!running && !loud} />
		{:else if shape === 'note'}
			<Quill size={13} alive={running} muted={!running && !loud} />
		{:else if shape === 'memory'}
			<Brain size={13} alive={running} muted={!running && !loud} />
		{:else if shape === 'artifact'}
			<Stele size={13} alive={running} muted={!running && !loud} />
		{:else}
			<Wrench size={13} alive={running} muted={!running && !loud} />
		{/if}
	</span>

	<button
		class="head"
		type="button"
		disabled={!expandable}
		aria-expanded={expandable ? open : undefined}
		onclick={() => (open = !open)}
	>
		{#if skill}
			<!-- The same shape `hera__skill` gets below. Being handed a skill by the router and
			     reaching for one mid-task are the same event to a reader, and the trail is where
			     the difference belongs. -->
			<span class="verb">{t.activity.skill}</span>
			<span class="target">{skill.skill}</span>
			<span class="trail">{why}</span>
		{:else if row.kind === 'thinking'}
			<span class="verb">{t.activity.thoughtFor}</span>
			<span class="target">{words} {words === 1 ? 'word' : 'words'}</span>
			<span class="trail">{open ? t.activity.hide : t.activity.show}</span>
		{:else if row.kind === 'unknown'}
			<span class="verb">{row.event.type}</span>
			<span class="trail">{t.activity.unknown}</span>
		{:else if mine && (did || begun)}
			<!-- Her own tool reads with its own name as the verb. `begun` keeps it that way while
			     the arguments are still arriving, so the row does not say *called scratch write*
			     for a minute and then change its mind to *scratch write design-plan.md*: the
			     wording settles once and only the target fills in. -->
			<span class="verb">{named.action}</span>
			<span class="target" title={named.qualified}>{did}</span>
			<span class="trail">{trail}</span>
		{:else}
			<span class="verb">{result && !result.ok ? '' : t.activity.called}</span>
			<span class="target" title={named.qualified}>
				{#if named.server && !mine}<strong>{named.server}</strong>{/if}
				{named.action}
			</span>
			<span class="trail">{trail}</span>
		{/if}
	</button>
</div>

{#if tailing}
	<!-- The tail of what she is thinking, while she is still thinking it.
	     A collapsed row says "thought · 213 words · Show", which is a receipt: it tells you
	     something happened and nothing about what. Following her reasoning meant opening a panel,
	     and while a turn is still running that panel grows under your cursor. Three lines of the
	     *most recent* words is enough to follow along and small enough to ignore.

	     It closes to nothing the moment the block does. A finished thought is a record and reads
	     as one row; only the one still being written earns three lines of the gutter, and a turn
	     with six blocks in it would otherwise be a wall of half-sentences nobody is reading any
	     more.

	     Anchored to the bottom rather than truncated at the top: the box is three lines tall, the
	     prose inside it is however long it is, and `justify-content: flex-end` pushes the end of
	     it into view. Taking the last N characters in JavaScript would have to guess how many
	     fit, and would guess wrong at every window width. -->
	<div class="body">
		<span class="gutter hairline"></span>
		<p class="tail" aria-hidden="true">{thought}</p>
	</div>
{/if}

{#if open}
	<div class="body">
		<span class="gutter hairline"></span>
		<div class="detail">
			{#if thought}
				<!-- Reasoning is written in the same notation her answers are, so it is set the
				     same way (ADR 11) — quieter, a step smaller, and never mixed into the prose
				     above. A wall of unbroken text was the one place her thinking was harder to
				     read than her answer. -->
				<div class="thinking"><Prose text={thought} /></div>
			{:else}
				{#if args.length}
					<ul class="args mono">
						{#each args as line (line)}<li>{line}</li>{/each}
					</ul>
				{/if}
				{#if result?.text}
					<div class="result">
						<pre class="mono">{result.text}</pre>
					</div>
					{#if lines > 12}
						<p class="caption size">{t.activity.lines(lines)}</p>
					{/if}
				{/if}
				{#if others.length}
					<!-- A result can be an image or a resource link (ADR 4). Those are named,
					     because the text above is not all of what came back. Plain text blocks
					     are what the panel already shows, and listing "text" under it said
					     nothing. -->
					<p class="caption">{others.join(', ')}</p>
				{/if}
			{/if}
		</div>
	</div>
{/if}

<style>
	.row,
	.body {
		display: grid;
		grid-template-columns: 18px 1fr;
		align-items: start;
		gap: 9px;

		/* One line of the row, named once. The mark's cell is exactly this tall and centres
		   inside it, so every mark sits on the same optical line as its words whatever size
		   the glyph is — rather than each icon being nudged with its own padding until it
		   looks about right, which is what left the 13 px ones two pixels low. */
		--line-box: 25px;
	}

	.gutter {
		display: flex;
		align-items: center;
		justify-content: center;
		height: var(--line-box);
		position: relative;
	}

	/* The hairline that joins the eyes into one column. */
	.gutter::before {
		content: '';
		position: absolute;
		inset: 0 auto -6px 50%;
		width: 1px;
		background: var(--line);
		transform: translateX(-50%);
	}

	/* Every mark sits on the ground colour and breaks the hairline, rather than having the
	   line drawn across it. An eye with a wire through it is not an eye. */
	.gutter :global(.ocellus),
	.gutter :global(.wrench),
	.gutter :global(.scroll),
	.gutter :global(.globe),
	.gutter :global(.quill),
	.gutter :global(.knot),
	.gutter :global(.stele) {
		position: relative;
		background: var(--ground);
		padding: 3px 0;
		box-sizing: content-box;
	}

	.hairline {
		align-self: stretch;
		height: auto;
	}

	.head {
		display: flex;
		align-items: baseline;
		gap: 9px;
		width: 100%;
		text-align: left;
		font-size: 13.5px;
		line-height: var(--line-box);
		color: var(--text-muted);
		border-radius: 4px;
		transition: color var(--fade) var(--ease);
	}

	.head:not(:disabled):hover {
		color: var(--text);
	}

	.head:disabled {
		cursor: default;
	}

	/* A real column, not a hint. This was 34px — narrower than the word "thought" — so every
	   verb rendered at its natural width and the targets beside them started at a different x on
	   every row. A gutter is read down its left edge; ragged starts are the one thing that stops
	   it being a column at all. Sized in `em` so it tracks the type rather than being a number
	   that quietly stops fitting the next time this grows.

	   Clipped as well as fixed, because for her own tools the verb *is* the tool's name and the
	   longest one is not knowable here: a tool added to `hera_mcp` with a long name would
	   otherwise push its own row's target out of the column and be the only row that does.

	   Widened from 5.2em when the scratchpad landed, which is the case the paragraph above
	   predicted: `scratch write` and `scratch read` both clipped to `scratch w…` and `scratch
	   r…`, so the two rows a person most needs to tell apart were the two the column made
	   identical. 8em fits her longest name with room, and the target still has the reading
	   column to itself. */
	.verb {
		width: 8em;
		flex: none;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--text-faint);
	}

	/* `min-width: 0` is the one that matters: a flex item will not shrink below its content by
	   default, so a search query long enough — and hers are model-written, so they are — pushed
	   the whole row wider than the column and took the duration off the end of it with it.
	   Ellipsis needs somewhere to happen, and this is what gives it somewhere.

	   `max-width` on top of that is a reading decision rather than a layout one: a row that
	   fills every pixel up to the duration is a paragraph, not a gutter entry, and the column of
	   times down the right stops reading as a column when one line reaches it and the rest do
	   not. The whole query is in the expanded panel and in the tooltip. */
	.target {
		min-width: 0;
		max-width: 46ch;
		color: var(--text-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* Where it came from, set in the sentence rather than boxed. Five chips down a gutter read
	   as a form; the same five words in bold read as a list of things she did. */
	.target strong {
		font-weight: 600;
		color: var(--text);
	}

	/* `padding-left` rather than a wider gap, so the breathing room only exists on the side that
	   can be reached by a truncated target. An ellipsis that stops one space short of a duration
	   reads as a collision even when it is not one. */
	.trail {
		margin-left: auto;
		flex: none;
		padding-left: 14px;
		color: var(--text-faint);
		font-variant-numeric: tabular-nums;
	}

	.loud .trail {
		color: var(--danger);
	}

	.detail {
		padding: 2px 0 10px;
		font-size: 13.5px;
		color: var(--text-muted);
	}

	/* Two lines of her reasoning, ending at the end of it. A fixed-height column that puts its
	   content at the bottom, so the overflow happens off the *top* and what you are left looking
	   at is the most recent thing she wrote. The mask fades that cut instead of leaving a hard
	   edge halfway through a letter. */
	.tail {
		display: flex;
		flex-direction: column;
		justify-content: flex-end;
		/* Three full lines and a sliver of the one above them. The sliver is what says *there is
		   more of this* — without it, three clean lines read as the whole thought. */
		max-height: 4.55em;
		margin: 0;
		padding-bottom: 7px;
		overflow: hidden;
		font-family: var(--font-body);
		font-size: 13px;
		line-height: 1.45;
		color: var(--text-faint);
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		mask-image: linear-gradient(to bottom, transparent, #000 0.9em);
	}

	.args {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.args li {
		overflow-wrap: anywhere;
	}

	/* A skill body is a document, and this is a gutter row. It scrolls inside a fixed frame
	   rather than pushing her answer down the page. */
	.result {
		margin: 6px 0 0;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		max-height: 15em;
		overflow: auto;
		overscroll-behavior: contain;
	}

	.result pre {
		margin: 0;
		padding: 8px 10px;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}

	.size {
		margin: 4px 0 0;
		color: var(--text-faint);
	}

	/* `:global`, because the prose is rendered through `{@html}` and Svelte's scoped classes
	   never reach it. Scoped under `.thinking` so this is still only about this row. */
	.thinking :global(.prose) {
		font-size: 15px;
		line-height: 1.6;
		color: var(--text-muted);
	}

	.thinking :global(.prose h1),
	.thinking :global(.prose h2),
	.thinking :global(.prose h3) {
		font-size: 15px;
		margin: 1em 0 0.3em;
	}

	.thinking :global(.prose pre) {
		background: var(--ground);
	}
</style>
