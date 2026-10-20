<script lang="ts">
	/**
	 * A bordered box whose header discloses its content (the theme's `hera/collapsible`, soft look):
	 * provider cards, model rows, advanced settings.
	 *
	 * The body animates with `grid-template-rows: 0fr ↔ 1fr` plus opacity (`collapse.disclose`), and
	 * stays in the document while shut, `inert`, so a field inside keeps its value when the box
	 * closes and opens again. `lazy` instead renders the body only while it is open — for a box
	 * whose content fetches something or holds a draft, so a list of twenty closed boxes fetches
	 * nothing and closing one *is* discarding what was typed in it. The
	 * header is the button; `actions` sit beside it rather than inside it, because a button inside a
	 * button is a click nobody can predict.
	 */
	import type { Snippet } from 'svelte';
	import Icon from './Icon.svelte';

	interface Props {
		open?: boolean;
		lazy?: boolean;
		title: Snippet;
		subtitle?: Snippet;
		/** Controls that belong on the header row but are not the disclosure. */
		actions?: Snippet;
		ontoggle?: (open: boolean) => void;
		children: Snippet;
	}

	let {
		open = $bindable(false),
		lazy = false,
		title,
		subtitle,
		actions,
		ontoggle,
		children
	}: Props = $props();

	const id = $props.id();

	function toggle() {
		open = !open;
		ontoggle?.(open);
	}
</script>

<section class="box" class:open>
	<div class="header">
		<button type="button" class="toggle" aria-expanded={open} aria-controls={id} onclick={toggle}>
			<span class="chevron"><Icon name="chevR" /></span>
			<span class="titles">
				<b>{@render title()}</b>
				{#if subtitle}<small>{@render subtitle()}</small>{/if}
			</span>
		</button>
		{#if actions}<div class="actions">{@render actions()}</div>{/if}
	</div>
	<div class="body" {id} inert={!open}>
		<div>
			<div class="inner">
				{#if !lazy || open}{@render children()}{/if}
			</div>
		</div>
	</div>
</section>

<style>
	.box {
		overflow: hidden;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius);
		background: var(--surface);
	}

	.header {
		display: flex;
		align-items: center;
		gap: 8px;
		padding-right: 12px;
	}

	.toggle {
		display: flex;
		flex: 1;
		align-items: center;
		gap: 10px;
		min-width: 0;
		padding: 12px 14px;
		text-align: left;
	}

	.chevron {
		display: inline-grid;
		color: var(--text-faint);
		transition: transform var(--motion-collapse-disclose);
	}

	.open .chevron {
		transform: rotate(90deg);
	}

	.titles {
		flex: 1;
		min-width: 0;
	}

	b {
		display: block;
		overflow: hidden;
		color: var(--text);
		font-size: 13.5px;
		font-weight: 500;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	small {
		display: block;
		overflow: hidden;
		color: var(--text-faint);
		font-size: 12px;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.actions {
		display: flex;
		flex: none;
		align-items: center;
		gap: 8px;
	}

	.body {
		display: grid;
		grid-template-rows: 0fr;
		opacity: 0;
		transition:
			grid-template-rows var(--motion-collapse-disclose),
			opacity var(--motion-collapse-disclose);
	}

	.body > div {
		min-height: 0;
		overflow: hidden;
	}

	.open .body {
		grid-template-rows: 1fr;
		opacity: 1;
	}

	.inner {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 0 14px 14px 38px;
		color: var(--text-muted);
		font-size: 13px;
	}
</style>
