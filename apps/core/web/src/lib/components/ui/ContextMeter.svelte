<script lang="ts" module>
	/** 12 400 → "12.4k", 32 768 → "33k", 1 048 576 → "1M": a count read at a glance. */
	export function compact(n: number): string {
		if (n < 1000) return String(Math.round(n));
		if (n < 10_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, '')}k`;
		if (n < 1_000_000) return `${Math.round(n / 1000)}k`;
		return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, '')}M`;
	}
</script>

<script lang="ts">
	/**
	 * How full the conversation's context window is (a Hera addition to the theme,
	 * `hera/context-meter`): a 16px ring filled to the share used, and the two numbers beside it in
	 * the mono face. It lives in the top bar's toolbar, because it describes the chat, not the
	 * message being typed.
	 *
	 * One arc over a `--line` track — the same circle drawn twice, never two circles, so it is not
	 * mistaken for the ocellus. Laurel, because a filling window is live state; `--danger` past 85%,
	 * where the next long answer may not fit. The exact count is the tooltip and the meter's value
	 * text.
	 */
	import { t } from '$lib/i18n';
	import { tooltip } from '$lib/tooltip';

	interface Props {
		used: number;
		limit: number;
	}

	let { used, limit }: Props = $props();

	const RADIUS = 6.5;
	const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
	const share = $derived(limit > 0 ? Math.min(1, Math.max(0, used / limit)) : 0);
	const tight = $derived(share > 0.85);
	const exact = $derived(t.composer.contextUsed(used, limit));
</script>

<div
	class="meter"
	class:tight
	role="meter"
	aria-label={t.composer.contextLabel}
	aria-valuemin={0}
	aria-valuemax={limit}
	aria-valuenow={Math.min(used, limit)}
	aria-valuetext={exact}
	use:tooltip={exact}
>
	<svg viewBox="0 0 16 16" aria-hidden="true">
		<circle class="track" cx="8" cy="8" r={RADIUS} />
		<circle
			class="arc"
			cx="8"
			cy="8"
			r={RADIUS}
			stroke-dasharray="{share * CIRCUMFERENCE} {CIRCUMFERENCE}"
		/>
	</svg>
	<span class="numbers">{compact(used)} / {compact(limit)}</span>
</div>

<style>
	.meter {
		display: inline-flex;
		flex: none;
		align-items: center;
		gap: 6px;
		height: calc(var(--space) * 7);
		padding: 0 6px;
		border-radius: var(--radius-sm);
		color: var(--laurel);
	}

	.tight {
		color: var(--danger);
	}

	svg {
		width: 16px;
		height: 16px;
		transform: rotate(-90deg);
	}

	circle {
		fill: none;
		stroke-width: 2;
	}

	.track {
		stroke: var(--line);
	}

	.arc {
		stroke: currentColor;
		stroke-linecap: round;
		transition: stroke-dasharray var(--motion-bar-indeterminate);
	}

	.numbers {
		color: var(--text-muted);
		font: 11px var(--font-mono);
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	.tight .numbers {
		color: var(--danger);
	}
</style>
