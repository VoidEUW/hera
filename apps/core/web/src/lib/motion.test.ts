/**
 * The half of `$lib/motion` that has behaviour without a DOM: turning a theme's motion slot into
 * a duration and an easing function a Svelte transition can run on.
 */

import { describe, expect, it } from 'vitest';

import { cubicBezier, parseSlot, slot } from './motion';

describe('cubicBezier', () => {
	it('starts at rest and ends at rest', () => {
		const ease = cubicBezier(0.2, 0.7, 0.2, 1);
		expect(ease(0)).toBe(0);
		expect(ease(1)).toBe(1);
	});

	it('is the identity when both handles sit on the diagonal', () => {
		const linear = cubicBezier(0.25, 0.25, 0.75, 0.75);
		for (const t of [0.1, 0.33, 0.5, 0.9]) expect(linear(t)).toBeCloseTo(t, 5);
	});

	it("agrees with CSS's own `ease` at the midpoint", () => {
		// The browser's `ease` is cubic-bezier(0.25, 0.1, 0.25, 1); its value at x = 0.5 is the
		// textbook 0.8024.
		expect(cubicBezier(0.25, 0.1, 0.25, 1)(0.5)).toBeCloseTo(0.8024, 3);
	});

	it('lets a spring overshoot, which is what makes it a spring', () => {
		const spring = cubicBezier(0.3, 1.35, 0.6, 1);
		const peak = Math.max(...Array.from({ length: 99 }, (_, i) => spring((i + 1) / 100)));
		expect(peak).toBeGreaterThan(1);
	});

	it('only ever moves forward for a curve whose x handles stay inside [0, 1]', () => {
		const emphasized = cubicBezier(0.6, 0, 0.3, 1);
		let last = 0;
		for (let i = 1; i <= 100; i++) {
			const value = emphasized(i / 100);
			expect(value).toBeGreaterThanOrEqual(last - 1e-9);
			last = value;
		}
	});
});

describe('parseSlot', () => {
	it('reads a slot the way the computed style spells it', () => {
		const parsed = parseSlot(' 330ms cubic-bezier(0.2, 0.7, 0.2, 1)');
		expect(parsed?.duration).toBe(330);
		expect(parsed?.easing(0.5)).toBeCloseTo(cubicBezier(0.2, 0.7, 0.2, 1)(0.5), 6);
	});

	it('reads seconds as well as milliseconds', () => {
		expect(parseSlot('1.54s linear')?.duration).toBe(1540);
	});

	it('takes a keyword curve at its CSS definition', () => {
		expect(parseSlot('200ms ease-out')?.easing(0.5)).toBeCloseTo(
			cubicBezier(0, 0, 0.58, 1)(0.5),
			6
		);
	});

	it('runs linearly when no curve is named', () => {
		expect(parseSlot('120ms')?.easing(0.3)).toBeCloseTo(0.3, 6);
	});

	it('is null for something that is not a slot', () => {
		expect(parseSlot('')).toBeNull();
		expect(parseSlot('auto')).toBeNull();
	});
});

describe('slot', () => {
	it('answers with the fallback where there is no document to ask', () => {
		const fallback = { duration: 123, easing: (t: number) => t };
		expect(slot('menu-enter', fallback)).toBe(fallback);
	});
});
