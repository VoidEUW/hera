<script lang="ts">
	/**
	 * The ocellus (the theme's `hera/ocellus`): a single peacock eye — brass ring, laurel iris,
	 * a ground pupil with a highlight across it. The one mark the interface is remembered by.
	 *
	 * Argus Panoptes had a hundred eyes and never slept; when he was killed, Hera set them into
	 * the peacock's tail so she would still see everything. Three sizes, three jobs: 20–28 px is
	 * identity, 16–22 px is her thinking (`Thinking` pulses it), 8 px is one eye in the gutter.
	 * Nothing else in the interface may use concentric circles.
	 *
	 * `closed` is the eye shut — a lid and three lashes under the ring — for the offline page.
	 * `tone` is how an error page bends the same mark: a server fault reddens the iris, a missing
	 * page dims the whole eye, an unreachable model breaks the ring.
	 */
	interface Props {
		size?: number;
		/** The eye shut: offline. */
		closed?: boolean;
		/** Pulse in scale (`thinking.loop`). `Thinking` sets it; nothing else should. */
		pulse?: boolean;
		tone?: 'server' | 'missing' | 'model';
		/** The accessible name. Omitted, the mark is decoration. */
		title?: string;
	}

	let { size = 22, closed = false, pulse = false, tone, title }: Props = $props();
</script>

<svg
	class="ocellus {tone ?? ''}"
	class:pulse
	class:closed
	viewBox="-12 -12 24 24"
	width={size}
	height={size}
	role={title ? 'img' : 'presentation'}
	aria-label={title}
	aria-hidden={title ? undefined : 'true'}
>
	<circle class="ring" r="9" />
	{#if closed}
		<path class="lid" d="M-5.6 -0.6Q0 4.6 5.6 -0.6" />
		<path class="lash" d="M-3.6 2.4l-1.2 2.2M0 3.4v2.5M3.6 2.4l1.2 2.2" />
	{:else}
		<circle class="iris" r="5.4" />
		<path class="highlight" d="M-3.6 -1.8A4 4 0 0 1 1.6 -3.8" />
		<circle class="pupil" r="2" />
	{/if}
</svg>

<style>
	.ocellus {
		display: block;
		flex: none;
		overflow: visible;
	}

	.ring {
		fill: none;
		stroke: var(--brass);
		stroke-width: 2.4;
	}

	.iris {
		fill: var(--laurel);
	}

	.highlight {
		fill: none;
		stroke: var(--ground);
		stroke-opacity: 0.45;
		stroke-width: 1.3;
		stroke-linecap: round;
	}

	.pupil {
		fill: var(--ground);
	}

	/* `thinking.loop`, the pulse preset: the still eye breathes in scale. */
	.pulse {
		transform-origin: center;
		animation: pulse var(--motion-thinking-loop) infinite;
	}

	@keyframes pulse {
		0%,
		100% {
			transform: scale(0.55);
			opacity: 0.35;
		}
		50% {
			transform: scale(1);
			opacity: 1;
		}
	}

	.closed .ring {
		opacity: 0.5;
	}

	.lid,
	.lash {
		fill: none;
		stroke: var(--brass);
		stroke-linecap: round;
	}

	.lid {
		stroke-width: 2;
	}

	.lash {
		stroke-width: 1.4;
		opacity: 0.8;
	}

	.server .iris {
		fill: var(--danger);
	}

	.missing {
		opacity: 0.45;
	}

	.model .ring {
		stroke-dasharray: 4 3;
	}

	/* Reduced motion: the eye shows still and whole, never frozen mid-pulse at a third. */
	@media (prefers-reduced-motion: reduce) {
		.pulse {
			animation: none;
		}
	}
</style>
