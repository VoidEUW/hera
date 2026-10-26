/**
 * One icon set, drawn in one place (ADR 21). A component that draws its own `<svg>` or spells an
 * icon as a text glyph is a second icon family, which is the thing the theme rules out.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { ICONS } from './icons';

const src = join(dirname(fileURLToPath(import.meta.url)), '..');

function components(dir: string): string[] {
	return readdirSync(dir).flatMap((name) => {
		const path = join(dir, name);
		if (statSync(path).isDirectory()) return components(path);
		return path.endsWith('.svelte') ? [path] : [];
	});
}

/** The markup of a component, without its script, its style and its comments. */
function markup(path: string): string {
	return readFileSync(path, 'utf8')
		.replace(/<script[\s\S]*?<\/script>/g, '')
		.replace(/<style[\s\S]*?<\/style>/g, '')
		.replace(/<!--[\s\S]*?-->/g, '');
}

describe('the icon set', () => {
	it('draws every icon with something', () => {
		for (const [name, parts] of Object.entries(ICONS))
			expect(parts.length, name).toBeGreaterThan(0);
	});

	it('uses only the elements a stroke icon needs', () => {
		const allowed = new Set(['path', 'circle', 'rect', 'line', 'polyline', 'polygon', 'ellipse']);
		for (const [name, parts] of Object.entries(ICONS)) {
			for (const [tag] of parts) expect(allowed.has(tag), `${name}: ${tag}`).toBe(true);
		}
	});
});

describe('a component', () => {
	it('draws no svg of its own', () => {
		const drawers = new Set([
			'lib/components/ui/Icon.svelte',
			// The signature, which is not an icon and may not become one (docs/frontend.md).
			'lib/components/ui/Ocellus.svelte',
			// Arcs, not icons: a stroke that is animated or filled to a share, which an icon's
			// never is.
			'lib/components/ui/Spinner.svelte',
			'lib/components/ui/SendButton.svelte',
			'lib/components/ui/ContextMeter.svelte',
			// Bars, not icons: a chart's rectangles scaled to data (#111).
			'lib/components/ui/BarChart.svelte'
		]);
		const offenders = components(src)
			.filter((path) => !drawers.has(relative(src, path)))
			.filter((path) => /<svg\b/.test(markup(path)))
			.map((path) => relative(src, path));
		expect(offenders).toEqual([]);
	});

	it('spells no icon as a text glyph', () => {
		const glyphs = /[✕×▸▾▴☰⋯＋↑✓✔⚠⚙]/;
		const offenders = components(src).flatMap((path) =>
			markup(path)
				.split('\n')
				.filter((line) => glyphs.test(line))
				.map((line) => `${relative(src, path)}: ${line.trim()}`)
		);
		expect(offenders).toEqual([]);
	});
});
