<script lang="ts">
	/**
	 * One button, six meanings (ADR 21, the theme's `hera/button`).
	 *
	 * The variant is what the button *says*, never how loud someone wanted it to be:
	 *
	 *   neutral      most things
	 *   highlighted  the one action a screen leads with — brass, her authority
	 *   signature    only where the action is her — pomegranate, the send button's colour
	 *   danger       a destructive action, once it has been confirmed
	 *   danger-soft  the destructive action before it is confirmed, or beside quieter ones
	 *   ghost        low emphasis: Cancel, a secondary verb in a row
	 *
	 * Grayed out is `disabled`, not a variant: whether a button can be pressed is a fact about
	 * the moment, and the variant still says what it would do.
	 *
	 * An icon-only button takes `label`, which becomes its accessible name and its title. A link
	 * that navigates is an `<a>`, not this: acting and going somewhere are different elements to
	 * a screen reader even when they look the same.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import type { IconName } from '$lib/icons';
	import Icon from './Icon.svelte';

	type Variant = 'neutral' | 'highlighted' | 'signature' | 'danger' | 'danger-soft' | 'ghost';

	interface Props extends Omit<HTMLButtonAttributes, 'children'> {
		variant?: Variant;
		size?: 'sm' | 'md' | 'lg';
		/** A leading icon, or the whole button when there are no children. */
		icon?: IconName;
		/** The accessible name of an icon-only button. Required when there are no children. */
		label?: string;
		children?: Snippet;
	}

	let {
		variant = 'neutral',
		size = 'md',
		icon,
		label,
		type = 'button',
		children,
		...rest
	}: Props = $props();

	const iconOnly = $derived(!children && Boolean(icon));
</script>

{#snippet content()}
	{#if icon}<Icon name={icon} />{/if}
	{#if children}<span class="text">{@render children()}</span>{/if}
{/snippet}

<button
	class="button {variant} {size}"
	class:icon-only={iconOnly}
	{type}
	aria-label={iconOnly ? label : undefined}
	title={iconOnly ? label : undefined}
	{...rest}
>
	{@render content()}
</button>

<style>
	.button {
		/* The density unit decides the height (the theme's "8.5 units tall, 7 small, 10.5
		   large"), so a denser theme is a shorter button without anyone touching this file. */
		--height: calc(var(--space) * 8.5);
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: calc(var(--space) * 1.5);
		height: var(--height);
		padding: 0 calc(var(--space) * 3.25);
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: var(--surface);
		color: var(--text);
		font-family: var(--font-ui);
		font-size: var(--ui-size);
		font-weight: 500;
		line-height: 1;
		white-space: nowrap;
		text-decoration: none;
		cursor: pointer;
		transition:
			transform var(--motion-button-hover),
			box-shadow var(--motion-button-hover),
			background var(--fade) var(--ease),
			border-color var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	.sm {
		--height: calc(var(--space) * 7);
		padding: 0 calc(var(--space) * 2.5);
		font-size: calc(var(--ui-size) - 1px);
	}

	.lg {
		--height: calc(var(--space) * 10.5);
		padding: 0 calc(var(--space) * 4.5);
	}

	.icon-only {
		width: var(--height);
		padding: 0;
	}

	/* `button.hover` lifts a pixel with the small shadow; `button.press` sinks it back. */
	.button:hover:not(:disabled) {
		transform: translateY(-1px);
		box-shadow: var(--shadow-sm);
	}

	.button:active:not(:disabled) {
		transform: translateY(1px);
		box-shadow: none;
		/* A slot is a duration *and* a curve, so it goes in the shorthand, never in
		   `transition-duration`. */
		transition:
			transform var(--motion-button-press),
			box-shadow var(--motion-button-press);
	}

	.neutral:hover:not(:disabled) {
		background: var(--surface-raised);
	}

	.highlighted {
		background: var(--brass);
		border-color: var(--brass);
		color: var(--on-brass);
	}

	.signature {
		background: var(--pomegranate);
		border-color: var(--pomegranate);
		color: var(--on-pomegranate);
	}

	.danger {
		background: var(--danger);
		border-color: var(--danger);
		color: var(--on-danger);
	}

	.danger-soft {
		background: var(--danger-soft);
		border-color: transparent;
		color: var(--danger);
	}

	.ghost {
		background: transparent;
		border-color: transparent;
		color: var(--text-muted);
	}

	.ghost:hover:not(:disabled) {
		background: var(--hover);
		color: var(--text);
		box-shadow: none;
	}

	.button:disabled {
		background: var(--surface);
		border-color: var(--line);
		color: var(--text-faint);
		cursor: not-allowed;
	}

	.ghost:disabled {
		background: transparent;
		border-color: transparent;
	}

	.text {
		overflow: hidden;
		text-overflow: ellipsis;
	}
</style>
