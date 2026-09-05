<script lang="ts">
	/**
	 * The ocellus — a single peacock eye. The one element the interface is remembered by.
	 *
	 * Argus Panoptes had a hundred eyes and never slept; when he was killed, Hera set them into
	 * the peacock's tail so she would still see everything. The brief's strongest functional
	 * requirement is that the interface show as much as it can, and her own myth is about total
	 * visibility — so the activity gutter is not *decorated* with peacock eyes, it **is** the
	 * hundred eyes.
	 *
	 * Three sizes, three jobs: 24 px is identity, 16 px is her thinking, 8 px is one thing she
	 * did. Nothing else in the interface may use concentric circles.
	 */
	interface Props {
		size?: number;
		/** Rotate the iris and breathe the ring. Her thinking indicator, and only that. */
		alive?: boolean;
		/** Loop between feather and eye. The waiting state before her first word. */
		morph?: boolean;
		/** Dim it, for a row that has already finished. */
		muted?: boolean;
		title?: string;
	}

	let { size = 16, alive = false, morph = false, muted = false, title }: Props = $props();
</script>

<span
	class="ocellus"
	class:alive
	class:morph
	class:muted
	style="--size: {size}px"
	role={title ? 'img' : 'presentation'}
	aria-label={title}
>
	<svg viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
		<!-- outer ground, so it sits on any surface -->
		<circle cx="12" cy="12" r="11.5" class="ground" />
		<!-- brass: her authority -->
		<circle cx="12" cy="12" r="9.5" class="ring" />
		<!-- laurel: her attention -->
		<circle cx="12" cy="12" r="6.5" class="iris" />
		{#if morph}
			<!-- the feather the iris folds into while she is still without words -->
			<g class="feather">
				<path class="vane" d="M12 5.6 C 15.4 7.9 15.4 13.1 12 18.4 C 8.6 13.1 8.6 7.9 12 5.6 Z" />
				<circle class="spot" cx="12" cy="10.6" r="1.9" />
				<path class="shaft" d="M11.5 6 V 21.5" />
			</g>
		{/if}
		<!-- the pupil is the ground colour, punched through -->
		<circle cx="12" cy="12" r="2.6" class="pupil" />
	</svg>
</span>

<style>
	.ocellus {
		display: inline-flex;
		width: var(--size);
		height: var(--size);
		flex: none;
		line-height: 0;
	}

	.ground {
		fill: var(--surface);
	}

	.ring {
		fill: none;
		stroke: var(--brass);
		stroke-width: 1.6;
		opacity: 0.95;
	}

	.iris {
		fill: var(--laurel);
		transform-origin: 50% 50%;
	}

	.pupil {
		fill: var(--ground);
	}

	.muted .ring {
		stroke: var(--line);
	}

	.muted .iris {
		fill: var(--text-faint);
	}

	/* One piece of choreography in the whole interface. The iris turns once every four
	   seconds and the ring breathes on the same cycle — slow enough to read as attention
	   rather than as a spinner. */
	.alive .iris {
		animation: look 4s var(--ease) infinite;
	}

	.alive .ring {
		animation: breathe 4s ease-in-out infinite;
	}

	/* Under `morph` the same four-second cycle splits in two: the iris twists shut into a
	   petal-thin sliver that a feather fades in over, holds, then folds back into the open
	   eye as the pupil returns. Used only by the empty waiting state — the gutter eyes keep
	   the plain spinning look. */
	.morph .iris {
		animation: unfurl 4s var(--ease) infinite;
	}

	.morph .feather {
		transform-origin: 50% 50%;
		animation: plume 4s var(--ease) infinite;
	}

	.morph .pupil {
		transform-origin: 50% 50%;
		animation: close-open 4s var(--ease) infinite;
	}

	/* The waiting ocellus gets the morphism alone — no competing ring breath. */
	.alive.morph .ring {
		animation: none;
	}

	.feather .vane {
		fill: var(--laurel);
	}

	.feather .spot {
		fill: var(--ground);
	}

	.feather .shaft {
		fill: none;
		stroke: var(--brass);
		stroke-width: 1.1;
	}

	@keyframes look {
		from {
			transform: rotate(0deg) scale(1);
		}
		50% {
			transform: rotate(180deg) scale(0.92);
		}
		to {
			transform: rotate(360deg) scale(1);
		}
	}

	@keyframes unfurl {
		0%,
		22% {
			transform: rotate(0deg) scale(1);
			opacity: 1;
		}
		42%,
		58% {
			transform: rotate(120deg) scaleY(0.3);
			opacity: 0;
		}
		78%,
		100% {
			transform: rotate(360deg) scale(1);
			opacity: 1;
		}
	}

	@keyframes plume {
		0%,
		18% {
			transform: rotate(-12deg) scale(0.6);
			opacity: 0;
		}
		38%,
		62% {
			transform: rotate(4deg) scale(1);
			opacity: 1;
		}
		80%,
		100% {
			transform: rotate(12deg) scale(0.6);
			opacity: 0;
		}
	}

	@keyframes close-open {
		0%,
		24% {
			opacity: 1;
			transform: scale(1);
		}
		40%,
		60% {
			opacity: 0;
			transform: scale(0.2);
		}
		76%,
		100% {
			opacity: 1;
			transform: scale(1);
		}
	}

	@keyframes breathe {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.6;
		}
	}

	/* Reduced motion gets a static ocellus at full opacity, not a missing one. */
	@media (prefers-reduced-motion: reduce) {
		.alive .iris,
		.alive .ring,
		.morph .iris,
		.morph .feather,
		.morph .pupil {
			animation: none;
			opacity: 1;
		}

		.morph .feather {
			opacity: 0;
		}
	}
</style>
