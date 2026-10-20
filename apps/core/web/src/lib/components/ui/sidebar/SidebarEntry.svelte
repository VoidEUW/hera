<script lang="ts">
	/**
	 * One row of a sidebar (the theme's `hera/sidebar-entry`): a leading icon on the lead line,
	 * the label on the label line, optional meta, and an optional trailing action — a chat, a
	 * project, a settings section, the account.
	 *
	 * A link when it goes somewhere (`href`, already resolved by the caller), a button when it
	 * does something. Active is a 2 px brass bar on the left edge with a faint fill
	 * (`entry.active`) — brass, because the chat you are in is her authority's one mark here.
	 *
	 * The trailing action shows on hover, on keyboard focus anywhere in the row, and while it is
	 * `pinned` (its menu is open) — a control that only appears under a pointer is one a keyboard
	 * cannot reach. Folded to an icon rail, the row is its icon with the label as a tooltip.
	 */
	import type { Snippet } from 'svelte';
	import type { IconName } from '$lib/icons';
	import { tooltip } from '$lib/tooltip';
	import Icon from '../Icon.svelte';
	import { sidebarContext } from './Sidebar.svelte';

	interface Props {
		label: string;
		icon?: IconName;
		/** A CSS colour for the icon — a project's own colour. A token, never a literal. */
		tint?: string;
		/** A custom lead instead of an icon: the brand mark, an avatar. */
		lead?: Snippet;
		href?: string;
		onclick?: (event: MouseEvent) => void;
		active?: boolean;
		disabled?: boolean;
		meta?: string;
		/** For a row that discloses something (a project's chats). */
		expanded?: boolean;
		/** Keep the trailing action visible — its menu is open. */
		pinned?: boolean;
		/** Indented one step: a chat inside a project. */
		nested?: boolean;
		action?: Snippet;
		ariaLabel?: string;
	}

	let {
		label,
		icon,
		tint,
		lead,
		href,
		onclick,
		active = false,
		disabled = false,
		meta,
		expanded,
		pinned = false,
		nested = false,
		action,
		ariaLabel
	}: Props = $props();

	const context = sidebarContext();
	const hint = $derived(context.collapsed ? label : undefined);
</script>

{#snippet inside()}
	<span class="lead" style:color={tint}>
		{#if lead}{@render lead()}{:else if icon}<Icon name={icon} />{/if}
	</span>
	<span class="label">{label}</span>
	{#if meta}<span class="meta">{meta}</span>{/if}
{/snippet}

<div class="row" class:active class:pinned class:nested class:has-action={Boolean(action)}>
	{#if href}
		<!-- The caller resolves the URL with `resolve()`. -->
		<!-- eslint-disable svelte/no-navigation-without-resolve -->
		<a
			class="entry"
			{href}
			aria-current={active ? 'page' : undefined}
			aria-label={ariaLabel}
			{onclick}
			use:tooltip={hint}>{@render inside()}</a
		>
		<!-- eslint-enable svelte/no-navigation-without-resolve -->
	{:else}
		<button
			class="entry"
			type="button"
			{disabled}
			aria-expanded={expanded}
			aria-current={active ? 'true' : undefined}
			aria-label={ariaLabel}
			{onclick}
			use:tooltip={hint}
		>
			{@render inside()}
		</button>
	{/if}
	{#if action && !context.collapsed}<span class="action">{@render action()}</span>{/if}
</div>

<style>
	.row {
		position: relative;
		display: flex;
		align-items: center;
	}

	.entry {
		position: relative;
		display: flex;
		flex: 1;
		align-items: center;
		gap: var(--sb-gap);
		min-width: 0;
		height: var(--sb-row);
		padding: 0 var(--sb-ir) 0 var(--sb-ix);
		border-radius: var(--radius-sm);
		color: var(--text-muted);
		font-size: var(--ui-size);
		text-align: left;
		text-decoration: none;
		transition:
			background var(--motion-entry-hover),
			color var(--motion-entry-hover);
	}

	.nested .entry {
		padding-left: calc(var(--sb-ix) + var(--sb-lead) + var(--sb-gap) - 4px);
	}

	.has-action .entry {
		padding-right: calc(var(--space) * 7);
	}

	.entry:hover:not(:disabled) {
		background: var(--hover);
		color: var(--text);
	}

	.entry:disabled {
		color: var(--text-faint);
		cursor: default;
	}

	/* `entry.active`: the bar, the text, a faint fill. */
	.active .entry {
		background: var(--hover);
		color: var(--text);
	}

	.active .entry::before {
		content: '';
		position: absolute;
		top: 22%;
		bottom: 22%;
		left: 0;
		width: 2px;
		border-radius: 1px;
		background: var(--brass);
		transition: opacity var(--motion-entry-active);
	}

	.lead {
		display: grid;
		place-items: center;
		flex: none;
		width: var(--sb-lead);
		color: var(--text-faint);
	}

	.active .lead,
	.entry:hover .lead {
		color: inherit;
	}

	.label {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		transition: opacity var(--motion-sidebar-collapse);
	}

	.meta {
		flex: none;
		color: var(--text-faint);
		font-family: var(--font-mono);
		font-size: 11px;
	}

	/* Folded: the label goes in the first part of the fold, and the row is only its icon. */
	:global(.sidebar.collapsed) .label,
	:global(.sidebar.collapsed) .meta {
		opacity: 0;
	}

	.action {
		position: absolute;
		top: 50%;
		right: calc(var(--space) * 1);
		display: flex;
		opacity: 0;
		transform: translateY(-50%);
		transition: opacity var(--fade) var(--ease);
	}

	.row:hover .action,
	.row:focus-within .action,
	.pinned .action {
		opacity: 1;
	}
</style>
