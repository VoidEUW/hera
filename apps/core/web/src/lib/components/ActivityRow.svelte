<script lang="ts">
	/**
	 * One row in the activity gutter: an 8 px ocellus on a hairline, the verb, the target, and
	 * how long it took. Quiet, expandable, caption type on muted text.
	 *
	 * A turn with six tool calls draws six eyes down its left gutter, joined by a hairline —
	 * activity becomes a column of eyes you read at a glance. That is the hundred eyes of Argus,
	 * and it is why this is a row of its own rather than a log line.
	 *
	 * The split between a loud failure and a muted one is deliberate: `unknown_tool` and
	 * `tool_error` are the system behaving correctly, and alarming a person about those teaches
	 * them to ignore the colour that matters.
	 */
	import type { SkillSelected, ToolCallReady, ToolResultEvent } from '$lib/api/events';
	import { duration, t } from '$lib/i18n';
	import type { Activity } from '$lib/turn';
	import Ocellus from './Ocellus.svelte';

	interface Props {
		row: Activity;
	}

	let { row }: Props = $props();
	let open = $state(false);

	/** Failures worth raising your voice about. The other two are her working correctly. */
	const LOUD = new Set(['denied', 'unavailable', 'timeout']);

	const skill = $derived(row.kind === 'skill' ? (row.event as SkillSelected) : null);
	const call = $derived(row.event.type === 'tool_call_ready' ? (row.event as ToolCallReady) : null);
	const result = $derived(
		row.result ?? (row.event.type === 'tool_result' ? (row.event as ToolResultEvent) : undefined)
	);
	const thought = $derived(
		row.kind === 'thinking' ? ((row.event as { text?: string }).text ?? '') : ''
	);

	const running = $derived(row.kind === 'tool' && !result);
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

	const words = $derived(thought.trim().split(/\s+/).filter(Boolean).length);
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

	function show(value: unknown): string {
		return typeof value === 'string' ? value : JSON.stringify(value);
	}
</script>

<div class="row" class:loud>
	<span class="gutter"><Ocellus size={8} alive={running} muted={!running} /></span>

	<button
		class="head"
		type="button"
		disabled={!expandable}
		aria-expanded={expandable ? open : undefined}
		onclick={() => (open = !open)}
	>
		{#if skill}
			<span class="verb">{t.activity.used}</span>
			<span class="target">{skill.skill}</span>
			<span class="trail">{why}</span>
		{:else if row.kind === 'thinking'}
			<span class="verb">{t.activity.thoughtFor}</span>
			<span class="target">{words} {words === 1 ? 'word' : 'words'}</span>
			<span class="trail">{open ? t.activity.hide : t.activity.show}</span>
		{:else if row.kind === 'unknown'}
			<span class="verb">{row.event.type}</span>
			<span class="trail">{t.activity.unknown}</span>
		{:else}
			<span class="verb">{result && !result.ok ? '' : t.activity.ran}</span>
			<span class="target mono">{call?.name ?? result?.tool}</span>
			<span class="trail">{trail}</span>
		{/if}
	</button>
</div>

{#if open}
	<div class="body">
		<span class="gutter hairline"></span>
		<div class="detail">
			{#if thought}
				<p class="thinking">{thought}</p>
			{:else}
				{#if args.length}
					<ul class="args mono">
						{#each args as line (line)}<li>{line}</li>{/each}
					</ul>
				{/if}
				{#if result?.text}
					<pre class="result mono">{result.text}</pre>
				{/if}
				{#if result?.blocks?.length}
					<!-- A result can be an image or a resource link (ADR 4). The row names what
					     arrived rather than flattening it to a string. -->
					<p class="caption">{result.blocks.map((block) => String(block.type)).join(', ')}</p>
				{/if}
			{/if}
		</div>
	</div>
{/if}

<style>
	.row,
	.body {
		display: grid;
		grid-template-columns: 16px 1fr;
		align-items: start;
		gap: 8px;
	}

	.gutter {
		display: flex;
		justify-content: center;
		padding-top: 5px;
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

	.gutter :global(.ocellus) {
		position: relative;
		background: var(--ground);
	}

	.hairline {
		align-self: stretch;
		padding: 0;
	}

	.head {
		display: flex;
		align-items: baseline;
		gap: 8px;
		width: 100%;
		text-align: left;
		font-size: 12.5px;
		line-height: 1.9;
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

	.verb {
		min-width: 34px;
		color: var(--text-faint);
	}

	.target {
		color: var(--text-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.trail {
		margin-left: auto;
		flex: none;
		color: var(--text-faint);
		font-variant-numeric: tabular-nums;
	}

	.loud .trail {
		color: var(--danger);
	}

	.detail {
		padding: 2px 0 10px;
		font-size: 12.5px;
		color: var(--text-muted);
	}

	.args {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.args li {
		overflow-wrap: anywhere;
	}

	.result {
		margin: 6px 0 0;
		padding: 8px 10px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		white-space: pre-wrap;
		overflow-wrap: anywhere;
		max-height: 18em;
		overflow: auto;
	}

	.thinking {
		margin: 0;
		font-family: var(--font-body);
		font-size: 15px;
		line-height: 1.6;
		white-space: pre-wrap;
		color: var(--text-muted);
		max-width: var(--measure);
	}
</style>
