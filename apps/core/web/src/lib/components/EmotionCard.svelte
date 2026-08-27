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
	 */
	import type { ToolCallReady } from '$lib/api/events';

	interface Props {
		call: ToolCallReady;
	}

	let { call }: Props = $props();

	type Tone = 'warm' | 'cool' | 'sharp' | 'soft';

	const TONES: Record<string, Tone> = {
		agree: 'warm',
		hope: 'warm',
		excited: 'warm',
		funny: 'warm',
		joke: 'warm',
		curious: 'cool',
		surprised: 'cool',
		doubt: 'cool',
		ask: 'cool',
		warn: 'sharp',
		disagree: 'sharp',
		judge: 'sharp',
		annoyed: 'sharp',
		sorry: 'soft'
	};

	const GLYPHS: Record<Tone, string> = {
		warm: '◕',
		cool: '◔',
		sharp: '◑',
		soft: '◌'
	};

	const kind = $derived(String(call.arguments.kind ?? 'note'));
	const text = $derived(String(call.arguments.text ?? ''));
	// Every unknown kind is `soft`, which reads as a stance she is holding lightly -- a
	// reasonable thing for a word nobody anticipated.
	const tone = $derived<Tone>(TONES[kind] ?? 'soft');
</script>

<aside class="card" data-tone={tone}>
	<span class="glyph" aria-hidden="true">{GLYPHS[tone]}</span>
	<div class="content">
		<p class="kind">{kind}</p>
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

	.card[data-tone='warm'] {
		--edge: var(--pomegranate);
	}
	.card[data-tone='cool'] {
		--edge: var(--peacock);
	}
	.card[data-tone='sharp'] {
		--edge: var(--brass);
	}
	.card[data-tone='soft'] {
		--edge: var(--line);
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
