<script lang="ts">
	/**
	 * Waiting on something that has no number to show (the theme's `hera/spinner`). Always
	 * `--laurel`, because waiting is live state.
	 *
	 * `spinner.loop` is "material": one arc with no track, growing and shrinking on the loop's
	 * curve while the whole circle turns, linearly, once every 1.7 loops — the two never line up,
	 * which is what keeps it from reading as a ticking clock. No accent layer (`spinner.accent:
	 * none`); the label is plain muted text (`spinner.label: plain`).
	 *
	 * `stalled` is what it becomes when nothing has arrived for a while (`hera/spinner-stalled`):
	 * the whole spinner turns `--danger` and breathes (`spinner.stall`). The caller decides when
	 * that is, because only it knows how long is too long — see `StallBox`.
	 */
	import { t } from '$lib/i18n';

	interface Props {
		size?: 14 | 16 | 20 | 22 | 28;
		/** Shown beside the circle. Omit for a spinner that is only a picture of waiting. */
		label?: string;
		stalled?: boolean;
	}

	let { size = 20, label, stalled = false }: Props = $props();
</script>

<span class="loader" role="status">
	<span class="spinner" class:stalled style:--diameter="{size}px">
		<svg viewBox="-12 -12 24 24" aria-hidden="true"><circle class="arc" r="9" /></svg>
	</span>
	{#if label}
		<span class="label">{label}</span>
	{:else}
		<span class="sr-only">{stalled ? t.ui.notResponding : t.ui.loading}</span>
	{/if}
</span>

<style>
	.loader {
		display: inline-flex;
		align-items: center;
		gap: 10px;
	}

	.spinner {
		display: inline-grid;
		flex: none;
		place-items: center;
		width: var(--diameter);
		height: var(--diameter);
		color: var(--laurel);
	}

	svg {
		width: 100%;
		height: 100%;
		overflow: visible;
		animation: turn calc(var(--motion-spinner-loop-d) * 1.7) linear infinite;
	}

	.arc {
		fill: none;
		stroke: currentColor;
		stroke-width: 2.6;
		stroke-linecap: round;
		stroke-dasharray: 1 60;
		animation: dash var(--motion-spinner-loop) infinite;
	}

	.stalled {
		color: var(--danger);
		animation: breathe var(--motion-spinner-stall) infinite;
	}

	.label {
		color: var(--text-muted);
		font-size: 13px;
		white-space: nowrap;
	}

	@keyframes turn {
		to {
			transform: rotate(360deg);
		}
	}

	@keyframes dash {
		0% {
			stroke-dasharray: 1 60;
			stroke-dashoffset: 0;
		}
		50% {
			stroke-dasharray: 34 60;
			stroke-dashoffset: -8;
		}
		100% {
			stroke-dasharray: 34 60;
			stroke-dashoffset: -56;
		}
	}

	@keyframes breathe {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.45;
		}
	}

	/* Still, it is a quarter arc: enough to read as "waiting", not a full ring. */
	@media (prefers-reduced-motion: reduce) {
		svg,
		.arc,
		.stalled {
			animation: none;
		}

		.arc {
			stroke-dasharray: 20 60;
		}
	}
</style>
