<script lang="ts">
	/**
	 * Waiting on something that has no number to show (the theme's `hera/spinner`). Always
	 * `--laurel`, because waiting is live state.
	 *
	 * `stalled` is what it becomes when nothing has arrived for a while: `--danger`, breathing
	 * (`spinner.stall`), with the label saying so — a spinner that keeps turning at the same
	 * speed whether the answer is a second away or never coming is not telling anybody anything.
	 * The caller decides when that is, because only it knows how long is too long.
	 */
	import { t } from '$lib/i18n';

	interface Props {
		size?: 14 | 20 | 28;
		/** Shown beside the circle. Omit for a spinner that is only a picture of waiting. */
		label?: string;
		stalled?: boolean;
	}

	let { size = 20, label, stalled = false }: Props = $props();
</script>

<span class="spinner" class:stalled role="status" style:--diameter="{size}px">
	<svg class="circle" viewBox="0 0 24 24" aria-hidden="true">
		<circle class="track" cx="12" cy="12" r="9" />
		<circle class="arc" cx="12" cy="12" r="9" />
	</svg>
	{#if label || stalled}
		<span class="label">{stalled ? t.ui.notResponding : label}</span>
	{:else}
		<span class="sr-only">{t.ui.loading}</span>
	{/if}
</span>

<style>
	.spinner {
		display: inline-flex;
		align-items: center;
		gap: calc(var(--space) * 2);
		color: var(--laurel);
	}

	.circle {
		width: var(--diameter);
		height: var(--diameter);
		fill: none;
		stroke-width: 2.4;
		stroke-linecap: round;
		animation: turn var(--motion-spinner-loop) infinite;
	}

	.track {
		stroke: var(--line);
	}

	/* `spinner.loop` is "material": one arc that grows and shrinks while it turns. */
	.arc {
		stroke: currentColor;
		stroke-dasharray: 1 57;
		stroke-dashoffset: 0;
		animation: grow var(--motion-spinner-loop) infinite;
	}

	.label {
		color: var(--text-muted);
		font-size: var(--ui-size);
	}

	.stalled {
		color: var(--danger);
	}

	.stalled .circle {
		animation:
			turn var(--motion-spinner-loop) infinite,
			breathe var(--motion-spinner-stall) infinite alternate;
	}

	@keyframes turn {
		to {
			transform: rotate(360deg);
		}
	}

	@keyframes grow {
		0% {
			stroke-dasharray: 1 57;
			stroke-dashoffset: 0;
		}
		50% {
			stroke-dasharray: 34 57;
			stroke-dashoffset: -8;
		}
		100% {
			stroke-dasharray: 1 57;
			stroke-dashoffset: -56;
		}
	}

	@keyframes breathe {
		to {
			opacity: 0.45;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.arc {
			stroke-dasharray: 20 57;
		}
	}
</style>
