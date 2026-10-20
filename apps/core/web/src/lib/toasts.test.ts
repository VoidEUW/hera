/**
 * `Toasts` — the behaviour half of `hera/toast`: a toast leaves on its own after `STAY`, and is
 * held while somebody is pointing at it so its action can be reached.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { STAY, Toasts } from './toasts.svelte';

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe('Toasts', () => {
	it('shows a toast and lets it go after STAY', () => {
		const toasts = new Toasts();
		toasts.show('Copied');
		expect(toasts.items.map((toast) => toast.message)).toEqual(['Copied']);
		vi.advanceTimersByTime(STAY - 1);
		expect(toasts.items).toHaveLength(1);
		vi.advanceTimersByTime(1);
		expect(toasts.items).toHaveLength(0);
	});

	it('is a success unless it is a failure', () => {
		const toasts = new Toasts();
		toasts.show('Saved');
		toasts.fail('Could not save');
		expect(toasts.items.map((toast) => toast.kind)).toEqual(['success', 'failure']);
	});

	it('keeps a held toast until it is released, then gives it a full STAY again', () => {
		const toasts = new Toasts();
		const id = toasts.show('Copied');
		vi.advanceTimersByTime(STAY - 10);
		toasts.hold(id);
		vi.advanceTimersByTime(STAY * 3);
		expect(toasts.items).toHaveLength(1);
		toasts.release(id);
		vi.advanceTimersByTime(STAY - 1);
		expect(toasts.items).toHaveLength(1);
		vi.advanceTimersByTime(1);
		expect(toasts.items).toHaveLength(0);
	});

	it('dismisses one without disturbing the others', () => {
		const toasts = new Toasts();
		const first = toasts.show('One');
		toasts.show('Two');
		toasts.dismiss(first);
		expect(toasts.items.map((toast) => toast.message)).toEqual(['Two']);
	});

	it('does not bring back a toast that is already gone when it is released', () => {
		const toasts = new Toasts();
		const id = toasts.show('Copied');
		toasts.dismiss(id);
		toasts.release(id);
		vi.advanceTimersByTime(STAY);
		expect(toasts.items).toHaveLength(0);
	});
});
