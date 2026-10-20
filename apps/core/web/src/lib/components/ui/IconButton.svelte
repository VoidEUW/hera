<script lang="ts">
	/**
	 * A control that is only an icon (the theme's `.ib`): copy, retry, download, the sidebar
	 * toggle, a row's overflow menu. Borderless and muted, the icon brightening and a faint tint
	 * on hover, sinking on press like every other button.
	 *
	 * The label is required twice over: it is the accessible name, and it is the tooltip that
	 * shows after a moment's rest (`hera/tooltip`), because an icon alone is a word you would have
	 * to already know. `on` is brass — the momentary "done" after Copy, a toggled view.
	 * `bordered` is the composer's round attach button.
	 */
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import type { IconName } from '$lib/icons';
	import Icon from './Icon.svelte';
	import { tooltip } from '$lib/tooltip';

	interface Props extends Omit<HTMLButtonAttributes, 'children'> {
		icon: IconName;
		label: string;
		size?: 'sm' | 'md';
		on?: boolean;
		bordered?: boolean;
		/** Makes it a link — a download. Already resolved by the caller. */
		href?: string;
		download?: string | boolean;
		external?: boolean;
		ref?: HTMLElement | null;
	}

	let {
		icon,
		label,
		size = 'md',
		on = false,
		bordered = false,
		href,
		download,
		external = false,
		type = 'button',
		ref = $bindable(),
		...rest
	}: Props = $props();
</script>

{#if href}
	<!-- eslint-disable svelte/no-navigation-without-resolve -->
	<a
		bind:this={ref}
		class="icon-button {size}"
		class:on
		class:bordered
		{href}
		download={download === true ? '' : download || undefined}
		rel={external ? 'external' : undefined}
		aria-label={label}
		use:tooltip={label}
	>
		<Icon name={icon} />
	</a>
	<!-- eslint-enable svelte/no-navigation-without-resolve -->
{:else}
	<button
		bind:this={ref}
		class="icon-button {size}"
		class:on
		class:bordered
		{type}
		aria-label={label}
		use:tooltip={label}
		{...rest}
	>
		<Icon name={icon} />
	</button>
{/if}

<style>
	.icon-button {
		position: relative;
		display: inline-grid;
		flex: none;
		place-items: center;
		width: calc(var(--icon-size) + 14px);
		height: calc(var(--icon-size) + 14px);
		border-radius: var(--radius-sm);
		color: var(--text-muted);
		transition:
			box-shadow var(--motion-button-hover),
			transform var(--motion-button-hover),
			background-color var(--motion-button-hover),
			color var(--motion-button-hover);
	}

	.sm {
		width: 24px;
		height: 24px;
		border-radius: calc(var(--radius-sm) - 2px);
		--icon-size: 14px;
	}

	.icon-button:hover:not(:disabled) {
		color: var(--text);
		box-shadow: inset 0 0 0 100px var(--hover);
	}

	.icon-button:active:not(:disabled) {
		transform: translateY(1px);
		transition: transform var(--motion-button-press);
	}

	.icon-button:disabled {
		color: var(--text-faint);
		cursor: not-allowed;
		opacity: 0.6;
	}

	.on {
		color: var(--brass);
	}

	.bordered {
		width: 28px;
		height: 28px;
		border: var(--border-width) solid var(--line);
		border-radius: 50%;
	}
</style>
