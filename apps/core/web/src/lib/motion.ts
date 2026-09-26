import { cubicOut, expoIn, expoOut } from 'svelte/easing';

/** Whether the reader has asked for the interface not to move.
 *
 * A transition directive is JavaScript writing inline styles, or a Web Animations entry the
 * browser owns, and the global `prefers-reduced-motion` block in `app.css` collapses
 * `transition-duration` and `animation-duration` — neither of which is what either of those is.
 * So the question has to be asked here, once, rather than answered in every transition: with motion
 * off, `0` is a real answer and the state change simply happens. */
export function still(): boolean {
	return matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export interface RevealParams {
	/** Vertical travel in pixels at the fully-hidden end — positive arrives from below,
	 * negative from above. `0` for a control with no edge of its own to travel from, like a
	 * centred dialog. */
	y?: number;
	/** The scale the fully-hidden end sits at. `1` (the default) is no scaling at all — an
	 * edge-anchored panel moves rather than grows; a centred dialog wants a `y` of `0` and a
	 * `scale` under `1` instead. */
	scale?: number;
	/** Blur in pixels at the fully-hidden end, softening a short travel enough that it still
	 * reads as a full arrival rather than a slide. `0` for none. */
	blur?: number;
	duration?: number;
	easing?: (t: number) => number;
}

/**
 * Hera's one "something opens or closes" gesture, parameterised rather than reimplemented per
 * component — every primitive that arrives or leaves the screen (`Select.svelte`'s popup,
 * `Modal.svelte`'s sheet) uses this, so a person reads them as the same event happening at
 * different scales rather than as several unrelated animators. A dropdown or an edge-docked
 * sheet travels (`y`) and softens through a light blur; a centred dialog has no edge to travel
 * from and grows into place (`scale`) instead. Pass different `duration`s to `in:`/`out:` for a
 * gesture that opens a little slower than it closes, the way a hand reaches further than it
 * lets go.
 *
 * The easing defaults to `expoOut` arriving and `expoIn` leaving, picked from `options.direction`
 * rather than left for every call site to remember — and the two are *not* interchangeable.
 * Svelte's own outro math turns an arriving-style curve (fast start, long gentle settle) into,
 * once run in reverse, an element that sits fully visible for most of its `out:` duration and
 * only fades in the last sliver of it — a close that looks like it never started until it
 * suddenly ends. `expoIn` (slow start, fast finish) is the mirror image: read forwards it
 * describes an arrival nobody would want, but reversed by the same outro math it spends most of
 * the duration visibly fading and only settles at the very end, which is the close that
 * actually reads as one.
 */
export function reveal(
	_node: Element,
	params: RevealParams = {},
	options: { direction?: 'in' | 'out' | 'both' } = {}
) {
	const {
		y = 0,
		scale = 1,
		blur = 0,
		duration = 220,
		easing = options.direction === 'out' ? expoIn : expoOut
	} = params;
	return {
		duration,
		easing,
		css: (t: number, u: number) =>
			`transform: translateY(${u * y}px) scale(${1 - u * (1 - scale)});` +
			`opacity: ${t};` +
			(blur ? `filter: blur(${u * blur}px);` : '')
	};
}

export interface DiscloseParams {
	duration?: number;
	easing?: (t: number) => number;
	delay?: number;
}

/**
 * The other sanctioned gesture: a panel that **opens and closes** rather than arriving.
 *
 * `docs/frontend.md` § Motion allows exactly two things besides the ocellus — a 120 ms fade and a
 * 160 ms disclosure height — and this is the second one, which until now existed only as the
 * `--disclose` token and had no implementation behind it anywhere in the interface. Use it for a
 * `{#if}` that grows or shrinks its container: a reasoning panel opening in the activity gutter, a
 * project's chats being disclosed in the rail.
 *
 * **A height, not a slide.** The container is part of a column of other things, so what a person
 * needs to see is the column rearranging itself rather than a box sliding past its neighbours —
 * and `reveal`'s `translateY` is the gesture for something that is *arriving from an edge*, which
 * an inline panel in the middle of a list has no edge of. Opening slower than closing for the same
 * reason `reveal` does: a hand reaches further than it lets go.
 *
 * The height is measured rather than assumed, and measured at the moment the transition is asked
 * for — which is the only moment the node is in the document at its natural size. Svelte hands the
 * same function both directions: on the way in the node has just been created, and on the way out
 * it has not been removed yet, so one `getBoundingClientRect()` answers both.
 */
export function disclose(_node: Element, params: DiscloseParams = {}) {
	// `0` rather than a short duration: with motion off this is not a faster animation, it is the
	// state change happening, and the caller should not have to know that a transition existed.
	if (still()) return { duration: 0 };

	const { duration = 160, easing = cubicOut, delay = 0 } = params;
	// `floor`, because a fractional pixel target rounds up on the way in and leaves a sub-pixel gap
	// under the content at the end of the animation.
	const height = Math.floor(_node.getBoundingClientRect().height);
	return {
		delay,
		duration,
		easing,
		// `overflow: hidden` for the length of it. Without it the content is visible outside the box
		// being measured down towards zero, so a panel being closed shows every one of its lines
		// squeezing into a shorter box instead of being covered by the edge arriving.
		css: (t: number) => `height: ${t * height}px; overflow: hidden;`
	};
}
