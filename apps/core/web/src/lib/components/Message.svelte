<script lang="ts">
	/**
	 * One message: the activity gutter above, then her prose with cards in the flow of it.
	 *
	 * Renders one component per event variant and parses nothing. A new kind of thing a turn can
	 * contain is one branch here, never a regular expression — that rule is the single largest
	 * source of bugs in the previous version, and it is designed out.
	 */
	import type { AnyEvent, PermissionRequired, ToolCallReady } from '$lib/api/events';
	import { size } from '$lib/attachments';
	import { t } from '$lib/i18n';
	import { isAnswered, reduce } from '$lib/turn';
	import ActivityRow from './ActivityRow.svelte';
	import EmotionCard from './EmotionCard.svelte';
	import Ocellus from './Ocellus.svelte';
	import PermissionCard from './PermissionCard.svelte';

	interface Props {
		role: 'user' | 'assistant';
		content?: string;
		/** Files sent with a user message. Names and sizes, drawn as chips — the contents went
		 * to the model and are not needed to render them. */
		attachments?: Array<{ name: string; bytes: number }>;
		events?: AnyEvent[];
		/** Whether this message is the turn currently arriving. */
		streaming?: boolean;
		busy?: boolean;
		onanswer?: (callId: string, allow: boolean, remember: boolean) => void;
	}

	let {
		role,
		content = '',
		attachments = [],
		events = [],
		streaming = false,
		busy = false,
		onanswer
	}: Props = $props();

	const turn = $derived(reduce(events));
	const closed = $derived(turn.closed);
	// The one piece of choreography: the ocellus appears where her answer will begin, and when
	// the first text arrives it shrinks into the gutter as the first eye of the turn.
	const waiting = $derived(streaming && turn.inline.length === 0 && turn.activity.length === 0);

	const note = $derived.by(() => {
		if (!closed || closed.reason === 'completed') return '';
		if (closed.reason === 'failed') return closed.error || t.turn.failed;
		return t.turn[closed.reason] ?? '';
	});

	function decision(callId: string) {
		if (!isAnswered(events, callId)) return null;
		const event = events.find(
			(candidate) =>
				candidate.type === 'permission_decided' &&
				(candidate as { call_id: string }).call_id === callId
		) as { allowed: boolean; remembered: boolean } | undefined;
		return event ?? null;
	}
</script>

{#if role === 'user'}
	<div class="mine">
		<div class="bubble">
			{#if content.trim()}<p class="said">{content}</p>{/if}
			{#if attachments.length}
				<ul class="files">
					{#each attachments as file (file.name)}
						<li>
							<span class="mono">{file.name}</span>
							<span class="bytes">{size(file.bytes)}</span>
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	</div>
{:else}
	<article class="hers">
		{#if turn.activity.length}
			<div class="gutter">
				{#each turn.activity as row (row.key)}
					<ActivityRow {row} />
				{/each}
			</div>
		{/if}

		{#if waiting}
			<p class="waiting"><Ocellus size={16} alive /> <span class="sr-only">Thinking</span></p>
		{/if}

		{#each turn.inline as item (item.key)}
			{#if item.kind === 'prose'}
				<div class="prose">
					{#each (item.text ?? '').split(/\n{2,}/) as paragraph, index (index)}
						<p>{paragraph}</p>
					{/each}
				</div>
			{:else if item.kind === 'emotion'}
				<EmotionCard call={item.event as ToolCallReady} />
			{:else if item.kind === 'permission'}
				{@const card = item.event as PermissionRequired}
				<PermissionCard
					{card}
					decided={decision(card.call_id)}
					{busy}
					onanswer={(allow, remember) => onanswer?.(card.call_id, allow, remember)}
				/>
			{/if}
		{/each}

		{#if note}
			<p class="note" class:bad={closed?.reason === 'failed'}>{note}</p>
		{/if}
	</article>
{/if}

<style>
	.mine {
		display: flex;
		justify-content: flex-end;
		margin: 22px 0;
	}

	.said {
		margin: 0;
		white-space: pre-wrap;
	}

	.files {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		list-style: none;
		margin: 8px 0 0;
		padding: 0;
	}

	.files:first-child {
		margin-top: 0;
	}

	.files li {
		display: flex;
		align-items: baseline;
		gap: 8px;
		padding: 3px 10px;
		background: var(--ground);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 12.5px;
	}

	.bytes {
		color: var(--text-faint);
	}

	.bubble {
		max-width: 46ch;
		padding: 10px 14px;
		background: var(--surface-raised);
		border-radius: var(--radius-lg);
		border-bottom-right-radius: 4px;
		font-family: var(--font-body);
		font-size: 16px;
		line-height: 1.55;
		overflow-wrap: anywhere;
	}

	.hers {
		margin: 22px 0 30px;
	}

	.gutter {
		margin-bottom: 12px;
	}

	.waiting {
		margin: 0;
	}

	.note {
		margin: 12px 0 0;
		font-size: 12.5px;
		color: var(--text-muted);
	}

	.note.bad {
		color: var(--danger);
	}
</style>
