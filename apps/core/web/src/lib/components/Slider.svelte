<script lang="ts">
	/**
	 * One slider, drawn by us (#99).
	 *
	 * The native range input carried the OS's own groove and knob — thin, grey, and matching
	 * nothing else in the interface, the same gap `Checkbox.svelte` and `Select.svelte` closed
	 * for their controls. This draws the track: a hairline groove, a brass fill from the low end
	 * to the thumb, and a thumb that grows on hover the way a button does.
	 *
	 * The input stays a real `<input type="range">` underneath — only its track and thumb are
	 * replaced via the browser's own styling hooks, so arrow keys, Home/End and screen readers
	 * keep working exactly as they did.
	 */

	interface Props {
		value: number;
		min: number;
		max: number;
		step?: number;
		/** The accessible name — every sampling slider sits beside its own visible label already,
		 * so this is what a screen reader announces instead of a second, redundant one. */
		ariaLabel?: string;
		disabled?: boolean;
		onchange?: (value: number) => void;
	}

	let { value, min, max, step = 1, ariaLabel = '', disabled = false, onchange }: Props = $props();

	// Where the thumb sits, as a percentage of the track — Blink reads it back out of this same
	// custom property to stop its fill gradient at the right point (`::-webkit-slider-runnable-
	// track` below), so the two can never disagree about where the value is.
	const pct = $derived(
		max > min ? ((Math.min(Math.max(value, min), max) - min) / (max - min)) * 100 : 0
	);

	function handle(event: Event) {
		onchange?.(Number((event.currentTarget as HTMLInputElement).value));
	}
</script>

<input
	class="slider"
	type="range"
	{min}
	{max}
	{step}
	{value}
	{disabled}
	aria-label={ariaLabel || undefined}
	style:--fill="{pct}%"
	oninput={handle}
/>

<style>
	.slider {
		--track: 4px;
		--thumb: 14px;
		width: 100%;
		margin: 0;
		background: none;
		appearance: none;
		cursor: pointer;
	}

	.slider:disabled {
		cursor: default;
		opacity: 0.4;
	}

	.slider:focus-visible {
		outline: none;
	}

	/* Blink/WebKit: the track is one pseudo-element, and the fill is a gradient stopped at
	   `--fill` rather than a second layered element — there is no `::-webkit-range-progress`. */
	.slider::-webkit-slider-runnable-track {
		height: var(--track);
		border-radius: 999px;
		background: linear-gradient(to right, var(--brass) var(--fill), var(--line) var(--fill));
	}

	.slider::-webkit-slider-thumb {
		appearance: none;
		width: var(--thumb);
		height: var(--thumb);
		margin-top: calc((var(--track) - var(--thumb)) / 2);
		border-radius: 50%;
		background: var(--brass);
		border: 2px solid var(--ground);
		box-shadow: 0 0 0 1px var(--brass);
		transition: transform var(--fade) var(--ease);
	}

	.slider:not(:disabled):hover::-webkit-slider-thumb {
		transform: scale(1.15);
	}

	.slider:not(:disabled):active::-webkit-slider-thumb {
		transform: scale(0.95);
	}

	.slider:focus-visible::-webkit-slider-thumb {
		box-shadow:
			0 0 0 1px var(--brass),
			0 0 0 4px rgb(217 174 82 / 0.25);
	}

	/* Firefox: `-moz-range-progress` is a real pseudo-element here, so the fill needs no gradient
	   trick — it is drawn brass up to the thumb and the track stays `--line` underneath it. */
	.slider::-moz-range-track {
		height: var(--track);
		border-radius: 999px;
		background: var(--line);
	}

	.slider::-moz-range-progress {
		height: var(--track);
		border-radius: 999px;
		background: var(--brass);
	}

	.slider::-moz-range-thumb {
		width: var(--thumb);
		height: var(--thumb);
		border-radius: 50%;
		background: var(--brass);
		border: 2px solid var(--ground);
		box-shadow: 0 0 0 1px var(--brass);
		transition: transform var(--fade) var(--ease);
	}

	.slider:not(:disabled):hover::-moz-range-thumb {
		transform: scale(1.15);
	}

	.slider:not(:disabled):active::-moz-range-thumb {
		transform: scale(0.95);
	}

	.slider:focus-visible::-moz-range-thumb {
		box-shadow:
			0 0 0 1px var(--brass),
			0 0 0 4px rgb(217 174 82 / 0.25);
	}
</style>
