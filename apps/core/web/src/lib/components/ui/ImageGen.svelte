<script lang="ts">
	/**
	 * An image she is making (the theme's `hera/image-gen`, open look): a hairline frame with small
	 * corners, the prompt and the step counter under it in mono.
	 *
	 * - `queued` — a skeleton sweep and a spinner saying what it waits for;
	 * - `generating` — the picture visible from the start, blurred and desaturated, sharpening as
	 *   the steps complete (`imagegen.progress`);
	 * - `done` — out of the last of the blur (`imagegen.reveal`);
	 * - `failed` — the picture faded to grey under a panel that names the reason and offers Retry
	 *   (`imagegen.error`).
	 *
	 * Built and on `/design`; Hera has no image model to drive it yet.
	 */
	import { t } from '$lib/i18n';
	import Button from './Button.svelte';
	import Icon from './Icon.svelte';
	import Spinner from './Spinner.svelte';

	interface Props {
		state: 'queued' | 'generating' | 'done' | 'failed';
		prompt: string;
		/** What is drawn — the final image, or the current preview while generating. */
		src?: string;
		step?: number;
		steps?: number;
		/** What finished means: "3.3 s · 1280 × 800". */
		summary?: string;
		reason?: string;
		onretry?: () => void;
	}

	let {
		state,
		prompt,
		src,
		step = 0,
		steps = 30,
		summary = '',
		reason = '',
		onretry
	}: Props = $props();

	const progress = $derived(steps > 0 ? Math.min(1, step / steps) : 0);
	const line = $derived(
		state === 'queued'
			? t.imagegen.queued
			: state === 'generating'
				? t.imagegen.step(step, steps, Math.round(progress * 100))
				: state === 'failed'
					? t.imagegen.failedAt(step)
					: t.imagegen.done(summary)
	);
</script>

<figure class="imagegen" data-state={state} style:--progress={progress}>
	<div class="frame">
		<div class="placeholder"></div>
		{#if src}<img class="picture" {src} alt={prompt} />{/if}
		{#if state === 'queued'}
			<div class="queue"><Spinner size={16} label={t.imagegen.waiting} /></div>
		{:else if state === 'failed'}
			<div class="failure" role="alert">
				<Icon name="alert" size="22px" />
				<b>{t.imagegen.failed}</b>
				<span>{reason}</span>
				{#if onretry}<Button size="sm" icon="refresh" onclick={onretry}>{t.ui.retry}</Button>{/if}
			</div>
		{/if}
	</div>
	<figcaption>
		<span class="prompt">“{prompt}”</span>
		<span class="step">{line}</span>
	</figcaption>
</figure>

<style>
	.imagegen {
		display: flex;
		flex-direction: column;
		gap: 8px;
		width: min(100%, 440px);
		margin: 0;
	}

	.frame {
		position: relative;
		aspect-ratio: 16 / 10;
		overflow: hidden;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: var(--surface-raised);
	}

	.frame > * {
		position: absolute;
		inset: 0;
	}

	.picture {
		width: 100%;
		height: 100%;
		object-fit: cover;
		transition: filter var(--motion-imagegen-progress);
	}

	.placeholder {
		opacity: 0;
		background: linear-gradient(
			100deg,
			var(--surface-raised) 30%,
			var(--skeleton-highlight) 50%,
			var(--surface-raised) 70%
		);
		background-size: 300% 100%;
		animation: sweep var(--motion-skeleton-sweep) infinite;
	}

	[data-state='queued'] .placeholder {
		opacity: 1;
	}

	[data-state='queued'] .picture {
		opacity: 0;
	}

	[data-state='generating'] .picture {
		filter: blur(calc((1 - var(--progress)) * 26px)) saturate(calc(0.25 + var(--progress) * 0.75));
	}

	[data-state='done'] .picture {
		animation: unblur var(--motion-imagegen-reveal);
	}

	[data-state='failed'] .picture {
		opacity: 0.3;
		filter: grayscale(1) blur(10px);
	}

	.queue {
		display: grid;
		place-items: center;
	}

	.failure {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 6px;
		padding: 16px;
		background: var(--surface);
		color: var(--text-muted);
		font-size: 12.5px;
		text-align: center;
		animation: fade var(--motion-imagegen-error);
	}

	.failure :global(.icon) {
		color: var(--danger);
	}

	.failure b {
		color: var(--text);
		font-size: 13.5px;
		font-weight: 600;
	}

	figcaption {
		display: flex;
		justify-content: space-between;
		gap: 12px;
		color: var(--text-faint);
		font: 10.5px var(--font-mono);
	}

	.prompt {
		min-width: 0;
		overflow: hidden;
		font-family: var(--font-body);
		font-size: 12.5px;
		font-style: italic;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.step {
		flex: none;
		font-variant-numeric: tabular-nums;
	}

	@keyframes sweep {
		from {
			background-position: 200% 0;
		}
		to {
			background-position: -100% 0;
		}
	}

	@keyframes unblur {
		from {
			filter: blur(16px);
			opacity: 0.4;
		}
	}

	@keyframes fade {
		from {
			opacity: 0;
		}
	}
</style>
