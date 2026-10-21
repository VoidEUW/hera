<script lang="ts">
	/** A key, as in ⌘K or Esc (the theme's `hera/chips`, the `kbd` part). */
	import type { Snippet } from 'svelte';

	interface Props {
		/** Drawn only: the control already announces its chord through `aria-keyshortcuts`, and
		 * reading it again inside the control's name — "New chat ⌘⇧O" — is noise. */
		decorative?: boolean;
		children: Snippet;
	}

	let { decorative = false, children }: Props = $props();
</script>

<kbd class="key" aria-hidden={decorative || undefined}>{@render children()}</kbd>

<style>
	.key {
		display: inline-flex;
		align-items: center;
		padding: 3px 5px;
		border: var(--border-width) solid var(--line);
		border-radius: 4px;
		background: var(--surface);
		color: var(--text-faint);
		font: 500 10.5px/1 var(--font-mono);
		white-space: nowrap;
	}
</style>
