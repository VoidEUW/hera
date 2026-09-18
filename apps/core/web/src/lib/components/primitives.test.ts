/**
 * The guard from #99: "every selector in the application is `Select.svelte`" stays true.
 *
 * The three native `<select>`s in `settings/Models.svelte` are gone; this is what keeps them
 * gone. A grep rather than a render test, because the thing being guarded against is not
 * behaviour but *drift* — somebody adding a field to a settings screen and reaching for the
 * platform control out of habit — and drift is exactly what a plain text search catches.
 *
 * The files are read through `import.meta.glob` with `?raw` rather than `node:fs`, so the test
 * runs through Vite's own pipeline and needs no node types.
 *
 * Comments are allowed to mention `<select` — `Select.svelte`'s docstring tells the story of
 * the native one it replaced, and `Composer.svelte`'s CSS says the same — so JS/CSS comment
 * spans are stripped before the scan rather than pattern-matched line by line. The point is
 * that no *element* ships, and an element is what is left when the comments are gone.
 *
 * The match is lowercase and word-boundary aware on purpose, and not case-insensitive: a
 * Svelte *element* is always lowercase (`<select>`), a *component* is always capitalized
 * (`<Select`), and an `i` flag would flag all ten of the component's call sites as offenders.
 */

import { describe, expect, it } from 'vitest';

const SOURCES = import.meta.glob('/src/**/*.svelte', {
	query: '?raw',
	import: 'default',
	eager: true
}) as Record<string, string>;

/** Drop every comment span the file could carry: `// …` to end of line, `/* … *\/`
 * blocks (CSS and JS), and `<!-- … -->` HTML comments — each replaced by its own newlines so
 * the line numbers reported below still name the element's line. Backtick mentions of
 * `<select>` inside those comments are what this is for: the story of the native control is
 * worth keeping in the source, and the guard should not make mentioning it illegal. */
function uncomment(source: string): string {
	return source
		.replace(/\/\*[\s\S]*?\*\//g, (span) => span.replace(/[^\n]/g, ''))
		.replace(/(^|[^:])\/\/.*$/gm, '$1')
		.replace(/<!--[\s\S]*?-->/g, (span) => span.replace(/[^\n]/g, ''));
}

describe('every selector is Select', () => {
	it('no .svelte file under src/ opens a native <select> element', () => {
		const offenders: string[] = [];
		for (const [path, source] of Object.entries(SOURCES)) {
			const stripped = uncomment(source);
			// Line numbers are counted on the stripped text — they still land on the element's
			// line, because comment removal collapses spans but never inserts newlines.
			stripped.split('\n').forEach((line: string, index: number) => {
				if (/<select\b/.test(line)) {
					offenders.push(`${path}:${index + 1}: ${line.trim()}`);
				}
			});
		}
		expect(offenders, offenders.join('\n')).toEqual([]);
	});
});
