<script lang="ts">
	/**
	 * A fully rounded pill-shaped control (the theme's `hera/chips`, `.chip`): the composer's
	 * skills and servers, the model and artifact selectors in a toolbar. On is a brass hairline
	 * and a brass dot — what is switched on for the next message is authority she has been given.
	 *
	 * The leading mark is a dot (a toggle, on or off) or an icon (a selector); a selector chip
	 * ends in a chevron that turns while its menu is open. `pressed` is set only when the chip is
	 * itself the switch; a chip that opens a menu says so with `haspopup` and `expanded`.
	 */
	import type { Snippet } from 'svelte';
	import type { IconName } from '$lib/icons';
	import Icon from './Icon.svelte';
	import { tooltip } from '$lib/tooltip';

	interface Props {
		on?: boolean;
		/** A leading dot. Off when there is an icon. */
		dot?: boolean;
		icon?: IconName;
		/** A small picture instead of an icon — a provider's logo. */
		image?: string;
		chevron?: boolean;
		pressed?: boolean;
		expanded?: boolean;
		haspopup?: 'menu' | 'dialog';
		disabled?: boolean;
		/** A tooltip, for when the label alone is a name you would have to already know. */
		hint?: string;
		label?: string;
		ref?: HTMLButtonElement | null;
		onclick?: (event: MouseEvent) => void;
		onkeydown?: (event: KeyboardEvent) => void;
		children: Snippet;
	}

	let {
		on = false,
		dot,
		icon,
		image,
		chevron = false,
		pressed,
		expanded,
		haspopup,
		disabled = false,
		hint,
		label,
		ref = $bindable(),
		onclick,
		onkeydown,
		children
	}: Props = $props();

	const showDot = $derived(dot ?? (!icon && !image));
</script>

<button
	bind:this={ref}
	class="chip"
	class:on
	class:open={expanded}
	type="button"
	aria-pressed={pressed}
	aria-expanded={expanded}
	aria-haspopup={haspopup}
	aria-label={label}
	{disabled}
	use:tooltip={hint}
	{onclick}
	{onkeydown}
>
	{#if showDot}<span class="dot" aria-hidden="true"></span>{/if}
	{#if image}
		<img class="image" src={image} alt="" />
	{:else if icon}
		<Icon name={icon} size="calc(var(--icon-size) - 2px)" />
	{/if}
	<span class="text">{@render children()}</span>
	{#if chevron}<span class="chevron"><Icon name="chevD" size="calc(var(--icon-size) - 2px)" /></span
		>{/if}
</button>

<style>
	.chip {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
		height: calc(var(--space) * 7);
		padding: 0 10px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--chip-radius);
		color: var(--text-muted);
		font-size: 12px;
		white-space: nowrap;
		transition:
			transform var(--motion-button-hover),
			box-shadow var(--motion-button-hover),
			background-color var(--motion-button-hover),
			color var(--motion-button-hover),
			border-color var(--motion-button-hover);
	}

	/* `button.hover` and `button.press`: every button, icon button and chip lifts and sinks. */
	.chip:hover:not(:disabled) {
		transform: translateY(-1px);
		box-shadow: var(--shadow-sm);
		color: var(--text);
	}

	.chip:active:not(:disabled) {
		transform: translateY(1px);
		box-shadow: none;
		transition:
			transform var(--motion-button-press),
			box-shadow var(--motion-button-press);
	}

	.chip:disabled {
		color: var(--text-faint);
		cursor: not-allowed;
	}

	.dot {
		flex: none;
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: var(--text-faint);
	}

	.image {
		width: calc(var(--icon-size) - 2px);
		height: calc(var(--icon-size) - 2px);
		object-fit: contain;
	}

	.text {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.chevron {
		display: inline-flex;
		color: var(--text-faint);
		transition: transform var(--motion-menu-enter);
	}

	.open .chevron {
		transform: rotate(180deg);
	}

	.on,
	.open {
		color: var(--text);
	}

	.on {
		border-color: var(--brass-line);
	}

	.on .dot {
		background: var(--brass);
	}
</style>
