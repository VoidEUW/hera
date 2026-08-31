<script lang="ts">
	/**
	 * She wrote something down.
	 *
	 * `hera__note` today, the per-chat scratchpad when it lands (`docs/tooling.md` § 2). Both are
	 * the same act to a reader — *she put something somewhere it will still be later* — and that
	 * is the distinction worth drawing in a gutter, not which tool carried it.
	 *
	 * Brass rather than laurel, because it belongs with the scroll: reading her instructions and
	 * writing her working out are two halves of the same thing, and the colour says so before the
	 * shape does. `remember` is deliberately *not* this — see `Brain.svelte`.
	 */
	interface Props {
		size?: number;
		alive?: boolean;
		muted?: boolean;
	}

	let { size = 13, alive = false, muted = false }: Props = $props();
</script>

<svg
	class="quill"
	class:alive
	class:muted
	width={size}
	height={size}
	viewBox="0 0 16 16"
	fill="none"
	stroke="currentColor"
	stroke-width="1.4"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
>
	<!-- The nib, and the line it is resting on. Two strokes: any more detail disappears at
	     13 px and comes back as noise on a display that doubles it. -->
	<path d="M13.4 2.6c-4.6.4-7.5 2.6-8.6 6.6l2 2c4-1.1 6.2-4 6.6-8.6z" />
	<path d="M4.8 11.2 2.4 13.6" />
	<path d="M2.2 13.8h11.6" />
</svg>

<style>
	.quill {
		display: block;
		color: var(--brass);
	}

	.muted {
		color: var(--text-faint);
	}

	.alive {
		animation: breathe 4s var(--ease) infinite;
	}

	@keyframes breathe {
		0%,
		100% {
			opacity: 0.6;
		}
		50% {
			opacity: 1;
		}
	}
</style>
