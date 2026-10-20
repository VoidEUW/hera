<script lang="ts">
	/**
	 * One row of the activity gutter (the theme's `hera/thought-trace` and `hera/tool-call`, soft
	 * look with Heaven's parts): a 7px dot in the row's state colour on a dashed hairline, the verb
	 * in small mono capitals, the target, and the duration in mono at the end. Opens to show its
	 * body — her reasoning, a call's input and result — on `trace.disclose`.
	 *
	 * The dot says what *state* the row is in, never what kind of thing it is — the verb already
	 * says that: `quiet` (a thought, a skill), `live` (a call out, pulsing on `tool.running`),
	 * `done` (laurel, with a check after the duration that draws its own stroke when it settles
	 * while you watch, `tool.done`), `failed` (danger, the target struck through at once).
	 */
	import type { Snippet } from 'svelte';
	import { t } from '$lib/i18n';
	import { disclose } from '$lib/motion';
	import { tooltip } from '$lib/tooltip';
	import Icon from './Icon.svelte';

	interface Props {
		state?: 'quiet' | 'live' | 'done' | 'failed';
		verb: string;
		/** The target, as text. Use `target` for anything richer. */
		text?: string;
		target?: Snippet;
		/** The end of the row: a duration, "running…", a reason. */
		meta?: string;
		/** Draw the done check's stroke — a call that settled while you watched. */
		fresh?: boolean;
		/** A failure worth raising its voice: the meta goes danger too. */
		loud?: boolean;
		/** A tooltip on the target — the qualified tool name. */
		hint?: string;
		/** End the row with Show / Hide instead of a meta. */
		toggle?: boolean;
		open?: boolean;
		/** For a row whose body is elsewhere — the gutter's own "did 5 things" line, which opens
		 * the rows under it rather than a panel of its own. */
		ontoggle?: (open: boolean) => void;
		body?: Snippet;
	}

	let {
		state = 'quiet',
		verb,
		text,
		target,
		meta,
		fresh = false,
		loud = false,
		hint,
		toggle = false,
		open = $bindable(false),
		ontoggle,
		body
	}: Props = $props();

	const expandable = $derived(Boolean(body || ontoggle));

	function flip() {
		if (ontoggle) ontoggle(!open);
		else open = !open;
	}
</script>

<div class="row" class:loud>
	<span class="gutter"><span class="dot {state}" aria-hidden="true"></span></span>
	<button
		class="line"
		type="button"
		disabled={!expandable}
		aria-expanded={expandable ? open : undefined}
		onclick={flip}
	>
		<span class="verb">{verb}</span>
		<span class="target" class:struck={state === 'failed'} use:tooltip={hint}>
			{#if target}{@render target()}{:else}{text}{/if}
		</span>
		<span class="meta">
			{#if toggle}
				<span class="link">{open ? t.activity.hide : t.activity.show}</span>
			{:else}
				{meta ?? ''}
				{#if state === 'done'}
					<span class="check" class:fresh><Icon name="check" size="13px" /></span>
				{/if}
			{/if}
		</span>
	</button>
</div>
{#if open && body}
	<div
		class="body"
		in:disclose={{ slot: 'trace-disclose' }}
		out:disclose={{ slot: 'trace-disclose' }}
	>
		<span class="gutter rule"></span>
		<div class="detail">{@render body()}</div>
	</div>
{/if}

<style>
	.row {
		animation: row-in var(--motion-trace-row);
	}

	@keyframes row-in {
		from {
			opacity: 0;
		}
	}

	.row,
	.body {
		--line-box: 22px;
		display: grid;
		grid-template-columns: 9px minmax(0, 1fr);
		column-gap: 11px;
		align-items: start;
	}

	.gutter {
		position: relative;
		display: grid;
		place-items: center;
		height: var(--line-box);
	}

	/* `trace.line`: a dashed hairline joining the dots, grown down from the first one. */
	.gutter::before {
		content: '';
		position: absolute;
		inset: 0 auto -2px 50%;
		width: 0;
		border-left: var(--border-width) dashed var(--line);
		transform: translateX(-50%);
		transform-origin: top;
		animation: grow var(--motion-trace-line);
	}

	.rule {
		align-self: stretch;
		height: auto;
	}

	@keyframes grow {
		from {
			transform: translateX(-50%) scaleY(0);
		}
	}

	/* `trace.marker: dot` — 7px, in the row's state colour, on the ground so the line breaks
	   around it. */
	.dot {
		position: relative;
		width: 7px;
		height: 7px;
		border-radius: 50%;
		background: var(--text-faint);
		box-shadow: 0 0 0 3px var(--ground);
	}

	.live,
	.done {
		background: var(--laurel);
	}

	.failed {
		background: var(--danger);
	}

	/* `tool.running`, the eye preset: the dot pulses in scale and opacity. */
	.live {
		animation: pulse var(--motion-tool-running) infinite;
	}

	@keyframes pulse {
		0%,
		100% {
			transform: scale(0.55);
			opacity: 0.35;
		}
		50% {
			transform: scale(1);
			opacity: 1;
		}
	}

	.line {
		display: flex;
		align-items: baseline;
		gap: 7px;
		width: 100%;
		min-width: 0;
		min-height: var(--line-box);
		padding: 2px 0;
		color: var(--text-muted);
		font-size: 12.5px;
		line-height: 18px;
		text-align: left;
	}

	.line:disabled {
		cursor: default;
	}

	/* `trace.verb: caps` — small mono capitals, in a column so every target starts on one x. */
	.verb {
		flex: none;
		width: 9em;
		overflow: hidden;
		color: var(--text-faint);
		font: 500 10px/1.9 var(--font-mono);
		letter-spacing: 0.09em;
		text-overflow: ellipsis;
		text-transform: uppercase;
		white-space: nowrap;
	}

	.row:has(.live) .verb {
		color: var(--laurel);
	}

	.target {
		flex: 1;
		min-width: 0;
		max-width: 46ch;
		overflow: hidden;
		color: var(--text-muted);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.target :global(strong) {
		color: var(--text);
		font-weight: 600;
	}

	/* `tool.error: strike` — the target struck through in danger, at once (`tool.error: none`). */
	.struck {
		color: var(--danger);
		text-decoration: line-through;
		text-decoration-color: var(--danger);
	}

	/* `trace.meta: mono` — the duration small and mono, in a column down the right. */
	.meta {
		display: inline-flex;
		flex: none;
		align-items: center;
		gap: 5px;
		margin-left: auto;
		padding-left: 14px;
		color: var(--text-faint);
		font: 10.5px var(--font-mono);
		font-variant-numeric: tabular-nums;
	}

	.loud .meta,
	.row:has(.failed) .meta {
		color: var(--danger);
	}

	.link {
		text-decoration: underline;
		text-decoration-color: var(--line);
		text-underline-offset: 2px;
	}

	.line:hover .link {
		color: var(--text-muted);
	}

	/* `tool.done: check` — a laurel check after the duration. */
	.check {
		display: inline-flex;
		color: var(--laurel);
		--icon-stroke: 2.4;
	}

	.check.fresh :global(path) {
		stroke-dasharray: 24;
		animation: draw var(--motion-tool-done) both;
	}

	@keyframes draw {
		from {
			stroke-dashoffset: 24;
		}
	}

	.detail {
		min-width: 0;
		padding: 4px 0 8px;
		color: var(--text-muted);
		font-size: 13px;
	}
</style>
