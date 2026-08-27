<script lang="ts">
	/**
	 * She looked outside.
	 *
	 * The one mark in the gutter that means *this left the machine*. Everything else she does —
	 * reading a skill, writing a note, having a thought — happens inside a self-hosted box on
	 * somebody's desk, and a person watching a turn should be able to see the moment that stops
	 * being true without reading the row.
	 *
	 * So a globe, and not a magnifying glass. A glass would say "she looked something up", which
	 * is the smaller and less interesting half of it.
	 */
	interface Props {
		size?: number;
		alive?: boolean;
		muted?: boolean;
	}

	let { size = 13, alive = false, muted = false }: Props = $props();
</script>

<svg
	class="globe"
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
	<circle cx="8" cy="8" r="6.1" />
	<path d="M1.9 8h12.2" />
	<!-- The meridian, drawn as two arcs rather than an ellipse: at 13 px an ellipse's sides
	     land on the circle and the whole thing reads as a solid disc. -->
	<path d="M8 1.9a9.3 9.3 0 0 1 0 12.2" />
	<path d="M8 1.9a9.3 9.3 0 0 0 0 12.2" />
</svg>

<style>
	.globe {
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
