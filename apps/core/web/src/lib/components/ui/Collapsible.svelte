<script lang="ts">
	/**
	 * A filled box whose header discloses its content (the theme's `hera/collapsible`): provider
	 * cards, model rows, advanced settings.
	 *
	 * The body animates with `grid-template-rows: 0fr ↔ 1fr` plus opacity — the theme's one
	 * disclosure gesture (`collapse.disclose`) — and stays in the document while shut, `inert`,
	 * so a field inside keeps its value and its state when the box closes and opens again. The
	 * header is the button; anything in `actions` sits beside it rather than inside it, because a
	 * button inside a button is a click nobody can predict.
	 */
	import type { Snippet } from 'svelte';
	import Icon from './Icon.svelte';

	interface Props {
		open?: boolean;
		title: Snippet;
		subtitle?: Snippet;
		/** Controls that belong on the header row but are not the disclosure. */
		actions?: Snippet;
		children: Snippet;
	}

	let { open = $bindable(false), title, subtitle, actions, children }: Props = $props();

	const id = `collapsible-${Math.random().toString(36).slice(2, 9)}`;
</script>

<section class="box" class:open>
	<div class="header">
		<button
			type="button"
			class="toggle"
			aria-expanded={open}
			aria-controls={id}
			onclick={() => (open = !open)}
		>
			<span class="chevron"><Icon name="chevR" /></span>
			<span class="titles">
				<span class="title">{@render title()}</span>
				{#if subtitle}<span class="subtitle">{@render subtitle()}</span>{/if}
			</span>
		</button>
		{#if actions}<div class="actions">{@render actions()}</div>{/if}
	</div>
	<div class="body" {id} inert={!open}>
		<div class="inner">{@render children()}</div>
	</div>
</section>

<style>
	.box {
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius);
		background: var(--surface);
	}

	.header {
		display: flex;
		align-items: center;
		gap: calc(var(--space) * 2);
		padding-right: calc(var(--space) * 3);
	}

	.toggle {
		display: flex;
		flex: 1;
		min-width: 0;
		align-items: center;
		gap: calc(var(--space) * 2.5);
		padding: calc(var(--space) * 3);
		text-align: left;
	}

	.chevron {
		display: flex;
		color: var(--text-faint);
		transition: transform var(--motion-collapse-disclose);
	}

	.open .chevron {
		transform: rotate(90deg);
	}

	.titles {
		display: flex;
		min-width: 0;
		flex-direction: column;
		gap: 2px;
	}

	.title {
		color: var(--text);
		font-weight: 500;
	}

	.subtitle {
		color: var(--text-faint);
		font-size: calc(var(--ui-size) - 1.5px);
	}

	.actions {
		display: flex;
		align-items: center;
		gap: calc(var(--space) * 2);
	}

	.body {
		display: grid;
		grid-template-rows: 0fr;
		opacity: 0;
		transition:
			grid-template-rows var(--motion-collapse-disclose),
			opacity var(--motion-collapse-disclose);
	}

	.open .body {
		grid-template-rows: 1fr;
		opacity: 1;
	}

	.inner {
		min-height: 0;
		overflow: hidden;
	}

	.open .inner {
		padding: 0 calc(var(--space) * 3) calc(var(--space) * 3);
	}
</style>
