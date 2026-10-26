<script lang="ts" module>
	export interface Series {
		label: string;
		/** `quiet` for the series that is context, `live` for the one being read. */
		tone: 'quiet' | 'live';
		/** A longer name, shown as the legend entry's tooltip. */
		hint?: string;
	}

	export interface Bar {
		/** What the bar is — a date — for the readout and the axis. */
		label: string;
		/** One value per series, stacked from the bottom in series order. */
		values: number[];
	}
</script>

<script lang="ts">
	/**
	 * Stacked bars, one per slot, drawn in inline SVG from the theme's tokens (Hera amendment
	 * `hera/bar-chart`, #111). No chart library: a column of rectangles is a few lines, and a
	 * library would bring a second visual language along with it.
	 *
	 * **One bar is always the one being read.** Pointing at a column or moving with the arrow
	 * keys chooses it, and its numbers are written in the readout above the chart — a line of
	 * text rather than a tooltip, so it is read out as it changes and never covers the bars
	 * beside it. Before anybody points, it is the last bar: the newest is what a person came for.
	 *
	 * The chart is a `slider` over the bars to assistive technology, since that is what it is
	 * to the keyboard; `aria-valuetext` is the readout.
	 */
	import { tooltip } from '$lib/tooltip';

	interface Props {
		bars: Bar[];
		series: Series[];
		/** The chart's accessible name. */
		label: string;
		/** The readout for one bar. */
		describe: (bar: Bar) => string;
		/** Under the first and the last bar. */
		ends?: [string, string];
	}

	let { bars, series, label, describe, ends }: Props = $props();

	/** Viewbox units per slot, and how much of it a bar takes. Stretched to the width the chart
	 * is given (`preserveAspectRatio="none"`), which is why nothing in here is text. */
	const SLOT = 10;
	const BAR = 7;
	const HEIGHT = 100;

	let chosen = $state<number | null>(null);
	const current = $derived(
		bars.length ? Math.min(chosen ?? bars.length - 1, bars.length - 1) : null
	);
	const peak = $derived(
		Math.max(0, ...bars.map((bar) => bar.values.reduce((sum, value) => sum + value, 0)))
	);
	const readout = $derived(current === null ? '' : describe(bars[current]));

	/** Each series' rectangle in one bar, bottom up. */
	function stack(bar: Bar): Array<{ y: number; height: number; tone: Series['tone'] }> {
		if (peak <= 0) return [];
		let top = HEIGHT;
		return bar.values.map((value, index) => {
			const height = (value / peak) * HEIGHT;
			top -= height;
			return { y: top, height, tone: series[index]?.tone ?? 'quiet' };
		});
	}

	function point(event: PointerEvent) {
		const box = (event.currentTarget as HTMLElement).getBoundingClientRect();
		if (!bars.length || box.width <= 0) return;
		const index = Math.floor(((event.clientX - box.left) / box.width) * bars.length);
		chosen = Math.max(0, Math.min(bars.length - 1, index));
	}

	function key(event: KeyboardEvent) {
		if (current === null) return;
		const next =
			event.key === 'ArrowLeft' || event.key === 'ArrowDown'
				? current - 1
				: event.key === 'ArrowRight' || event.key === 'ArrowUp'
					? current + 1
					: event.key === 'Home'
						? 0
						: event.key === 'End'
							? bars.length - 1
							: null;
		if (next === null) return;
		event.preventDefault();
		chosen = Math.max(0, Math.min(bars.length - 1, next));
	}
</script>

<figure class="chart">
	<figcaption>
		<span class="readout" aria-hidden="true">{readout}</span>
		<span class="legend">
			{#each series as entry (entry.label)}
				<span class="key" use:tooltip={entry.hint}>
					<span class="swatch {entry.tone}"></span>{entry.label}
				</span>
			{/each}
		</span>
	</figcaption>

	<div
		class="plot"
		role="slider"
		tabindex="0"
		aria-label={label}
		aria-valuemin={1}
		aria-valuemax={Math.max(1, bars.length)}
		aria-valuenow={(current ?? 0) + 1}
		aria-valuetext={readout}
		onpointermove={point}
		onpointerdown={point}
		onkeydown={key}
	>
		<svg
			viewBox="0 0 {Math.max(1, bars.length) * SLOT} {HEIGHT}"
			preserveAspectRatio="none"
			aria-hidden="true"
		>
			{#if current !== null}
				<rect class="focus" x={current * SLOT} y="0" width={SLOT} height={HEIGHT} />
			{/if}
			{#each bars as bar, index (index)}
				{#each stack(bar) as part, layer (layer)}
					<rect
						class={part.tone}
						x={index * SLOT + (SLOT - BAR) / 2}
						y={part.y}
						width={BAR}
						height={part.height}
					/>
				{/each}
			{/each}
		</svg>
	</div>

	{#if ends}
		<div class="ends" aria-hidden="true"><span>{ends[0]}</span><span>{ends[1]}</span></div>
	{/if}
</figure>

<style>
	.chart {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin: 0;
	}

	figcaption {
		display: flex;
		align-items: baseline;
		gap: 12px;
		min-height: 1.4em;
		font-size: 12.5px;
	}

	.readout {
		color: var(--text);
		font-variant-numeric: tabular-nums;
	}

	.legend {
		display: flex;
		gap: 12px;
		margin-left: auto;
		color: var(--text-muted);
	}

	.key {
		display: inline-flex;
		align-items: center;
		gap: 6px;
	}

	.swatch {
		width: 9px;
		height: 9px;
		border-radius: var(--radius-sm);
	}

	.swatch.quiet {
		background: var(--text-faint);
	}

	.swatch.live {
		background: var(--laurel);
	}

	.plot {
		height: calc(var(--space) * 40);
		border-bottom: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		cursor: crosshair;
	}

	.plot:focus-visible {
		outline: var(--focus-width) solid var(--laurel);
		outline-offset: 2px;
	}

	svg {
		display: block;
		width: 100%;
		height: 100%;
	}

	rect.focus {
		fill: var(--hover);
	}

	rect.quiet {
		fill: var(--text-faint);
	}

	rect.live {
		fill: var(--laurel);
	}

	.ends {
		display: flex;
		justify-content: space-between;
		color: var(--text-faint);
		font-size: 11.5px;
	}
</style>
