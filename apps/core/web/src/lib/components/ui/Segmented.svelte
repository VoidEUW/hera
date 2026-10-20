<script lang="ts" generics="T extends string">
	/**
	 * Two to four mutually exclusive choices with a thumb that slides between them (the theme's
	 * `hera/segmented`): appearance in Settings, Preview / Source in the side view.
	 *
	 * A radio group underneath, so arrow keys move the choice and a screen reader hears "2 of 3".
	 * The thumb is one element translated to the chosen segment rather than a background on the
	 * chosen button, so changing it reads as one thing moving (`indicator.move`) instead of one
	 * thing going out and another coming on.
	 */
	import type { IconName } from '$lib/icons';
	import Icon from './Icon.svelte';

	interface Option {
		value: T;
		label: string;
		icon?: IconName;
	}

	interface Props {
		options: Option[];
		value: T;
		/** The group's accessible name. */
		label: string;
		size?: 'sm' | 'md';
		onchange?: (value: T) => void;
	}

	let { options, value = $bindable(), label, size = 'md', onchange }: Props = $props();

	const index = $derived(
		Math.max(
			0,
			options.findIndex((option) => option.value === value)
		)
	);
	let buttons: HTMLButtonElement[] = $state([]);

	function choose(next: T) {
		value = next;
		onchange?.(next);
	}

	function walk(event: KeyboardEvent) {
		const step =
			event.key === 'ArrowRight' || event.key === 'ArrowDown'
				? 1
				: event.key === 'ArrowLeft' || event.key === 'ArrowUp'
					? -1
					: 0;
		if (!step) return;
		event.preventDefault();
		const next = (index + step + options.length) % options.length;
		choose(options[next].value);
		buttons[next]?.focus();
	}
</script>

<div
	class="segmented {size}"
	role="radiogroup"
	aria-label={label}
	tabindex="-1"
	onkeydown={walk}
	style:--count={options.length}
	style:--index={index}
>
	<span class="thumb" aria-hidden="true"></span>
	{#each options as option, position (option.value)}
		<button
			bind:this={buttons[position]}
			type="button"
			role="radio"
			aria-checked={option.value === value}
			tabindex={option.value === value ? 0 : -1}
			class:on={option.value === value}
			onclick={() => choose(option.value)}
		>
			{#if option.icon}<Icon name={option.icon} />{/if}
			{option.label}
		</button>
	{/each}
</div>

<style>
	.segmented {
		--pad: 3px;
		position: relative;
		display: inline-grid;
		grid-template-columns: repeat(var(--count), minmax(0, 1fr));
		padding: var(--pad);
		border: var(--border-width) solid var(--line);
		border-radius: var(--chip-radius);
		background: var(--ground);
	}

	.thumb {
		position: absolute;
		top: var(--pad);
		bottom: var(--pad);
		left: var(--pad);
		width: calc((100% - 2 * var(--pad)) / var(--count));
		border-radius: var(--chip-radius);
		background: var(--surface-raised);
		box-shadow: var(--shadow-sm);
		transform: translateX(calc(100% * var(--index)));
		transition: transform var(--motion-indicator-move);
	}

	button {
		position: relative;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: calc(var(--space) * 1.5);
		height: calc(var(--space) * 7.5);
		padding: 0 calc(var(--space) * 4);
		border-radius: var(--chip-radius);
		color: var(--text-muted);
		font-size: var(--ui-size);
		white-space: nowrap;
		transition: color var(--fade) var(--ease);
	}

	.sm button {
		height: calc(var(--space) * 6);
		padding: 0 calc(var(--space) * 3);
		font-size: calc(var(--ui-size) - 1px);
	}

	button:hover,
	button.on {
		color: var(--text);
	}
</style>
