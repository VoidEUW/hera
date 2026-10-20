<script lang="ts">
	/**
	 * The popover every row menu uses (the theme's selector menu, which is "the same popover
	 * every other menu in Hera uses"): a raised surface, a hairline, the card radius, the shadow,
	 * growing out of its anchor on `menu.enter`.
	 *
	 * Positioned `fixed` from its anchor rather than absolutely inside it, so no scrolling list
	 * or disclosing group can clip it; it opens below the anchor and flips above when there is no
	 * room. A transparent catcher behind it takes the click that closes it — a menu is not a
	 * modal, so nothing is dimmed.
	 *
	 * Keyboard: the first item takes focus on open, arrow keys move between items, Escape and
	 * Tab close it and focus goes back to the anchor.
	 */
	import type { Snippet } from 'svelte';
	import { reveal } from '$lib/motion';

	interface Props {
		open: boolean;
		/** The control that opened it: where it is placed, and where focus returns. */
		anchor: HTMLElement | null;
		label: string;
		align?: 'start' | 'end';
		onclose: () => void;
		children: Snippet;
	}

	let { open, anchor, label, align = 'end', onclose, children }: Props = $props();

	let menu = $state<HTMLDivElement | null>(null);
	let place = $state({ top: 0, left: 0, above: false });

	const GAP = 4;

	$effect(() => {
		if (!open || !anchor || !menu) return;
		const box = anchor.getBoundingClientRect();
		const own = menu.getBoundingClientRect();
		const above = box.bottom + GAP + own.height > window.innerHeight - 8;
		const left = align === 'end' ? box.right - own.width : box.left;
		place = {
			top: above ? box.top - GAP - own.height : box.bottom + GAP,
			left: Math.min(Math.max(8, left), window.innerWidth - own.width - 8),
			above
		};
		menu.querySelector<HTMLElement>('[role^="menuitem"]:not([disabled])')?.focus();
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
		const step = event.key === 'ArrowDown' ? 1 : event.key === 'ArrowUp' ? -1 : 0;
		if (!step) return;
		event.preventDefault();
		const list = items();
		const here = list.indexOf(document.activeElement as HTMLElement);
		list[(here + step + list.length) % list.length]?.focus();
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
		z-index: 40;
	}

	.menu {
		position: fixed;
		z-index: 41;
		display: flex;
		flex-direction: column;
		min-width: 176px;
		max-width: min(320px, 80vw);
		max-height: 44vh;
		overflow-y: auto;
		padding: calc(var(--space) * 1.25);
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
