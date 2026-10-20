<script lang="ts">
	/**
	 * One row in a `Menu` (the theme's `.mi`): an optional icon, a label with an optional quieter
	 * description under it, and what ends the row —
	 *
	 * - `trail="check"` (the default for a choice): a brass check, visible only on the row that is
	 *   chosen. A chosen row has no fill of its own; hover is the `--hover` tint and nothing else.
	 * - `trail="switch"` / `trail="checkbox"`: the `Toggle` drawing, for a row that turns something
	 *   on rather than picking one of several.
	 *
	 * A button, or a link when it goes somewhere (`href`), because navigating and acting are
	 * different elements to a screen reader. `danger` is a destructive verb.
	 */
	import type { Snippet } from 'svelte';
	import type { IconName } from '$lib/icons';
	import Icon from './Icon.svelte';
	import Toggle from './Toggle.svelte';

	interface Props {
		icon?: IconName;
		/** A small picture instead of an icon — a provider's logo. */
		image?: string;
		description?: string;
		trail?: 'check' | 'switch' | 'checkbox' | 'none';
		/** Chosen (check) or switched on (switch, checkbox). */
		on?: boolean;
		danger?: boolean;
		disabled?: boolean;
		role?: 'menuitem' | 'menuitemradio' | 'menuitemcheckbox';
		/** Already resolved by the caller (`resolve(…)` or an API URL). */
		href?: string;
		download?: boolean;
		/** A link that leaves the client router — a file download, not a page. */
		external?: boolean;
		onclick?: (event: MouseEvent) => void;
		children: Snippet;
	}

	let {
		icon,
		image,
		description,
		trail,
		on = false,
		danger = false,
		disabled = false,
		role,
		href,
		download = false,
		external = false,
		onclick,
		children
	}: Props = $props();

	const end = $derived(
		trail ??
			(role === 'menuitemradio' ? 'check' : role === 'menuitemcheckbox' ? 'checkbox' : 'none')
	);
	const resolvedRole = $derived(
		role ?? (end === 'check' ? 'menuitemradio' : end === 'none' ? 'menuitem' : 'menuitemcheckbox')
	);
</script>

{#snippet body()}
	{#if image}
		<img class="lead image" src={image} alt="" />
	{:else if icon}
		<span class="lead"><Icon name={icon} /></span>
	{/if}
	<span class="text">
		{@render children()}
		{#if description}<small>{description}</small>{/if}
	</span>
	{#if end === 'check'}
		<span class="check" class:on><Icon name="check" /></span>
	{:else if end === 'switch'}
		<Toggle kind="switch" {on} />
	{:else if end === 'checkbox'}
		<Toggle kind="box" {on} />
	{/if}
{/snippet}

{#if href}
	<!-- The caller resolves the URL: `resolve()` for a page, the API base for a download. -->
	<!-- eslint-disable svelte/no-navigation-without-resolve -->
	<a
		class="item"
		class:danger
		role="menuitem"
		{href}
		download={download || undefined}
		rel={external ? 'external' : undefined}
		{onclick}
	>
		{@render body()}
	</a>
	<!-- eslint-enable svelte/no-navigation-without-resolve -->
{:else}
	<button
		class="item"
		class:danger
		type="button"
		role={resolvedRole}
		aria-checked={resolvedRole === 'menuitem' ? undefined : on}
		{disabled}
		{onclick}
	>
		{@render body()}
	</button>
{/if}

<style>
	.item {
		display: flex;
		align-items: center;
		gap: 9px;
		width: 100%;
		min-height: 32px;
		padding: 6px 9px;
		border-radius: max(calc(var(--radius) - 4px), 2px);
		color: var(--text);
		font-size: 13px;
		text-align: left;
		text-decoration: none;
		white-space: nowrap;
		transition: background-color var(--motion-entry-hover);
	}

	.item:hover:not(:disabled),
	.item:focus-visible {
		background: var(--hover);
		outline: none;
	}

	.item:disabled {
		color: var(--text-faint);
		cursor: default;
	}

	.lead {
		display: inline-grid;
		flex: none;
		color: var(--text-muted);
	}

	.image {
		width: var(--icon-size);
		height: var(--icon-size);
		object-fit: contain;
	}

	.text {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	small {
		display: block;
		overflow: hidden;
		color: var(--text-faint);
		font-size: 11px;
		text-overflow: ellipsis;
	}

	.check {
		display: inline-grid;
		flex: none;
		color: var(--brass);
		visibility: hidden;
	}

	.check.on {
		visibility: visible;
	}

	.danger,
	.danger .lead {
		color: var(--danger);
	}
</style>
