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
	import Prose from './Prose.svelte';
	import TraceRow from './ui/TraceRow.svelte';

	interface Props {
		row: Activity;
		/** Whether this turn is the one currently arriving. A call that settles while you watch
		 * draws its check; one loaded from history just has it. */
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
	/** What the dot says (ADR 21): a thought or a skill is quiet, a call is live while it runs
	 * and settled in laurel once it answered, and a failure is danger. The kind of thing is the
	 * verb's job, not the dot's. */
	const standing = $derived.by((): 'quiet' | 'live' | 'done' | 'failed' => {
		if (row.kind !== 'tool') return 'quiet';
		if (!result) return 'live';
		return result.ok ? 'done' : 'failed';
	});
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

{#snippet detail()}
	{#if thought}
		<!-- Reasoning is written in the same notation her answers are, so it is set the same way
		     (ADR 11) — quieter, a step smaller, and never mixed into the prose above. -->
		<div class="thinking"><Prose text={thought} /></div>
	{:else}
		{#if args.length || result?.text}
			<!-- The call's input and what came back, in the tool-call's own bordered box (`.tr-io`).
			     A skill body is a document and this is a gutter row, so it scrolls inside a fixed
			     frame rather than pushing her answer down the page. -->
			<div class="io">
				{#each args as line (line)}<div class="arg">{line}</div>{/each}
				{#if result?.text}
					{#if args.length}<div class="arrow">→</div>{/if}
					<pre>{result.text}</pre>
				{/if}
			</div>
			{#if lines > 12}<p class="size">{t.activity.lines(lines)}</p>{/if}
		{/if}
		{#if others.length}
			<!-- A result can be an image or a resource link (ADR 4). Those are named, because the
			     text above is not all of what came back. -->
			<p class="size">{others.join(', ')}</p>
		{/if}
	{/if}
{/snippet}

{#snippet foreign()}
	{#if named.server && !mine}<strong>{named.server}</strong>{/if}
	{named.action}
{/snippet}

{#if skill}
	<!-- The same shape `hera__skill` gets below: being handed a skill by the router and reaching for
	     one mid-task are the same event to a reader, and the meta is where the difference goes. -->
	<TraceRow verb={t.activity.skill} text={skill.skill} meta={why} />
{:else if row.kind === 'thinking'}
	<!-- `trace.tail: none` — a shut thought shows only its word count. -->
	<TraceRow
		verb={t.activity.thoughtFor}
		text="{words} {words === 1 ? 'word' : 'words'}"
		toggle
		bind:open
		body={thought ? detail : undefined}
	/>
{:else if row.kind === 'unknown'}
	<TraceRow verb={row.event.type} meta={t.activity.unknown} />
{:else if mine && (did || begun)}
	<!-- Her own tool reads with its own name as the verb. `begun` keeps it that way while the
	     arguments are still arriving, so the wording settles once and only the target fills in. -->
	<TraceRow
		state={standing}
		verb={named.action}
		text={did}
		meta={trail}
		fresh={streaming}
		{loud}
		hint={named.qualified}
		bind:open
		body={expandable ? detail : undefined}
	/>
{:else}
	<TraceRow
		state={standing}
		verb={t.activity.called}
		target={foreign}
		meta={trail}
		fresh={streaming}
		{loud}
		hint={named.qualified}
		bind:open
		body={expandable ? detail : undefined}
	/>
{/if}

<style>
	.io {
		max-height: 15em;
		margin: 2px 0;
		padding: 8px 10px;
		overflow: auto;
		overscroll-behavior: contain;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: var(--surface);
		color: var(--text-muted);
		font: 12px/1.55 var(--font-mono);
	}

	.arg {
		overflow-wrap: anywhere;
	}

	.arrow {
		color: var(--text-faint);
	}

	pre {
		margin: 0;
		font: inherit;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}

	.size {
		margin: 4px 0 0;
		color: var(--text-faint);
		font-size: 12px;
	}

	/* `:global`, because the prose is rendered through `{@html}`. */
	.thinking :global(.prose) {
		color: var(--text-muted);
		font-size: 14px;
		line-height: 1.65;
	}

	.thinking :global(.prose h1),
	.thinking :global(.prose h2),
	.thinking :global(.prose h3) {
		margin: 1em 0 0.3em;
		font-size: 14px;
	}
</style>
