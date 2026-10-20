<script lang="ts">
	/**
	 * A small status mark that carries its meaning by role colour (the theme's `hera/chips`):
	 * `live` is something running, `authority` something she was granted or pinned, `danger`
	 * something that failed. A dot leads the live and danger ones, because a state reads at a
	 * glance before its word does.
	 */
	import type { Snippet } from 'svelte';

	interface Props {
		tone?: 'neutral' | 'authority' | 'live' | 'danger';
		dot?: boolean;
		children: Snippet;
	}

	let { tone = 'neutral', dot = tone === 'live' || tone === 'danger', children }: Props = $props();
</script>

<span class="pill {tone}">
	{#if dot}<span class="dot" aria-hidden="true"></span>{/if}
	{@render children()}
</span>

<style>
	.pill {
		display: inline-flex;
		align-items: center;
		gap: calc(var(--space) * 1.25);
		height: calc(var(--space) * 5.5);
		padding: 0 calc(var(--space) * 2.5);
		border-radius: var(--chip-radius);
		background: var(--hover);
		color: var(--text-muted);
		font-size: calc(var(--ui-size) - 2px);
		font-weight: 500;
		white-space: nowrap;
	}

	.authority {
		background: var(--brass-soft);
		color: var(--brass);
	}

	.live {
		background: var(--laurel-soft);
		color: var(--laurel);
	}

	.danger {
		background: var(--danger-soft);
		color: var(--danger);
	}

	.dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: currentColor;
	}
</style>
