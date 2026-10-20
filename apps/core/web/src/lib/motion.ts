import { cubicOut, expoIn } from 'svelte/easing';

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

/** One motion slot, resolved: what `--motion-<name>` says, as numbers a transition can use. */
export interface Slot {
	duration: number;
	easing: (t: number) => number;
}

const NAMED: Record<string, [number, number, number, number]> = {
	ease: [0.25, 0.1, 0.25, 1],
	'ease-in': [0.42, 0, 1, 1],
	'ease-out': [0, 0, 0.58, 1],
	'ease-in-out': [0.42, 0, 0.58, 1]
};

/**
 * CSS's `cubic-bezier()` as a function of progress, so a Svelte transition can run on the curve
 * a theme names. Solved for x with Newton's method and finished by bisection where the slope is
 * too flat for Newton to converge; y is free to leave [0, 1], which is what a spring overshoot is.
 */
export function cubicBezier(x1: number, y1: number, x2: number, y2: number): (t: number) => number {
	const cx = 3 * x1;
	const bx = 3 * (x2 - x1) - cx;
	const ax = 1 - cx - bx;
	const cy = 3 * y1;
	const by = 3 * (y2 - y1) - cy;
	const ay = 1 - cy - by;
	const x = (u: number) => ((ax * u + bx) * u + cx) * u;
	const y = (u: number) => ((ay * u + by) * u + cy) * u;
	const slope = (u: number) => (3 * ax * u + 2 * bx) * u + cx;

	return (t: number) => {
		if (t <= 0) return 0;
		if (t >= 1) return 1;
		let u = t;
		for (let i = 0; i < 8; i++) {
			const error = x(u) - t;
			if (Math.abs(error) < 1e-6) return y(u);
			const d = slope(u);
			if (Math.abs(d) < 1e-6) break;
			u -= error / d;
		}
		let lo = 0;
		let hi = 1;
		u = t;
		for (let i = 0; i < 40 && hi - lo > 1e-7; i++) {
			if (x(u) < t) lo = u;
			else hi = u;
			u = (lo + hi) / 2;
		}
		return y(u);
	};
}

/** Parse the computed value of a motion slot — `330ms cubic-bezier(0.2, 0.7, 0.2, 1)`, `1.5s
 *  linear` — or `null` if it is not one. */
export function parseSlot(value: string): Slot | null {
	const duration = /(-?[\d.]+)(ms|s)\b/.exec(value);
	if (!duration) return null;
	const ms = Number(duration[1]) * (duration[2] === 's' ? 1000 : 1);
	const bezier = /cubic-bezier\(([^)]+)\)/.exec(value);
	if (bezier) {
		const [a, b, c, d] = bezier[1].split(',').map(Number);
		return { duration: ms, easing: cubicBezier(a, b, c, d) };
	}
	const named = Object.keys(NAMED)
		.sort((p, q) => q.length - p.length)
		.find((name) => new RegExp(`(^|\\s)${name}(\\s|$)`).test(value));
	if (named) return { duration: ms, easing: cubicBezier(...NAMED[named]) };
	return { duration: ms, easing: (t: number) => t };
}

/**
 * The theme's slot `--motion-<name>` (ADR 21), read off the root element where the theme
 * declares it. A transition that runs in JavaScript cannot say `var(--motion-…)`, so this is how
 * it asks the same question a stylesheet does. `fallback` is for a document with no theme loaded,
 * which in practice means a unit test.
 */
export function slot(name: string, fallback: Slot = { duration: 200, easing: cubicOut }): Slot {
	if (typeof document === 'undefined') return fallback;
	const value = getComputedStyle(document.documentElement).getPropertyValue(`--motion-${name}`);
	return parseSlot(value) ?? fallback;
}

/** How much quicker a close is than its open: a hand reaches further than it lets go. */
export const LEAVING = 0.7;

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
	/** The motion slot the gesture runs on. `menu-enter` unless the caller is something else — a
	 * dialog is `modal-enter`, a docked panel `drawer-open`. */
	slot?: string;
}

/**
 * Hera's one "something opens or closes" gesture, parameterised rather than reimplemented per
 * component — every primitive that arrives or leaves the screen (`Select.svelte`'s popup,
 * `Modal.svelte`'s sheet) uses this, so a person reads them as the same event happening at
 * different scales rather than as several unrelated animators. A dropdown or an edge-docked
 * sheet travels (`y`) and softens through a light blur; a centred dialog has no edge to travel
 * from and grows into place (`scale`) instead. The duration and the arriving curve are the
 * theme's slot (`params.slot`); leaving takes `LEAVING` of the duration, so every gesture opens a
 * little slower than it closes, the way a hand reaches further than it lets go.
 *
 * Leaving always runs on `expoIn`, picked from `options.direction` rather than left for every
 * call site to remember — the arriving curve and the leaving one are *not* interchangeable.
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
	// `0` for the reason `disclose` gives, and because this is the one the CSS override cannot
	// reach: a `transition:` is turned off by `prefers-reduced-motion` for free, and a Svelte
	// transition is a rAF loop that never asks. `reveal` backs `Modal` and `Select`, so without
	// this every sheet and every dropdown in the interface still slid for 220 ms with motion off,
	// against what `docs/frontend.md` says in as many words.
	if (still()) return { duration: 0 };

	const { y = 0, scale = 1, blur = 0 } = params;
	const motion = slot(params.slot ?? 'menu-enter');
	const leaving = options.direction === 'out';
	return {
		duration: leaving ? motion.duration * LEAVING : motion.duration,
		easing: leaving ? expoIn : motion.easing,
		// A spring slot overshoots, so `t` passes 1 and `u` goes below 0 for a moment. That is the
		// point for travel and scale; opacity and blur have no meaning past their ends — a negative
		// blur is an invalid keyframe the browser warns about and drops — so they are clamped.
		css: (t: number, u: number) =>
			`transform: translateY(${u * y}px) scale(${1 - u * (1 - scale)});` +
			`opacity: ${Math.min(1, Math.max(0, t))};` +
			(blur ? `filter: blur(${Math.max(0, u * blur)}px);` : '')
	};
}

export interface DiscloseParams {
	/** `collapse-disclose` unless the panel belongs to something with its own slot, like the
	 * activity trace (`trace-disclose`). */
	slot?: string;
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
export function disclose(
	_node: Element,
	params: DiscloseParams = {},
	options: { direction?: 'in' | 'out' | 'both' } = {}
) {
	// `0` rather than a short duration: with motion off this is not a faster animation, it is the
	// state change happening, and the caller should not have to know that a transition existed.
	if (still()) return { duration: 0 };

	const { delay = 0 } = params;
	const motion = slot(params.slot ?? 'collapse-disclose');
	const duration = options.direction === 'out' ? motion.duration * LEAVING : motion.duration;
	const easing = motion.easing;
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
