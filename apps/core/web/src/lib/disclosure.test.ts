import { describe, expect, it } from 'vitest';
import { Disclosure, providers } from './disclosure.svelte';

describe('Disclosure', () => {
	it('answers with the fallback until something is toggled', () => {
		const d = new Disclosure();
		expect(d.isOpen('local', true)).toBe(true);
		expect(d.isOpen('other', false)).toBe(false);
	});

	it('lets a toggle win over the fallback, in both directions', () => {
		const d = new Disclosure();
		d.toggle('local', true);
		expect(d.isOpen('local', true)).toBe(false);
		d.toggle('other', false);
		expect(d.isOpen('other', false)).toBe(true);
	});

	it('keeps an explicit answer even when the fallback changes underneath it', () => {
		// The active provider moving must not close one somebody opened by hand.
		const d = new Disclosure();
		d.set('studio', true);
		expect(d.isOpen('studio', false)).toBe(true);
	});

	it('is one shared instance, so a screen that remounts finds the same answers', () => {
		providers.set('shared', true);
		expect(providers.isOpen('shared', false)).toBe(true);
	});
});
