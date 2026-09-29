<script module lang="ts">
	/** How long the tail takes to draw back into the eye, in milliseconds. Exported because the
	 *  caller owns the unmount: whoever sets `folding` has to keep the mark on screen exactly
	 *  this long, and a second copy of the number in a stylesheet would drift from it. */
	export const FOLD_MS = 460;
</script>

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
	 * did. The waiting mark is the one that steps outside it at 22 px — it is the only thing on
	 * screen while it is up, and at 16 px a fanned tail is a smudge rather than a tail. Nothing
	 * else in the interface may use concentric circles.
	 */
	interface Props {
		size?: number;
		/** Rotate the iris and breathe the ring. Her thinking indicator, and only that. */
		alive?: boolean;
		/** Fan the tail: the eye swells, feathers throw outward, everything springs back. The
		 *  waiting state before her first word. */
		burst?: boolean;
		/** Her words have started. The tail draws back into the eye from wherever it had got to
		 *  and goes out; the caller unmounts the mark once it has. */
		folding?: boolean;
		/** Dim it, for a row that has already finished. */
		muted?: boolean;
		title?: string;
	}

	let {
		size = 16,
		alive = false,
		burst = false,
		folding = false,
		muted = false,
		title
	}: Props = $props();

	/** Eight feathers, evenly around the circle: enough to read as a tail, few enough to stay
	    legible at 16 px. Static angles rather than a stagger — a ripple travelling around the
	    ring is the spinner this is meant not to be. */
	const PLUMES = [0, 45, 90, 135, 180, 225, 270, 315];
</script>

<span
	class="ocellus"
	class:alive
	class:burst
	class:folding
	class:muted
	style="--size: {size}px; --fold-ms: {FOLD_MS}ms"
	role={title ? 'img' : 'presentation'}
	aria-label={title}
>
	<!-- The bursting variant keeps the eye at its usual pixel size and doubles the box around
	     it, so a fanned feather has somewhere to go instead of being cropped at the widest
	     moment of the animation. -->
	<svg
		viewBox={burst ? '-12 -12 48 48' : '0 0 24 24'}
		width={burst ? size * 2 : size}
		height={burst ? size * 2 : size}
		aria-hidden="true"
	>
		{#if burst}
			<!-- Drawn before the eye, so they throw out from behind it rather than across it: at
			     rest each one is collapsed into the middle, hidden under the opaque ground disc.

			     Three nested groups because three things move independently and each owns one
			     transform: `plumes` turns the whole fan, `fold` draws it back in when her words
			     arrive, and each `plume` throws itself outward. Collapsing any two of them into
			     one element would mean two animations writing `transform`, where the last one
			     simply wins. -->
			<g class="plumes">
				<g class="fold">
					{#each PLUMES as angle (angle)}
						<g transform="rotate({angle} 12 12)">
							<g class="plume">
								<path class="vane" d="M12 1.5 C 14.7 5 14.7 9 12 12 C 9.3 9 9.3 5 12 1.5 Z" />
								<circle class="spot" cx="12" cy="5.6" r="1.35" />
								<path class="shaft" d="M12 12 V 3.4" />
							</g>
						</g>
					{/each}
				</g>
			</g>
		{/if}
		<g class="eye">
			<!-- outer ground, so it sits on any surface -->
			<circle cx="12" cy="12" r="11.5" class="ground" />
			<!-- brass: her authority -->
			<circle cx="12" cy="12" r="9.5" class="ring" />
			<!-- laurel: her attention -->
			<circle cx="12" cy="12" r="6.5" class="iris" />
			<!-- the pupil is the ground colour, punched through -->
			<circle cx="12" cy="12" r="2.6" class="pupil" />
		</g>
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

	/* The doubled box is pulled back to the size everything else lays out against, so a fanning
	   tail bleeds over its neighbours instead of pushing the line apart. */
	.burst svg {
		flex: none;
		margin: calc(var(--size) / -2);
	}

	.ground {
		fill: var(--surface);
	}

	.ring {
		fill: none;
		stroke: var(--brass);
		stroke-width: 1.6;
		opacity: 0.95;
		/* A tool finishing is a state change, and the ring is what reports it: the row goes from
		   saying *she is doing this* to saying *she did this*, and the only thing on screen that
		   says so is these two colours. Without the transition the whole gutter report lands as a
		   single frame, once per tool call, which is the loudest way to say something quiet.

		   On `stroke` here and `fill` on the iris below rather than on a `color` the six other
		   gutter marks transition, because an SVG's `fill` and `stroke` do not read `currentColor`
		   here — the ring and iris are set explicitly so that `.muted` can move them to colours of
		   their own. */
		transition: stroke var(--fade) var(--ease);
	}

	.iris {
		fill: var(--laurel);
		transform-origin: 50% 50%;
		transition: fill var(--fade) var(--ease);
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

	/* Under `burst` the beat becomes a display: the eye swells, eight feathers throw outward past
	   where they settle, and the whole thing springs back through its resting size before the next
	   one. Used only by the empty waiting state — the gutter eyes keep the plain look.

	   Shorter than the four seconds the settled state runs on, and it has to be. A display is one
	   gesture with a beginning and an end, so whatever is left over after it finishes is a still
	   circle; the way to have less of that is to come round again sooner, not to find something to
	   fill it with. An earlier version filled it — the mark dimmed and came back up between throws
	   — and a blink sitting next to a gesture this smooth read as a different animation borrowed
	   from somewhere else. */
	.burst {
		--beat: 2.4s;
	}

	/* `ease-in-out` rather than the interface's usual ease-out, because this one loops: every
	   segment has to arrive at rest and leave from rest, or the joins read as jerks. The throw is
	   the single exception and overrides it on its own keyframe. */
	.burst .eye {
		transform-origin: 12px 12px;
		animation: swell var(--beat) ease-in-out infinite;
	}

	.burst .plume {
		transform-origin: 12px 12px;
		animation: fan var(--beat) ease-in-out infinite;
	}

	/* The turn is deliberately *not* on the beat. Rotating exactly one feather's spacing per beat
	   looks seamless in isolation and is the reason the fan appeared to snap back: every throw
	   sampled the same 45° arc, so the tail came out at the angle the last one started from and
	   the drift that happened while it was folded away was invisible. An interval that does not
	   divide into the beat means each display picks up further round than the last, which is what
	   a turn that never stopped actually looks like. The keyframe still spans exactly 45°, so the
	   rotation itself remains seamless — eight blades 45° apart are the same eight turned 45°. */
	.burst .plumes {
		transform-origin: 12px 12px;
		animation: turn 3.1s linear infinite;
	}

	/* `look` rotates a plain disc, which shows nothing, and its scale would fight the swell. */
	.alive.burst .iris,
	.alive.burst .ring {
		animation: none;
	}

	/* Her words have arrived. The throw and the swell freeze where they stand and the fan is drawn
	   into the eye as one piece — pausing rather than cancelling is the whole trick, because a
	   cancelled animation snaps back to its resting value and the tail would vanish before it
	   could be pulled in. `fold` has no transform of its own, so this starts from scale(1) no
	   matter which frame of the display it interrupts. The turn is deliberately *not* paused: the
	   fan keeps rotating as it comes in, which is what makes it read as drawn rather than
	   switched off. */
	.folding .plume,
	.folding .eye {
		animation-play-state: paused;
	}

	.folding .fold {
		transform-origin: 12px 12px;
		/* Accelerating inwards, unlike everything else here, because this one is being pulled
		   rather than settling. */
		animation: fold-in var(--fold-ms) cubic-bezier(0.42, 0, 1, 1) forwards;
	}

	.plume .vane {
		fill: var(--laurel);
	}

	/* The same colour as the pupil, so every feather carries the eye it came from. */
	.plume .spot {
		fill: var(--ground);
	}

	.plume .shaft {
		fill: none;
		stroke: var(--brass);
		stroke-width: 1;
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

	/* Both halves of the display run on one set of stops, so the eye is at its widest exactly
	   while the tail is: the throw, a hold, then the fold back — and the eye carries on past its
	   resting size on the way home, which is the bounce. It spends the last fifth easing back up
	   from there, so even the quietest part of the beat is still moving.

	   The launch curve leaves from rest and overshoots, rather than the back-out it used to use.
	   A back-out starts at roughly four times its average speed, and the previous beat had just
	   finished decelerating into the loop point — so position matched across the join and velocity
	   did not, which is exactly what a jerk is. Everything here now begins and ends at a
	   standstill. */
	@keyframes swell {
		0% {
			transform: scale(1);
			animation-timing-function: cubic-bezier(0.45, 0, 0.35, 1.35);
		}
		32%,
		58% {
			transform: scale(1.16);
		}
		80% {
			transform: scale(0.96);
		}
		100% {
			transform: scale(1);
		}
	}

	@keyframes turn {
		from {
			transform: rotate(0deg);
		}
		to {
			transform: rotate(45deg);
		}
	}

	/* Only as far as 0.5, not to nothing. A feather at full stretch has its tip 20.5 units out and
	   the eye covers 11.5 of that, so every part of this gesture anybody can actually see happens
	   between 1 and about 0.56 — shrinking further is time spent animating something already
	   hidden behind the disc, which is what made an earlier, apparently longer version look like
	   the tail had simply been switched off. */
	@keyframes fold-in {
		from {
			transform: scale(1);
			opacity: 1;
		}
		70% {
			opacity: 1;
		}
		to {
			transform: scale(0.5);
			opacity: 0;
		}
	}

	@keyframes fan {
		0% {
			transform: translateY(0) scale(0.12);
			opacity: 0;
			/* The throw, on the same from-rest overshoot as the swell it happens with. */
			animation-timing-function: cubic-bezier(0.45, 0, 0.35, 1.35);
		}
		32%,
		58% {
			transform: translateY(-11px) scale(1);
			opacity: 1;
		}
		80% {
			transform: translateY(-1px) scale(0.2);
			opacity: 0;
		}
		100% {
			transform: translateY(0) scale(0.12);
			opacity: 0;
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

	/* Reduced motion gets a static ocellus at full opacity, not a missing one. The `.alive.burst`
	   pair is listed in full because the rules they have to beat are themselves two classes deep
	   — a media query does not add specificity. */
	@media (prefers-reduced-motion: reduce) {
		.alive .iris,
		.alive .ring,
		.alive.burst .iris,
		.alive.burst .ring,
		.burst .eye,
		.burst .plumes,
		.burst .plume,
		.folding .fold {
			animation: none;
		}

		.burst .plume {
			opacity: 0;
		}
	}
</style>
