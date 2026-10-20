/** The chat sidebar's width: clamped on every way in, and remembered. */

import { describe, expect, it } from 'vitest';

import { clamp, DEFAULT, MAX, MIN, Sidebar, STEP } from './sidebar.svelte';

function memory() {
	const values = new Map<string, string>();
	return {
		getItem: (key: string) => values.get(key) ?? null,
		setItem: (key: string, value: string) => void values.set(key, value)
	};
}

describe('clamp', () => {
	it('keeps a width inside the range', () => {
		expect(clamp(MIN - 50)).toBe(MIN);
		expect(clamp(MAX + 50)).toBe(MAX);
		expect(clamp(300.4)).toBe(300);
	});

	it('falls back to the default for something that is not a number', () => {
		expect(clamp(Number('wide'))).toBe(DEFAULT);
	});
});

describe('Sidebar', () => {
	it('starts at the default when nothing is stored', () => {
		const sidebar = new Sidebar();
		sidebar.load(memory());
		expect(sidebar.width).toBe(DEFAULT);
	});

	it('remembers a width across loads', () => {
		const storage = memory();
		const first = new Sidebar();
		first.resize(333, storage);
		const second = new Sidebar();
		second.load(storage);
		expect(second.width).toBe(333);
	});

	it('does not trust a stored width from outside the range', () => {
		const storage = memory();
		storage.setItem('hera:sidebar-width', '9000');
		const sidebar = new Sidebar();
		sidebar.load(storage);
		expect(sidebar.width).toBe(MAX);
	});

	it('steps by the arrow keys and jumps by Home and End', () => {
		const storage = memory();
		const sidebar = new Sidebar();
		sidebar.load(storage);
		expect(sidebar.key('ArrowRight', storage)).toBe(true);
		expect(sidebar.width).toBe(DEFAULT + STEP);
		sidebar.key('ArrowLeft', storage);
		sidebar.key('ArrowLeft', storage);
		expect(sidebar.width).toBe(DEFAULT - STEP);
		sidebar.key('End', storage);
		expect(sidebar.width).toBe(MAX);
		sidebar.key('Home', storage);
		expect(sidebar.width).toBe(MIN);
		expect(sidebar.key('a', storage)).toBe(false);
	});

	it('goes back to the default on reset', () => {
		const storage = memory();
		const sidebar = new Sidebar();
		sidebar.resize(400, storage);
		sidebar.reset(storage);
		expect(sidebar.width).toBe(DEFAULT);
	});
});
