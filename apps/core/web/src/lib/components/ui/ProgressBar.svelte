<script lang="ts">
	/**
	 * How far along or how full something is (the theme's `hera/progress-bar`, soft look): a 4px
	 * rounded bar, 6px `thick`. Determinate when there is a number — an upload, a download, how
	 * much of the memory budget is spent — and indeterminate when there is not, which sweeps a soft
	 * laurel highlight across the track rather than pretending to a value (`bar.indeterminate`).
	 *
	 * `meter` is for a quantity rather than a task — space used, not work done — and `tone="danger"`
	 * is a quantity that has gone past where it should be.
	 */
	interface Props {
		/** 0 to `max`. Omit for indeterminate. */
		value?: number;
		/** What `value` is out of. A meter of tokens says so, so a screen reader hears the real
		 * numbers rather than a percentage. */
		max?: number;
		/** The accessible name: what is progressing, or what is being measured. */
		label: string;
		thick?: boolean;
		meter?: boolean;
		tone?: 'live' | 'danger';
		/** For a meter: the reading a screen reader hears, "3 200 of 4 000 tokens". */
		valuetext?: string;
	}

	let {
		value,
		max = 1,
		label,
		thick = false,
		meter = false,
		tone = 'live',
		valuetext
	}: Props = $props();

	const clamped = $derived(
		value === undefined || max <= 0 ? undefined : Math.min(1, Math.max(0, value / max))
	);
	/** Percent for a plain share, the real numbers when the caller gave a `max`. */
	const scale = $derived(max === 1 ? 100 : max);
</script>

<div
	class="bar {tone}"
	class:thick
	class:indeterminate={clamped === undefined}
	role={meter ? 'meter' : 'progressbar'}
	aria-label={label}
	aria-valuemin={0}
	aria-valuemax={scale}
	aria-valuenow={clamped === undefined ? undefined : Math.round(clamped * scale)}
	aria-valuetext={valuetext}
	style:--value={clamped ?? 0}
>
	<i></i>
</div>

<style>
	.bar {
		position: relative;
		width: 100%;
		height: 4px;
		overflow: hidden;
		border-radius: var(--chip-radius);
		background: var(--surface-raised);
	}

	.thick {
		height: 6px;
	}

	i {
		position: absolute;
		inset: 0 auto 0 0;
		width: calc(var(--value) * 100%);
		border-radius: inherit;
		background: var(--laurel);
		transition:
			width var(--motion-bar-indeterminate),
			background-color var(--motion-bar-indeterminate);
	}

	.danger i {
		background: var(--danger);
	}

	.indeterminate i {
		width: 100%;
		background: linear-gradient(90deg, transparent 0%, var(--laurel) 50%, transparent 100%)
			no-repeat;
		background-size: 50% 100%;
		animation: shine var(--motion-bar-indeterminate) infinite;
	}

	@keyframes shine {
		from {
			background-position: 150% 0;
		}
		to {
			background-position: -50% 0;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.indeterminate i {
			animation: none;
			background-position: 50% 0;
		}
	}
</style>
