<script lang="ts">
	/**
	 * How far along something is (the theme's `hera/progress-bar`): determinate when there is a
	 * number — an upload, a download — and indeterminate when there is not, which shimmers rather
	 * than pretending to a value (`bar.indeterminate`).
	 */
	interface Props {
		/** 0 to 1. Omit for indeterminate. */
		value?: number;
		/** The accessible name: what is progressing. */
		label: string;
		thick?: boolean;
	}

	let { value, label, thick = false }: Props = $props();

	const clamped = $derived(value === undefined ? undefined : Math.min(1, Math.max(0, value)));
</script>

<div
	class="bar"
	class:thick
	class:indeterminate={clamped === undefined}
	role="progressbar"
	aria-label={label}
	aria-valuemin={0}
	aria-valuemax={100}
	aria-valuenow={clamped === undefined ? undefined : Math.round(clamped * 100)}
	style:--value={clamped ?? 0}
>
	<span class="fill"></span>
</div>

<style>
	.bar {
		position: relative;
		height: 4px;
		overflow: hidden;
		border-radius: var(--chip-radius);
		background: var(--surface-raised);
	}

	.thick {
		height: 8px;
	}

	.fill {
		position: absolute;
		inset: 0 auto 0 0;
		width: calc(var(--value) * 100%);
		border-radius: inherit;
		background: var(--laurel);
		transition: width var(--disclose) var(--ease);
	}

	.indeterminate .fill {
		width: 40%;
		background: linear-gradient(90deg, transparent, var(--laurel), transparent);
		animation: shimmer var(--motion-bar-indeterminate) infinite;
	}

	@keyframes shimmer {
		from {
			transform: translateX(-100%);
		}
		to {
			transform: translateX(250%);
		}
	}
</style>
