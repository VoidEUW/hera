import { expoIn, expoOut } from 'svelte/easing';

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
