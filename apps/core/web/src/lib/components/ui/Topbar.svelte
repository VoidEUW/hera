<script lang="ts">
	/**
	 * The bar over a screen (the theme's `hera/topbar`): the title on the left, a toolbar on the
	 * right. The open look — no rule under it, the title in the interface face at full text
	 * colour — so the conversation below reads as one surface rather than a page under a header.
	 *
	 * The title crossfades when it changes (`topbar.title`), which is what a chat getting its
	 * name looks like: the same place, new words, no jump.
	 *
	 * On a phone the bar carries the menu button that opens the rail (`onmenu`), drawn like the
	 * toolbar's own icons (#41). It used to be the layout's floating button pinned over the
	 * bar's corner, which read as two things — a round button, and a bar beside it — and came
	 * apart from the bar whenever iOS moved the page under it. Not drawn above the breakpoint,
	 * where the rail is always there.
	 */
	import type { Snippet } from 'svelte';
	import { t } from '$lib/i18n';
	import IconButton from './IconButton.svelte';

	let { title, onmenu, children }: { title: string; onmenu?: () => void; children?: Snippet } =
		$props();
</script>

<header class="topbar">
	{#if onmenu}
		<span class="lead"><IconButton icon="menu" label={t.rail.openMenu} onclick={onmenu} /></span>
	{/if}
	{#key title}
		<h1 class="title">{title}</h1>
	{/key}
	{#if children}<div class="toolbar">{@render children()}</div>{/if}
</header>

<style>
	.topbar {
		display: flex;
		align-items: center;
		gap: 10px;
		flex: none;
		min-width: 0;
		height: calc(var(--space) * 13);
		padding: 0 12px 0 24px;
		background: var(--ground);
	}

	.title {
		flex: 1;
		min-width: 0;
		margin: 0;
		overflow: hidden;
		color: var(--text);
		font-family: var(--font-ui);
		font-size: 14px;
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

	.lead {
		display: none;
	}

	/* On a phone the bar starts with the menu button, and clears the status bar of an installed
	   app (`viewport-fit=cover` lets the page run under it). */
	@media (max-width: 780px) {
		.topbar {
			min-height: calc(64px + env(safe-area-inset-top));
			padding: env(safe-area-inset-top) 8px 0 8px;
		}

		.lead {
			display: flex;
			flex: none;
		}
	}

	.toolbar {
		display: flex;
		flex: none;
		align-items: center;
		gap: 4px;
	}
</style>
