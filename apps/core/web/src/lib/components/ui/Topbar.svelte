<script lang="ts">
	/**
	 * The bar over a screen (the theme's `hera/topbar`): the title on the left, a toolbar on the
	 * right. The open look — no rule under it, the title in the interface face at full text
	 * colour — so the conversation below reads as one surface rather than a page under a header.
	 *
	 * The title crossfades when it changes (`topbar.title`), which is what a chat getting its
	 * name looks like: the same place, new words, no jump.
	 */
	import type { Snippet } from 'svelte';

	let { title, children }: { title: string; children?: Snippet } = $props();
</script>

<header class="topbar">
	{#key title}
		<h1 class="title">{title}</h1>
	{/key}
	{#if children}<div class="toolbar">{@render children()}</div>{/if}
</header>

<style>
	.topbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: calc(var(--space) * 4);
		flex: none;
		height: calc(var(--space) * 13);
		padding: 0 calc(var(--space) * 6);
	}

	.title {
		min-width: 0;
		margin: 0;
		overflow: hidden;
		color: var(--text);
		font-family: var(--font-ui);
		font-size: calc(var(--ui-size) + 1px);
		font-weight: 500;
		text-overflow: ellipsis;
		white-space: nowrap;
		animation: title-in var(--motion-topbar-title);
	}

	@keyframes title-in {
		from {
			opacity: 0;
		}
	}

	/* Room for the menu button the layout pins over the top-left corner below the phone
	   breakpoint, so the title stops short of it instead of running under it. */
	@media (max-width: 780px) {
		.topbar {
			min-height: 64px;
			padding-left: 64px;
		}
	}

	.toolbar {
		display: flex;
		flex: none;
		align-items: center;
		gap: calc(var(--space) * 2);
	}
</style>
