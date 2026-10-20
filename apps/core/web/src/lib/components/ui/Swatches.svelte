<script lang="ts">
	/**
	 * A choice of colour (a Hera addition to the theme, `hera/swatches`): a row of round swatches,
	 * the chosen one ringed in `--text` — not brass, because picking a project's colour grants her
	 * nothing. A radio group, so arrow keys move the choice.
	 */
	interface Swatch {
		value: string;
		/** Any CSS colour expression — a token, or a mix of one. */
		colour: string;
		label: string;
	}

	interface Props {
		swatches: Swatch[];
		value: string;
		label: string;
		onchange: (value: string) => void;
	}

	let { swatches, value, label, onchange }: Props = $props();
	let buttons: HTMLButtonElement[] = $state([]);

	function walk(event: KeyboardEvent) {
		const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
		if (!step) return;
		event.preventDefault();
		const here = swatches.findIndex((swatch) => swatch.value === value);
		const next = (here + step + swatches.length) % swatches.length;
		onchange(swatches[next].value);
		buttons[next]?.focus();
	}
</script>

<div class="swatches" role="radiogroup" aria-label={label} tabindex="-1" onkeydown={walk}>
	{#each swatches as swatch, index (swatch.value)}
		<button
			bind:this={buttons[index]}
			type="button"
			role="radio"
			class="swatch"
			class:chosen={swatch.value === value}
			aria-checked={swatch.value === value}
			aria-label={swatch.label}
			tabindex={swatch.value === value ? 0 : -1}
			style:--swatch={swatch.colour}
			onclick={() => onchange(swatch.value)}
		></button>
	{/each}
</div>

<style>
	.swatches {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.swatch {
		width: 22px;
		height: 22px;
		border-radius: 50%;
		background: var(--swatch);
		transition:
			transform var(--motion-button-hover),
			box-shadow var(--motion-button-hover);
	}

	.swatch:hover {
		transform: translateY(-1px);
	}

	.chosen {
		box-shadow:
			0 0 0 2px var(--ground),
			0 0 0 4px var(--text);
	}
</style>
