<script lang="ts">
	/**
	 * The popover every menu in Hera uses (the theme's `hera/selector` menu): a raised surface,
	 * a hairline, the card radius and the shadow, growing out of the corner of its anchor on
	 * `menu.enter`. Rows are `MenuItem`s, grouped by `MenuHeading`s and `MenuSeparator`s.
	 *
	 * Positioned `fixed` from its anchor rather than inside it, so no scrolling list or disclosing
	 * group can clip it. It opens on its preferred side (`placement`) and flips when there is no
	 * room there; it is at least as wide as its anchor and never narrower than 200px. A
	 * transparent catcher behind it takes the click that closes it — a menu is not a modal, so
	 * nothing is dimmed — and scrolling anything else closes it too, as the builder's does.
	 *
	 * Keyboard: the chosen row (or the first) takes focus on open, arrow keys move, Home and End
	 * jump, Escape and Tab close it and focus goes back to the anchor.
	 */
	import type { Snippet } from 'svelte';
	import { reveal } from '$lib/motion';

	interface Props {
		open: boolean;
		/** The control that opened it: where it is placed, and where focus returns. */
		anchor: HTMLElement | null;
		label: string;
		align?: 'start' | 'end';
		/** The side it prefers. The composer sits at the foot of the window, so its menus open up. */
		placement?: 'below' | 'above';
		onclose: () => void;
		children: Snippet;
	}

	let {
		open,
		anchor,
		label,
		align = 'start',
		placement = 'below',
		onclose,
		children
	}: Props = $props();

	let menu = $state<HTMLDivElement | null>(null);
	let place = $state({ top: 0, left: 0, above: false });

	const GAP = 6;
	const EDGE = 8;

	$effect(() => {
		if (!open || !anchor || !menu) return;
		const box = anchor.getBoundingClientRect();
		const width = Math.max(box.width, 200);
		menu.style.minWidth = `${width}px`;
		const own = menu.getBoundingClientRect();
		const roomBelow = window.innerHeight - box.bottom - GAP - EDGE;
		const roomAbove = box.top - GAP - EDGE;
		const above =
			placement === 'above'
				? own.height <= roomAbove || roomAbove > roomBelow
				: own.height > roomBelow && roomAbove > roomBelow;
		const left = align === 'end' ? box.right - own.width : box.left;
		place = {
			top: above ? box.top - GAP - own.height : box.bottom + GAP,
			left: Math.min(Math.max(EDGE, left), window.innerWidth - own.width - EDGE),
			above
		};
		const chosen = menu.querySelector<HTMLElement>(
			'[role^="menuitem"][aria-checked="true"]:not([disabled])'
		);
		(chosen ?? items()[0])?.focus();
	});

	$effect(() => {
		if (!open) return;
		// Scrolling under an open menu would leave it floating beside nothing.
		const away = (event: Event) => {
			if (menu && event.target instanceof Node && menu.contains(event.target)) return;
			onclose();
		};
		window.addEventListener('scroll', away, true);
		window.addEventListener('resize', away);
		return () => {
			window.removeEventListener('scroll', away, true);
			window.removeEventListener('resize', away);
		};
	});

	function close() {
		onclose();
		anchor?.focus();
	}

	function items(): HTMLElement[] {
		return [...(menu?.querySelectorAll<HTMLElement>('[role^="menuitem"]:not([disabled])') ?? [])];
	}

	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'Escape' || event.key === 'Tab') {
			event.preventDefault();
			event.stopPropagation();
			close();
			return;
		}
		const list = items();
		const here = list.indexOf(document.activeElement as HTMLElement);
		const next =
			event.key === 'ArrowDown'
				? (here + 1) % list.length
				: event.key === 'ArrowUp'
					? (here - 1 + list.length) % list.length
					: event.key === 'Home'
						? 0
						: event.key === 'End'
							? list.length - 1
							: null;
		if (next === null) return;
		event.preventDefault();
		list[next]?.focus();
	}
</script>

{#if open}
	<div class="away" role="presentation" onclick={close}></div>
	<div
		bind:this={menu}
		class="menu"
		class:above={place.above}
		class:end={align === 'end'}
		role="menu"
		tabindex="-1"
		aria-label={label}
		style:top="{place.top}px"
		style:left="{place.left}px"
		{onkeydown}
		in:reveal={{ scale: 0.95 }}
		out:reveal={{ scale: 0.95 }}
	>
		{@render children()}
	</div>
{/if}

<style>
	.away {
		position: fixed;
		inset: 0;
		z-index: 60;
	}

	.menu {
		position: fixed;
		z-index: 61;
		display: flex;
		flex-direction: column;
		max-width: min(360px, calc(100vw - 16px));
		max-height: min(60vh, 440px);
		overflow-y: auto;
		padding: 4px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius);
		background: var(--surface-raised);
		box-shadow: var(--shadow);
		transform-origin: top left;
	}

	.menu.end {
		transform-origin: top right;
	}

	.menu.above {
		transform-origin: bottom left;
	}

	.menu.above.end {
		transform-origin: bottom right;
	}
</style>
