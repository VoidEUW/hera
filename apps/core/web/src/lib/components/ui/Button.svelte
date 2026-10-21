<script lang="ts" module>
	export type Variant =
		'neutral' | 'highlighted' | 'signature' | 'danger' | 'danger-soft' | 'ghost';
</script>

<script lang="ts">
	/**
	 * A button with a word on it (the theme's `hera/button`): one shape, six meanings.
	 *
	 * - `neutral` for most things;
	 * - `highlighted` (brass) for the one action a screen leads with — Save, Allow, Send an answer;
	 * - `signature` (pomegranate) only where it is her;
	 * - `danger` for a destructive verb, `danger-soft` for one that is quieter about it;
	 * - `ghost` for low emphasis — Cancel, Wait.
	 *
	 * Disabled is drawn the same for all of them: grayed out. With `href` it is a link that looks
	 * like a button — a download, an export — because going somewhere and doing something are
	 * different elements to a screen reader. A control that is only an icon is an `IconButton`.
	 */
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import type { IconName } from '$lib/icons';
	import Icon from './Icon.svelte';
	import Spinner from './Spinner.svelte';
	import { keys, type KeyId } from '$lib/keys';
	import { tooltip } from '$lib/tooltip';

	interface Props extends Omit<HTMLButtonAttributes, 'children'> {
		variant?: Variant;
		size?: 'sm' | 'md' | 'lg';
		/** A leading icon. */
		icon?: IconName;
		/** Working: a small spinner replaces the icon and the button stops taking clicks. */
		busy?: boolean;
		block?: boolean;
		/** Makes it a link. Already resolved by the caller. */
		href?: string;
		download?: string | boolean;
		/** A link that leaves the client router — a file, not a page. */
		external?: boolean;
		/** The chord this mirrors (#112), shown as a tooltip: a button with a word on it has no
		 * room for a key beside it without crowding the row it sits in. */
		keyId?: KeyId;
		children: Snippet;
	}

	let {
		variant = 'neutral',
		size = 'md',
		icon,
		busy = false,
		block = false,
		href,
		download,
		external = false,
		type = 'button',
		disabled,
		keyId,
		children,
		...rest
	}: Props = $props();
</script>

{#snippet content()}
	{#if busy}
		<Spinner size={14} />
	{:else if icon}
		<Icon name={icon} />
	{/if}
	<span class="text">{@render children()}</span>
{/snippet}

{#if href}
	<!-- eslint-disable svelte/no-navigation-without-resolve -->
	<a
		class="button {variant} {size}"
		class:block
		{href}
		download={download === true ? '' : download || undefined}
		rel={external ? 'external' : undefined}
	>
		{@render content()}
	</a>
	<!-- eslint-enable svelte/no-navigation-without-resolve -->
{:else}
	<button
		class="button {variant} {size}"
		class:block
		{type}
		disabled={disabled || busy}
		aria-busy={busy || undefined}
		aria-keyshortcuts={keyId ? keys.aria(keyId) : undefined}
		use:tooltip={keyId ? { label: '', keys: keys.label(keyId) } : undefined}
		{...rest}
	>
		{@render content()}
	</button>
{/if}

<style>
	.button {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 7px;
		height: calc(var(--space) * 8.5);
		padding: 0 calc(var(--space) * 3.5);
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: var(--surface);
		color: var(--text);
		font-family: var(--font-ui);
		font-size: 13px;
		font-weight: 500;
		line-height: 1;
		white-space: nowrap;
		text-decoration: none;
		cursor: pointer;
		transition:
			box-shadow var(--motion-button-hover),
			transform var(--motion-button-hover),
			background-color var(--motion-button-hover),
			color var(--motion-button-hover),
			border-color var(--motion-button-hover);
	}

	.sm {
		gap: 5px;
		height: calc(var(--space) * 7);
		padding: 0 calc(var(--space) * 2.5);
		font-size: 12px;
	}

	.lg {
		height: calc(var(--space) * 10.5);
		padding: 0 calc(var(--space) * 5);
		font-size: 14px;
	}

	.block {
		width: 100%;
	}

	/* `button.hover` lifts a pixel with the small shadow; `button.press` sinks it back. */
	.button:hover:not(:disabled) {
		transform: translateY(-1px);
		box-shadow: var(--shadow-sm);
	}

	.button:active:not(:disabled) {
		transform: translateY(1px);
		box-shadow: none;
		transition:
			transform var(--motion-button-press),
			box-shadow var(--motion-button-press);
	}

	.highlighted {
		border-color: var(--brass);
		background: var(--brass);
		color: var(--on-brass);
	}

	.signature {
		border-color: var(--pomegranate);
		background: var(--pomegranate);
		color: var(--on-pomegranate);
	}

	.danger {
		border-color: var(--danger);
		background: var(--danger);
		color: var(--on-danger);
	}

	.danger-soft {
		border-color: transparent;
		background: var(--danger-soft);
		color: var(--danger);
	}

	.ghost {
		border-color: transparent;
		background: transparent;
		color: var(--text-muted);
	}

	.ghost:hover:not(:disabled) {
		color: var(--text);
		box-shadow: inset 0 0 0 100px var(--hover);
	}

	.button:disabled {
		border-color: var(--line);
		background: var(--surface);
		color: var(--text-faint);
		cursor: not-allowed;
		opacity: 0.65;
	}

	.ghost:disabled {
		border-color: transparent;
		background: transparent;
	}

	.text {
		overflow: hidden;
		text-overflow: ellipsis;
	}
</style>
