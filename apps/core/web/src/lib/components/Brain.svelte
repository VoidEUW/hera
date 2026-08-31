<script lang="ts">
	/**
	 * She committed something to memory.
	 *
	 * `hera__remember` and `hera__forget` — the two calls that change what she carries into every
	 * later conversation (ADR 16). Both share it, the way the three scratchpad calls share the
	 * quill: *keeping something about you* is one habit to a reader, and splitting it would put
	 * two different marks in the gutter for one act.
	 *
	 * **Replaced a knot in a handkerchief**, which was the older mnemonic and the more literary
	 * picture, and lost to the plainer one. A knot is a promise to remember *later*; what this
	 * marks is a thing already known and already in her prompt, which is what a brain is. The
	 * settings screen carries the same mark, so the row in the gutter and the page listing what
	 * she keeps are visibly the same subject.
	 *
	 * Two mirrored hemispheres and the fissure between them, and nothing else — folds inside
	 * would be the honest drawing and at 13 px they close up into a smudge. Brass, because it
	 * belongs with the scroll, the quill and the stele: the things she makes, reads and keeps.
	 */
	interface Props {
		size?: number;
		alive?: boolean;
		muted?: boolean;
	}

	let { size = 13, alive = false, muted = false }: Props = $props();
</script>

<svg
	class="brain"
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
	<!-- Two hemispheres and the fissure between them. The scallops on the outline are the whole
	     of what makes this read as a brain rather than as a coin with a line scored across it —
	     and they are *exaggerated* on purpose: the first draft had subtle lobes that rasterised
	     away entirely at 13 px, which is the only size the gutter ever draws this at. No folds
	     inside; they are the honest drawing and at 13 px they close into a smudge. -->
	<path d="M8 3a2 2 0 0 0-3.1 1.3A1.9 1.9 0 0 0 2.8 7a2 2 0 0 0 .6 3A2 2 0 0 0 8 12.9" />
	<path d="M8 3a2 2 0 0 1 3.1 1.3A1.9 1.9 0 0 1 13.2 7a2 2 0 0 1-.6 3A2 2 0 0 1 8 12.9" />
	<path d="M8 3v9.9" />
</svg>

<style>
	.brain {
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
