/**
 * `Placeholder` — the floor, which is the only part of the loading pattern that has behaviour
 * rather than markup, and the part that decides whether anybody ever sees it.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FLOOR, Placeholder } from './loading.svelte';

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('Placeholder', () => {
	it('is up on the frame it is constructed, when that frame is already loading', () => {
		// The first render happens before the first effect. A placeholder that waits for the
		// effect has let the empty state through in the frame between them.
		expect(new Placeholder(true).shown).toBe(true);
		expect(new Placeholder(false).shown).toBe(false);
	});

	it('appears the moment loading starts, with no delay to beat', () => {
		const placeholder = new Placeholder();
		placeholder.set(true);

		expect(placeholder.shown).toBe(true);
	});

	it('stays up for the floor even when the load has already finished', () => {
		// The case that matters: a server on the same machine answers in a frame or two, and
		// without the floor the shape of the list would never be on screen long enough to read.
		const placeholder = new Placeholder(true);
		placeholder.set(false);
		expect(placeholder.shown).toBe(true);

		vi.advanceTimersByTime(FLOOR - 10);
		expect(placeholder.shown).toBe(true);

		vi.advanceTimersByTime(10);
		expect(placeholder.shown).toBe(false);
	});

	it('goes down at once when the load took longer than the floor', () => {
		const placeholder = new Placeholder(true);
		vi.advanceTimersByTime(FLOOR + 1000);

		placeholder.set(false);
		expect(placeholder.shown).toBe(false);
	});

	it('does not restart the floor when the loading flag is set to what it already is', () => {
		const placeholder = new Placeholder(true);
		vi.advanceTimersByTime(FLOOR - 10);
		// An effect re-running is not a new load.
		placeholder.set(true);
		placeholder.set(false);
		vi.advanceTimersByTime(10);

		expect(placeholder.shown).toBe(false);
	});

	it('drops a pending timer on stop', () => {
		const placeholder = new Placeholder(true);
		placeholder.set(false);
		placeholder.stop();

		vi.advanceTimersByTime(FLOOR * 4);
		// Still up, because nothing is left to take it down -- which is what teardown means.
		expect(placeholder.shown).toBe(true);
	});
});
