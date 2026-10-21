import { describe, expect, it } from 'vitest';
import { BINDINGS, RESERVED, format, matches, parse, type KeyId, type Press } from './keys';

function press(init: Partial<Press> & { key: string }): Press {
	return { metaKey: false, ctrlKey: false, altKey: false, shiftKey: false, ...init };
}

describe('a chord', () => {
	it('parses modifiers and the key', () => {
		expect(parse('Mod+Shift+O')).toEqual({ mod: true, alt: false, shift: true, key: 'o' });
		expect(parse('Alt+ArrowUp')).toEqual({ mod: false, alt: true, shift: false, key: 'arrowup' });
		expect(parse('Escape')).toEqual({ mod: false, alt: false, shift: false, key: 'escape' });
	});

	it('is Command on a Mac and Control elsewhere', () => {
		const chord = parse('Mod+K');
		expect(matches(press({ key: 'k', metaKey: true }), chord, true)).toBe(true);
		expect(matches(press({ key: 'k', ctrlKey: true }), chord, true)).toBe(false);
		expect(matches(press({ key: 'k', ctrlKey: true }), chord, false)).toBe(true);
		expect(matches(press({ key: 'k', metaKey: true }), chord, false)).toBe(false);
	});

	it('needs exactly the modifiers it names', () => {
		const chord = parse('Mod+Shift+O');
		expect(matches(press({ key: 'O', metaKey: true, shiftKey: true }), chord, true)).toBe(true);
		expect(matches(press({ key: 'o', metaKey: true }), chord, true)).toBe(false);
		expect(
			matches(press({ key: 'O', metaKey: true, shiftKey: true, altKey: true }), chord, true)
		).toBe(false);
	});

	it('ignores Shift for a symbol, so a layout that reaches it with Shift still works', () => {
		const slash = parse('Mod+/');
		expect(matches(press({ key: '/', metaKey: true }), slash, true)).toBe(true);
		expect(matches(press({ key: '/', metaKey: true, shiftKey: true }), slash, true)).toBe(true);
	});

	it('draws itself for the platform', () => {
		expect(format('Mod+Shift+O', true)).toBe('⌘⇧O');
		expect(format('Mod+Shift+O', false)).toBe('Ctrl+Shift+O');
		expect(format('Alt+ArrowUp', true)).toBe('⌥↑');
		expect(format('Alt+ArrowUp', false)).toBe('Alt+↑');
		expect(format('Mod+Backspace', true)).toBe('⌘⌫');
		expect(format('Mod+Backspace', false)).toBe('Ctrl+Backspace');
		expect(format('Shift+Escape', false)).toBe('Shift+Esc');
		expect(format('Mod+,', true)).toBe('⌘,');
	});
});

describe('the keymap', () => {
	it('gives every chord to exactly one action', () => {
		const seen = new Map<string, KeyId>();
		for (const binding of BINDINGS) {
			const clash = seen.get(binding.default);
			expect(clash, `${binding.id} and ${clash} share ${binding.default}`).toBeUndefined();
			seen.set(binding.default, binding.id);
		}
	});

	it('keeps off what the browser owns', () => {
		for (const binding of BINDINGS)
			expect(RESERVED, `${binding.id} takes ${binding.default}`).not.toContain(binding.default);
	});

	it('names the on-screen control every shortcut mirrors', () => {
		for (const binding of BINDINGS) {
			expect(binding.control.trim().length, binding.id).toBeGreaterThan(0);
			expect(binding.label.trim().length, binding.id).toBeGreaterThan(0);
		}
	});

	it('does not take a chord a text field edits with', () => {
		for (const binding of BINDINGS) {
			if (binding.inFields || binding.planned) continue;
			expect(['Mod+Backspace', 'Alt+ArrowUp', 'Alt+ArrowDown', 'Escape']).toContain(
				binding.default
			);
		}
	});
});
