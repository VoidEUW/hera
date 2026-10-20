<script lang="ts">
	/**
	 * One set of entries in a sidebar (the theme's `hera/sidebar-group`): a caps label that opens
	 * and closes the group, its count in a small tinted pill, and an optional add button.
	 *
	 * The disclosure is `grid-template-rows: 0fr ↔ 1fr` plus opacity on `group.disclose`, and the
	 * body stays in the document while shut (`inert`), so a rename in progress inside it is not
	 * thrown away by closing the group. `fixed` groups — the settings sidebar's — do not close at
	 * all, because a settings section you can hide is one you can lose.
	 *
	 * Folded to an icon rail, the label line is gone and the group is only its entries.
	 */
	import type { Snippet } from 'svelte';
	import Icon from '../Icon.svelte';
	import IconButton from '../IconButton.svelte';
	import { sidebarContext } from './Sidebar.svelte';

	interface Props {
		label: string;
		count?: number;
		/** The add button's accessible name; the button shows only when `onadd` is given. */
		addLabel?: string;
		onadd?: () => void;
		fixed?: boolean;
		open?: boolean;
		children: Snippet;
	}

	let {
		label,
		count,
		addLabel,
		onadd,
		fixed = false,
		open = $bindable(true),
		children
	}: Props = $props();

	const context = sidebarContext();
	const id = $props.id();
	const shut = $derived(!fixed && !open && !context.collapsed);
</script>

<section class="group" class:shut class:collapsed={context.collapsed} aria-label={label}>
	<div class="label-row">
		{#if fixed}
			<h3 class="label">{label}</h3>
		{:else}
			<button
				class="label toggle"
				type="button"
				aria-expanded={!shut}
				aria-controls={id}
				onclick={() => (open = !open)}
			>
				<span class="chevron"><Icon name="chevD" size="calc(var(--icon-size) - 3px)" /></span>
				{label}
			</button>
		{/if}
		{#if count !== undefined}<span class="count">{count}</span>{/if}
		{#if onadd}
			<IconButton icon="plus" size="sm" label={addLabel ?? label} onclick={onadd} />
		{/if}
	</div>
	<div class="entries" {id} inert={shut}>
		<div class="inner">{@render children()}</div>
	</div>
</section>

<style>
	.group {
		display: flex;
		flex-direction: column;
		margin-top: calc(var(--space) * 3);
	}

	.label-row {
		display: flex;
		align-items: center;
		gap: calc(var(--space) * 1.5);
		height: calc(var(--space) * 7);
		padding: 0 var(--sb-ir) 0 var(--sb-ix);
		transition: opacity var(--motion-sidebar-collapse);
	}

	.collapsed .label-row {
		opacity: 0;
		height: calc(var(--space) * 2);
		overflow: hidden;
	}

	.label {
		display: flex;
		align-items: center;
		gap: calc(var(--space) * 1.5);
		flex: 1;
		min-width: 0;
		margin: 0;
		color: var(--text-faint);
		font-size: 11px;
		font-weight: 600;
		letter-spacing: 0.09em;
		text-transform: uppercase;
		text-align: left;
	}

	.toggle:hover {
		color: var(--text-muted);
	}

	.chevron {
		display: flex;
		transition: transform var(--motion-group-disclose);
	}

	.shut .chevron {
		transform: rotate(-90deg);
	}

	/* The float look's count: a small tinted pill. */
	.count {
		padding: 0 calc(var(--space) * 1.75);
		border-radius: var(--chip-radius);
		background: var(--hover);
		color: var(--text-faint);
		font-size: 11px;
		font-variant-numeric: tabular-nums;
		line-height: 1.6;
	}

	.entries {
		display: grid;
		grid-template-rows: 1fr;
		opacity: 1;
		transition:
			grid-template-rows var(--motion-group-disclose),
			opacity var(--motion-group-disclose);
	}

	.shut .entries {
		grid-template-rows: 0fr;
		opacity: 0;
	}

	.inner {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-height: 0;
		overflow: hidden;
	}
</style>
