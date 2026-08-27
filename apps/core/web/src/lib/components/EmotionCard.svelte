<script lang="ts">
	/**
	 * `hera__emotion(kind, text)`, rendered where she called it.
	 *
	 * Inline, between paragraphs, because that is where she meant it (ADR 3). `kind` is free
	 * text and she is told she may invent one — so the map below is a *starting vocabulary*, and
	 * the fallback has to look deliberate rather than broken. An unfamiliar emotion is her
	 * working correctly, not a missing asset.
	 *
	 * The left edge is coloured by tone, not by kind, which is what lets an invented kind land
	 * somewhere sensible instead of nowhere.
	 *
	 * **Warm is not red.** Pomegranate is *her* — the mark, send, the active chat — and next to
	 * `--danger` in a dark interface it reads as an alarm, so a card saying *agree* looked like
	 * something had gone wrong. Warmth is brass here: her authority, the same colour her skills
	 * and permission cards already use. Nothing in this component is allowed to be the danger
	 * colour, because no stance she can hold is an error.
	 */
	import type { ToolCallReady } from '$lib/api/events';
	import { workspace } from '$lib/stores/workspace.svelte';

	interface Props {
		call: ToolCallReady;
	}

	let { call }: Props = $props();

	type Tone = 'warm' | 'cool' | 'sharp' | 'soft';

	const GLYPHS: Record<Tone, string> = {
		warm: '◕',
		cool: '◔',
		sharp: '◑',
		soft: '◌'
	};

	const kind = $derived(String(call.arguments.kind ?? 'note'));
	const text = $derived(String(call.arguments.text ?? ''));

	// The vocabulary is the person's, edited in Settings -> Emotions and read by the prompt
	// from the same list. There is no table of tones in this file any more: one that disagreed
	// with what she was told would draw her stance in the wrong colour and nobody could say why.
	const known = $derived(workspace.emotions.find((entry) => entry.kind === kind) ?? null);

	// Every unknown kind is `soft`, which reads as a stance she is holding lightly -- a
	// reasonable thing for a word nobody anticipated, and the case ADR 3 requires to look
	// deliberate rather than broken.
	const tone = $derived<Tone>(known?.tone ?? 'soft');
</script>

<aside class="card" data-tone={tone}>
	<span class="glyph" aria-hidden="true">{GLYPHS[tone]}</span>
	<div class="content">
		<p class="kind" title={known?.description ?? ''}>{kind}</p>
		{#if text}
			<!-- `text` may be absent: a card that is only a stance is valid. -->
			<p class="text">{text}</p>
		{/if}
	</div>
</aside>

<style>
	.card {
		display: flex;
		gap: 12px;
		align-items: flex-start;
		margin: 14px 0;
		padding: 12px 14px;
		max-width: var(--measure);
		background: var(--surface);
		border: 1px solid var(--line);
		border-left: 3px solid var(--edge, var(--line));
		border-radius: var(--radius);
	}

	/* Warm and sharp are both brass, distinguished by the glyph rather than by hue: two
	   neighbouring colours saying "positive" and "careful" is a distinction nobody reads
	   correctly anyway, and one of them would have to be red. */
	.card[data-tone='warm'] {
		--edge: var(--brass);
	}
	.card[data-tone='cool'] {
		--edge: var(--laurel);
	}
	.card[data-tone='sharp'] {
		--edge: var(--brass);
	}
	.card[data-tone='soft'] {
		--edge: var(--text-faint);
	}

	.glyph {
		font-size: 15px;
		line-height: 1.5;
		color: var(--edge);
	}

	.content {
		min-width: 0;
	}

	.kind {
		margin: 0;
		font-size: 12.5px;
		letter-spacing: 0.02em;
		color: var(--edge);
	}

	.text {
		margin: 2px 0 0;
		font-family: var(--font-body);
		font-size: 15px;
		line-height: 1.55;
		color: var(--text);
		overflow-wrap: anywhere;
	}
</style>
