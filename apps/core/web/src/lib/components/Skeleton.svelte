<script lang="ts">
	/**
	 * The shape of something that has not arrived yet: a few bars where its rows will be.
	 *
	 * Height is the whole point. A screen that draws nothing while it waits and then drops a
	 * list into place has moved everything under it; a block of the right height has not. So the
	 * caller says how many rows and how tall, because it is the one that knows what is coming.
	 *
	 * Purely presentational — *when* to draw one is `Placeholder` in `$lib/loading.svelte`, and
	 * keeping the two apart is what lets the timing be tested without a DOM.
	 *
	 * **It has to know what it is lying on.** A bar is `--surface-raised` on `--ground`, which is
	 * one step up from the room — and inside a sheet that is *already* `--surface-raised` it is
	 * the same colour as its background and cannot be seen at all. So the tone is a custom
	 * property: set `--skeleton-bar` (and `--skeleton-sheen`, which the shimmer mixes from) on
	 * an ancestor to take the same step up from wherever this one is standing.
	 *
	 * Not a spinner, and deliberately not the ocellus either. The mark is the one choreographed
	 * thing in the interface and it means *she is thinking*; a list arriving over the network is
	 * not her thinking, and borrowing the gesture for it would spend the only piece of motion
	 * this interface has on plumbing.
	 */
	interface Props {
		/** How many bars to draw. */
		rows?: number;
		/** Bar height in px. With the 16px gap below it, 15 makes a 31px row — a rail entry. */
		height?: number;
		/** Space between bars in px. With `height`, this is the row pitch of whatever is coming:
		 * 15 and 16 is a rail entry, 16 and 9 is a line of her prose. */
		gap?: number;
		/** Percent widths, cycled over the rows, so the block reads as titles of different
		 * lengths rather than as one grey rectangle. */
		widths?: number[];
		/** What is loading, read out rather than drawn — bars of grey say nothing to anybody who
		 * is not looking at them. Leave it off when the skeleton sits inside something that
		 * already announces itself: it then carries no role at all, rather than a second one
		 * talking over the first. */
		label?: string;
	}

	let { rows = 3, height = 15, gap = 16, widths = [86, 60, 74], label }: Props = $props();
</script>

<div
	class="skeleton"
	role={label ? 'status' : undefined}
	aria-busy={label ? 'true' : undefined}
	aria-label={label}
	aria-hidden={label ? undefined : 'true'}
	style:gap="{gap}px"
>
	{#each { length: rows }, index (index)}
		<span class="bar" style:height="{height}px" style:width="{widths[index % widths.length]}%"
		></span>
	{/each}
</div>

<style>
	.skeleton {
		display: flex;
		flex-direction: column;
		animation: fade var(--fade) var(--ease);
	}

	/* Half the interface's radius rather than all of it. A 15px bar with a 10px corner is a
	   capsule, and a capsule is a chip — the wrong promise about what is arriving. A line of
	   text is what is arriving. */
	.bar {
		position: relative;
		overflow: hidden;
		border-radius: 6px;
		background: var(--skeleton-bar, var(--surface-raised));
	}

	/* A slow, low-contrast sweep. Mixed off the hairline rather than off white, so it reads as
	   the same material the rest of the room is made of and stays that way in both themes. The
	   1.9s is long enough to be attention rather than activity — the same reasoning the
	   ocellus's four-second cycle is written down under. */
	.bar::after {
		content: '';
		position: absolute;
		inset: 0;
		background: linear-gradient(
			90deg,
			transparent,
			color-mix(in oklab, var(--skeleton-sheen, var(--line)) 70%, transparent),
			transparent
		);
		transform: translateX(-100%);
		animation: sweep 1.9s var(--ease) infinite;
	}

	@keyframes fade {
		from {
			opacity: 0;
		}
	}

	@keyframes sweep {
		to {
			transform: translateX(100%);
		}
	}

	/* The global reduced-motion block only collapses the duration, which would park the sweep at
	   its end state with the gradient half across the bar. Off means off: the bars stay, still. */
	@media (prefers-reduced-motion: reduce) {
		.bar::after {
			display: none;
		}
	}
</style>
