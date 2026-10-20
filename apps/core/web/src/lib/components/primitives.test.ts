/**
 * The guards that keep the interface one set of components (ADR 21, and the overhaul after it).
 *
 * **Every control is a primitive.** A `.svelte` file outside `lib/components/ui/` may not open a
 * `<button>`, `<input>`, `<textarea>` or `<select>` of its own: it composes `Button`, `IconButton`,
 * `Input`, `Selector` and the rest. The drift this catches is the one the overhaul removed — a
 * settings screen reaching for the platform control, or a hand-styled button with its own hover,
 * out of habit — and drift is exactly what a plain text search catches.
 *
 * **Brass stays where the theme puts it.** `--brass` is her authority, and the theme names where
 * that is said: highlighted buttons, toggles and chips that are on, the authority pill, the check
 * on a chosen menu row, an icon button's momentary "done", the ocellus, and the question and
 * permission cards. Anywhere else, yellow is a highlight nobody asked for.
 *
 * The files are read through `import.meta.glob` with `?raw`, so the test runs through Vite's own
 * pipeline. Comments are stripped first: the story of the control a primitive replaced is worth
 * keeping in the source, and the guard should not make mentioning it illegal.
 */

import { describe, expect, it } from 'vitest';

const SOURCES = import.meta.glob(['/src/**/*.svelte', '/src/**/*.css'], {
	query: '?raw',
	import: 'default',
	eager: true
}) as Record<string, string>;

/** Drop every comment span, each replaced by its own newlines so line numbers stay true. */
function uncomment(source: string): string {
	return source
		.replace(/\/\*[\s\S]*?\*\//g, (span) => span.replace(/[^\n]/g, ''))
		.replace(/(^|[^:'"`])\/\/.*$/gm, '$1')
		.replace(/<!--[\s\S]*?-->/g, (span) => span.replace(/[^\n]/g, ''));
}

/** The markup of a component: what is left without its script and its style. */
function markup(source: string): string {
	return uncomment(source)
		.replace(/<script[\s\S]*?<\/script>/g, (span) => span.replace(/[^\n]/g, ''))
		.replace(/<style[\s\S]*?<\/style>/g, (span) => span.replace(/[^\n]/g, ''));
}

function offenders(files: [string, string][], pattern: RegExp): string[] {
	return files.flatMap(([path, text]) =>
		text
			.split('\n')
			.flatMap((line, index) =>
				pattern.test(line) ? [`${path}:${index + 1}: ${line.trim()}`] : []
			)
	);
}

const UI = '/src/lib/components/ui/';

describe('every control is a primitive', () => {
	it('no component outside ui/ opens a button, input, textarea or select of its own', () => {
		const features = Object.entries(SOURCES)
			.filter(([path]) => path.endsWith('.svelte') && !path.startsWith(UI))
			.map(([path, source]): [string, string] => [path, markup(source)]);
		const found = offenders(features, /<(button|input|textarea|select)\b/);
		expect(found, found.join('\n')).toEqual([]);
	});

	it('no native select anywhere — a choice is a Selector', () => {
		const all = Object.entries(SOURCES)
			.filter(([path]) => path.endsWith('.svelte'))
			.map(([path, source]): [string, string] => [path, markup(source)]);
		const found = offenders(all, /<select\b/);
		expect(found, found.join('\n')).toEqual([]);
	});
});

describe('brass stays where the theme puts it', () => {
	const ALLOWED = new Set([
		`${UI}Button.svelte`,
		`${UI}Toggle.svelte`,
		`${UI}Chip.svelte`,
		`${UI}Pill.svelte`,
		`${UI}MenuItem.svelte`,
		`${UI}IconButton.svelte`,
		`${UI}Ocellus.svelte`,
		'/src/lib/components/QuestionCard.svelte',
		'/src/lib/components/PermissionCard.svelte'
	]);

	it('only the components the theme names read --brass', () => {
		const styles = Object.entries(SOURCES)
			.filter(([path]) => !path.startsWith('/src/lib/themes/') && !ALLOWED.has(path))
			.map(([path, source]): [string, string] => [
				path,
				path.endsWith('.css')
					? uncomment(source)
					: uncomment(/<style[^>]*>([\s\S]*?)<\/style>/.exec(source)?.[1] ?? '')
			]);
		const found = offenders(styles, /var\(--brass/);
		expect(found, found.join('\n')).toEqual([]);
	});
});
