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
		/** Dim it, for a row that has already finished. */
		muted?: boolean;
		title?: string;
	}

	let { size = 16, alive = false, muted = false, title }: Props = $props();
</script>

<span
	class="ocellus"
	class:alive
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
		.alive .ring {
			animation: none;
			opacity: 1;
		}
	}
</style>
