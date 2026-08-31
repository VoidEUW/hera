<script lang="ts">
	/**
	 * She published something.
	 *
	 * The three `hera__artifact_*` calls (ADR 13). A **stele** is a slab set up in public with
	 * something written on it — which is precisely what an artifact is and what the scratchpad is
	 * not: the quill is *she wrote something down where only she will read it*, and this is *she
	 * put something up where you can*.
	 *
	 * All three calls share it, the way all three scratchpad calls share the quill: publishing a
	 * page, changing a line of it and reading it back are one habit to a reader, and splitting
	 * them would put three marks in the gutter for one act.
	 *
	 * Brass, because it belongs with the scroll and the quill — the things she makes and reads.
	 */
	interface Props {
		size?: number;
		alive?: boolean;
		muted?: boolean;
	}

	let { size = 13, alive = false, muted = false }: Props = $props();
</script>

<svg
	class="stele"
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
	<!-- The slab: a round-topped stone standing on a base. Two lines of writing across it and no
	     more — a third reads as hatching at 13 px, and the top one has to stay short or the
	     rounded head loses its shape. -->
	<path d="M4 13.4V6a4 4 0 0 1 8 0v7.4" />
	<path d="M2.6 13.6h10.8" />
	<path d="M6.4 6.6h3.2" />
	<path d="M6 9.6h4" />
</svg>

<style>
	.stele {
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
