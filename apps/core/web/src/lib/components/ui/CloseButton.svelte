<script lang="ts">
	/**
	 * The way out of a dialog, a side view, a chip or a toast (the theme's `hera/close-button`,
	 * float look): a filled round button with an ×, growing a little on hover (`close.hover`).
	 * `sm` is the × on an attachment or in a search field; `lg` a full-screen sheet's.
	 *
	 * `inverse` is the toast's: on an inverted bar the disc is the bar's own colour and the ×
	 * takes the bar's text colour, faded, so the way out is there without being a second object.
	 */
	import { t } from '$lib/i18n';
	import Icon from './Icon.svelte';
	import { tooltip } from '$lib/tooltip';

	interface Props {
		size?: 'sm' | 'md' | 'lg';
		/** What closing means here — "Close settings", "Remove brief.pdf". */
		label?: string;
		inverse?: boolean;
		onclick?: (event: MouseEvent) => void;
	}

	let { size = 'md', label = t.ui.close, inverse = false, onclick }: Props = $props();
</script>

<button
	class="close {size}"
	class:inverse
	type="button"
	aria-label={label}
	use:tooltip={label}
	{onclick}
>
	<Icon name="x" />
</button>

<style>
	.close {
		position: relative;
		display: inline-grid;
		flex: none;
		place-items: center;
		width: 28px;
		height: 28px;
		border: var(--border-width) solid transparent;
		border-radius: 50%;
		background: var(--surface-raised);
		color: var(--text-muted);
		--icon-size: 14px;
		transition:
			transform var(--motion-close-hover),
			background-color var(--motion-close-hover),
			color var(--motion-close-hover);
	}

	.close:hover {
		transform: scale(1.1);
		color: var(--text);
	}

	.sm {
		width: 22px;
		height: 22px;
		border: 0;
		--icon-size: 12px;
	}

	.lg {
		width: 36px;
		height: 36px;
		--icon-size: 16px;
	}

	.inverse {
		background: transparent;
		color: inherit;
		opacity: 0.6;
	}

	.inverse:hover {
		color: inherit;
		opacity: 1;
	}

	/* The drawn disc can be small; the target is not. */
	.close::after {
		content: '';
		position: absolute;
		inset: -6px;
	}
</style>
