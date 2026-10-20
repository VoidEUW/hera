<script lang="ts">
	/** A key, as in ⌘K or Esc (the theme's `hera/chips`, the `kbd` part). */
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();
</script>

<kbd class="key">{@render children()}</kbd>

<style>
	.key {
		display: inline-grid;
		place-items: center;
		min-width: calc(var(--space) * 5);
		height: calc(var(--space) * 5);
		padding: 0 calc(var(--space) * 1.25);
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: var(--surface);
		color: var(--text-muted);
		font-family: var(--font-mono);
		font-size: calc(var(--ui-size) - 3px);
		line-height: 1;
	}
</style>
