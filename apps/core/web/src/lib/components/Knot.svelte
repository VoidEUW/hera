<script lang="ts">
	/**
	 * She committed something to memory.
	 *
	 * `hera__remember`, and only that. A knot in a handkerchief is the oldest mnemonic there is
	 * and it is the one picture nobody has to be taught — which matters here, because *storing a
	 * fact about you* is the one thing she does that a person most deserves to notice.
	 *
	 * Kept apart from the quill on purpose. Writing a note is a document you asked for; a memory
	 * is something she decided to keep about you, and drawing them the same way would hide the
	 * difference the tool descriptions work hardest to establish.
	 */
	interface Props {
		size?: number;
		alive?: boolean;
		muted?: boolean;
	}

	let { size = 13, alive = false, muted = false }: Props = $props();
</script>

<svg
	class="knot"
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
	<!-- A thread tied once: the loop, and the two ends left hanging. Two ends and not four —
	     four lines through a circle stop being a knot at this size and become an asterisk. -->
	<circle cx="8" cy="5.9" r="2.7" />
	<path d="M6.1 7.9 3.1 13.2" />
	<path d="M9.9 7.9 12.9 13.2" />
</svg>

<style>
	.knot {
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
