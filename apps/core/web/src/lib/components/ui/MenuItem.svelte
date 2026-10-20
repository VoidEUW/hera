<script lang="ts">
	/**
	 * One row in a `Menu`. A button, or a link when it goes somewhere (`href`) — Open, Export —
	 * because navigating and acting are different elements to a screen reader.
	 *
	 * `danger` is a destructive verb. `current` is the choice that is already made — the project
	 * a chat is in, in the move list — shown in brass and not pressable, rather than dropped, so
	 * the list is the same length every time and shows what the answer currently is.
	 */
	import type { Snippet } from 'svelte';
	import type { IconName } from '$lib/icons';
	import Icon from './Icon.svelte';

	interface Props {
		icon?: IconName;
		danger?: boolean;
		current?: boolean;
		/** `menuitemradio` for a list of mutually exclusive destinations. */
		role?: 'menuitem' | 'menuitemradio';
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
		danger = false,
		current = false,
		role = 'menuitem',
		href,
		download = false,
		external = false,
		onclick,
		children
	}: Props = $props();
</script>

{#if href}
	<!-- The caller resolves the URL: `resolve()` for a page, the API base for a download. -->
	<!-- eslint-disable svelte/no-navigation-without-resolve -->
	<a
		class="item"
		class:danger
		{role}
		{href}
		download={download || undefined}
		rel={external ? 'external' : undefined}
		{onclick}
	>
		{#if icon}<Icon name={icon} />{/if}
		{@render children()}
	</a>
	<!-- eslint-enable svelte/no-navigation-without-resolve -->
{:else}
	<button
		class="item"
		class:danger
		class:current
		type="button"
		{role}
		aria-checked={role === 'menuitemradio' ? current : undefined}
		disabled={current}
		{onclick}
	>
		{#if icon}<Icon name={icon} />{/if}
		{@render children()}
	</button>
{/if}

<style>
	.item {
		display: flex;
		align-items: center;
		gap: calc(var(--space) * 2);
		width: 100%;
		min-height: calc(var(--space) * 7.5);
		padding: 0 calc(var(--space) * 2);
		border-radius: var(--radius-sm);
		color: var(--text-muted);
		font-size: calc(var(--ui-size) - 0.5px);
		text-align: left;
		text-decoration: none;
		transition:
			background var(--motion-entry-hover),
			color var(--motion-entry-hover);
	}

	.item:hover,
	.item:focus-visible {
		background: var(--hover);
		color: var(--text);
		outline: none;
	}

	.danger,
	.danger:hover,
	.danger:focus-visible {
		color: var(--danger);
	}

	.current,
	.current:hover {
		background: none;
		color: var(--brass);
		cursor: default;
	}
</style>
