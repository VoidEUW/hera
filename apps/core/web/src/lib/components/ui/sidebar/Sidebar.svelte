<script lang="ts">
	/**
	 * One sidebar, two variants (the theme's `hera/sidebar`): the shell is always a head, a body
	 * that scrolls and an optional foot, and a variant only fills the slots.
	 *
	 * - **chat** — the brand in the head, groups in the body, the account in
	 *   the foot. Resizable from its right edge (drag, or arrow keys in 16 px steps, Home / End to
	 *   the ends, double-click to reset).
	 * - **settings** — the left column of the settings dialog: the same float panel with the title
	 *   as its brand, fixed groups, entries without actions, a narrower width, never resized.
	 *
	 * The float look: an inset panel on the ground, rounded, `--surface`, a soft shadow and no
	 * divider line. Every row hangs on the same two lines — the lead line (icons, the mark,
	 * chevrons) and the label line — set by the `--sb-*` custom properties here, so nothing pads a
	 * row by hand.
	 */
	import type { Snippet } from 'svelte';
	import { MAX, MIN, sidebar } from '$lib/stores/sidebar.svelte';
	import { t } from '$lib/i18n';

	interface Props {
		variant?: 'chat' | 'settings';
		/** The landmark's accessible name. */
		label: string;
		/** Chat only: whether the right edge can be dragged. Off for the phone sheet. */
		resizable?: boolean;
		head: Snippet;
		foot?: Snippet;
		children: Snippet;
	}

	let { variant = 'chat', label, resizable = false, head, foot, children }: Props = $props();

	let nav = $state<HTMLElement | null>(null);
	let dragging = $state(false);

	function drag(event: PointerEvent) {
		if (event.button !== 0 || !nav) return;
		event.preventDefault();
		const left = nav.getBoundingClientRect().left;
		const handle = event.currentTarget as HTMLElement;
		handle.setPointerCapture(event.pointerId);
		dragging = true;
		const move = (next: PointerEvent) => sidebar.resize(next.clientX - left);
		const stop = () => {
			dragging = false;
			handle.removeEventListener('pointermove', move);
			handle.removeEventListener('pointerup', stop);
			handle.removeEventListener('pointercancel', stop);
		};
		handle.addEventListener('pointermove', move);
		handle.addEventListener('pointerup', stop);
		handle.addEventListener('pointercancel', stop);
	}

	function key(event: KeyboardEvent) {
		if (sidebar.key(event.key)) event.preventDefault();
	}
</script>

<nav
	bind:this={nav}
	class="sidebar {variant}"
	class:dragging
	aria-label={label}
	style:--sb-width={variant === 'chat' && resizable ? `${sidebar.width}px` : undefined}
>
	<div class="head">{@render head()}</div>
	<div class="body">{@render children()}</div>
	{#if foot}<div class="foot">{@render foot()}</div>{/if}

	{#if resizable}
		<!-- A focusable `role="separator"` with a value is the ARIA window-splitter pattern: an
		     interactive widget, which Svelte's a11y lint does not know a separator can be. -->
		<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
		<div
			class="resize"
			role="separator"
			aria-orientation="vertical"
			aria-label={t.rail.resize}
			aria-valuenow={sidebar.width}
			aria-valuemin={MIN}
			aria-valuemax={MAX}
			tabindex="0"
			onpointerdown={drag}
			ondblclick={() => sidebar.reset()}
			onkeydown={key}
		></div>
	{/if}
</nav>

<style>
	.sidebar {
		/* The two lines every row hangs on (see the docstring): edge to row, row to lead line,
		   the lead column, lead to label, and the inset on the right. */
		--sb-pad: calc(var(--space) * 2);
		--sb-ix: calc(var(--space) * 2);
		--sb-lead: var(--icon-size);
		--sb-gap: calc(var(--space) * 2.5);
		--sb-ir: calc(var(--space) * 1.5);
		--sb-row: calc(var(--space) * 8);

		position: relative;
		display: flex;
		flex-direction: column;
		flex: none;
		width: var(--sb-width, var(--rail));
		min-height: 0;
		padding: var(--sb-pad);
		border-radius: var(--radius-lg);
		background: var(--surface);
		box-shadow: var(--shadow-sm);
		transition: width var(--motion-sidebar-collapse);
	}

	.chat,
	.settings {
		height: calc(100% - var(--sb-pad) * 2);
		margin: var(--sb-pad);
	}

	.settings {
		--sb-width: 228px;
	}

	.dragging {
		transition: none;
		user-select: none;
	}

	.head {
		display: flex;
		flex-direction: column;
		gap: 2px;
		flex: none;
	}

	.body {
		display: flex;
		flex: 1;
		flex-direction: column;
		gap: 2px;
		min-height: 0;
		overflow-x: hidden;
		overflow-y: auto;
		margin: 0 calc(var(--sb-pad) * -1);
		padding: 0 var(--sb-pad);
	}

	.foot {
		flex: none;
		padding-top: calc(var(--space) * 2);
	}

	/* The edge line fades in on hover, focus and while dragging (`sidebar.resize`). */
	.resize {
		position: absolute;
		top: var(--radius-lg);
		right: -4px;
		bottom: var(--radius-lg);
		width: 8px;
		cursor: col-resize;
		touch-action: none;
	}

	.resize::after {
		content: '';
		position: absolute;
		top: 0;
		bottom: 0;
		left: 3px;
		width: 2px;
		border-radius: 1px;
		background: var(--laurel);
		opacity: 0;
		transition: opacity var(--motion-sidebar-resize);
	}

	.resize:hover::after,
	.resize:focus-visible::after,
	.dragging .resize::after {
		opacity: 1;
	}

	.resize:focus-visible {
		outline: none;
	}

	/* The settings variant on a phone: Settings shows either this list or one screen (#41), so
	   the list is the page itself — the whole width, no card floating on the ground, and the same
	   inset the screen beside it has, so the two read as one sheet. */
	@media (max-width: 780px) {
		.settings {
			flex: 1;
			width: auto;
			height: auto;
			margin: 0;
			padding: 10px 16px 16px;
			border-radius: 0;
			background: none;
			box-shadow: none;
		}
	}
</style>
