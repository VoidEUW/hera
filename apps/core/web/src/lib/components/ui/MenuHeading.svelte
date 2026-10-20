<script lang="ts">
	/** A group label inside a `Menu` (the theme's `.mh`): small faint capitals. */
	import type { Snippet } from 'svelte';

	let { children }: { children: Snippet } = $props();
</script>

<div class="heading" role="presentation">{@render children()}</div>

<style>
	.heading {
		padding: 6px 9px 4px;
		color: var(--text-faint);
		font-size: 10.5px;
		font-weight: 600;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
</style>
