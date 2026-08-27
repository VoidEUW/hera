<script lang="ts">
	/**
	 * A tool ran here.
	 *
	 * The gutter is Hera's hundred eyes — a skill she was given and a thought she had are both
	 * things she *saw*, and they keep the ocellus. A tool call is not that: it is something she
	 * reached for and it happened outside her. A wrench says so in the one visual language
	 * everybody already reads, which is worth more here than another eye would be.
	 *
	 * Drawn rather than an emoji: 🔧 is loud, renders differently on every platform, and is the
	 * one glyph on screen that would not be ours.
	 */
	interface Props {
		size?: number;
		/** Still running: the same breathing the ocellus does, so a busy row reads as busy. */
		alive?: boolean;
		muted?: boolean;
	}

	let { size = 12, alive = false, muted = false }: Props = $props();
</script>

<svg
	class="wrench"
	class:alive
	class:muted
	width={size}
	height={size}
	viewBox="0 0 16 16"
	fill="none"
	stroke="currentColor"
	stroke-width="1.6"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
>
	<path
		d="M10.4 1.9a3.9 3.9 0 0 0-4.1 5.7L2 11.9l2.1 2.1 4.3-4.3a3.9 3.9 0 0 0 5.7-4.1l-2.3 2.3-2-.6-.6-2z"
	/>
</svg>

<style>
	.wrench {
		display: block;
		color: var(--laurel);
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
