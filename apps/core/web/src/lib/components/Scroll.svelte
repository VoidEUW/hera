<script lang="ts">
	/**
	 * A skill was read here.
	 *
	 * Skills are their own category and they look like one: a scroll, whether the router
	 * selected it before the turn or she reached for it mid-task with `hera__skill`. Those two
	 * are the same event to a reader — *she read some instructions* — and drawing the second as
	 * a wrench because it happened to arrive as a tool call was letting the plumbing decide what
	 * the picture is.
	 */
	interface Props {
		size?: number;
		alive?: boolean;
		muted?: boolean;
	}

	let { size = 12, alive = false, muted = false }: Props = $props();
</script>

<svg
	class="scroll"
	class:alive
	class:muted
	width={size}
	height={size}
	viewBox="0 0 16 16"
	fill="none"
	stroke="currentColor"
	stroke-width="1.5"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
>
	<path d="M4.4 2.2h7.1v9.4a2.2 2.2 0 0 0 2.2 2.2H5.6a2.2 2.2 0 0 1-2.2-2.2V3.2" />
	<path d="M3.4 3.2a1 1 0 0 0-2 0v1.6h2" />
	<path d="M13.7 13.8a2.2 2.2 0 0 0 .9-1.8v-1.4h-3.1" />
	<path d="M6.4 5.4h3.2M6.4 8h3.2" />
</svg>

<style>
	.scroll {
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
