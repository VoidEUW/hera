<script lang="ts">
	/**
	 * The way out of a dialog, a side view, a chip or a toast (the theme's `hera/close-button`):
	 * a filled round button with an ×, and a hit area that is never smaller than the target a
	 * thumb needs, whatever the drawing's size.
	 *
	 * `sm` is borderless and unfilled — the × on a chip or an attachment, where a filled disc
	 * would be heavier than the thing it removes.
	 */
	import { t } from '$lib/i18n';
	import Icon from './Icon.svelte';

	interface Props {
		size?: 'sm' | 'md' | 'lg';
		/** What closing means here, for a screen reader — "Close settings", "Remove file". */
		label?: string;
		onclick?: (event: MouseEvent) => void;
		class?: string;
	}

	let { size = 'md', label = t.ui.close, onclick, class: extra = '' }: Props = $props();
</script>

<button class="close {size} {extra}" type="button" aria-label={label} title={label} {onclick}>
	<Icon name="x" />
</button>

<style>
	.close {
		--diameter: calc(var(--space) * 7.5);
		display: inline-grid;
		place-items: center;
		flex: none;
		width: var(--diameter);
		height: var(--diameter);
		border-radius: 50%;
		background: var(--surface-raised);
		color: var(--text-muted);
		cursor: pointer;
		transition:
			transform var(--motion-close-hover),
			background var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	.close:hover {
		transform: scale(1.1);
		background: var(--hover);
		color: var(--text);
	}

	.lg {
		--diameter: calc(var(--space) * 9);
	}

	.sm {
		--diameter: calc(var(--space) * 5);
		background: transparent;
	}

	/* The visible disc is small; the target is not. */
	.close::after {
		content: '';
		position: absolute;
		inset: calc(var(--space) * -2);
	}

	.close {
		position: relative;
	}
</style>
