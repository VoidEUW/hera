<script lang="ts">
	/**
	 * A sentence inside a `Menu`: the question a confirmation asks, or — `quiet` — the consequence
	 * under it. Quieter rather than louder, because a consequence is a fact about what you are
	 * about to lose, not a second alarm.
	 */
	import type { Snippet } from 'svelte';

	let { quiet = false, children }: { quiet?: boolean; children: Snippet } = $props();
</script>

<p class="note" class:quiet>{@render children()}</p>

<style>
	.note {
		max-width: 240px;
		margin: calc(var(--space) * 1) calc(var(--space) * 2) calc(var(--space) * 1.5);
		color: var(--text-muted);
		font-size: calc(var(--ui-size) - 1.5px);
		line-height: 1.4;
	}

	.quiet {
		margin-top: calc(var(--space) * -0.5);
		color: var(--text-faint);
	}
</style>
