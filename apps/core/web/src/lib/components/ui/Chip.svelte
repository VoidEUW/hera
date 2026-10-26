<script lang="ts">
	/**
	 * A fully rounded pill-shaped control (the theme's `hera/chips`, `.chip`): the composer's
	 * skills and servers, the model and artifact selectors in a toolbar. On is a brass hairline
	 * and a brass dot — what is switched on for the next message is authority she has been given.
	 *
	 * The leading mark is a dot (a toggle, on or off) or an icon (a selector); a selector chip
	 * ends in a chevron that turns while its menu is open. `pressed` is set only when the chip is
	 * itself the switch; a chip that opens a menu says so with `haspopup` and `expanded`.
	 *
	 * **On a phone a chip can go short** (#41). A toolbar of full labels does not fit 390px, and
	 * every chip squeezing its own label to an ellipsis left four chips nobody could read. `short`
	 * is what the chip says below the breakpoint instead — a count, or nothing — and `shortIcon`
	 * stands in for the dot there, so a chip that is a dot on the desktop is a picture on the
	 * phone. The full label is still in the button, hidden only from the eye, so its name does not
	 * change with the width. Without `short` a chip is the same at every width.
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
		/** What the chip says below the phone breakpoint. `''` is the icon alone. */
		short?: string;
		/** The mark below the phone breakpoint, in place of the dot. */
		shortIcon?: IconName;
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
		short,
		shortIcon,
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
	class:compact={short !== undefined}
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
	{#if showDot}<span class="dot" class:long={!!shortIcon} aria-hidden="true"></span>{/if}
	{#if shortIcon}
		<span class="short mark" aria-hidden="true"
			><Icon name={shortIcon} size="calc(var(--icon-size) - 2px)" /></span
		>
	{/if}
	{#if image}
		<img class="image" src={image} alt="" />
	{:else if icon}
		<Icon name={icon} size="calc(var(--icon-size) - 2px)" />
	{/if}
	{#if short === undefined}
		<span class="text">{@render children()}</span>
	{:else}
		<span class="text long">{@render children()}</span>
		{#if short}<span class="text short" aria-hidden="true">{short}</span>{/if}
	{/if}
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

	.short {
		display: none;
	}

	.mark {
		color: var(--text-faint);
	}

	.on .mark {
		color: var(--brass);
	}

	/* Below the breakpoint the short form is the visible one. The long label is hidden from the
	   eye only, the usual visually-hidden recipe, so it is still the button's name. */
	@media (max-width: 780px) {
		.short {
			display: inline-flex;
		}

		/* A short chip is already as small as it gets, so it does not shrink further: in a full
		   toolbar every chip used to give up room, and a count or an icon was cut off. The one that
		   gives way is the one with a name to shorten, the model's. */
		.compact {
			flex: none;
		}

		.long {
			position: absolute;
			width: 1px;
			height: 1px;
			overflow: hidden;
			clip-path: inset(50%);
			white-space: nowrap;
		}

		.dot.long {
			display: none;
		}
	}
</style>
