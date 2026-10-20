/**
 * The guards ADR 21 relies on: a theme is what its export says, every theme defines what the
 * interface reads, and no component names a colour or a duration of its own.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import { parseExport, type Declaration } from '../../../scripts/import-theme.ts';
import registry from './registry.json';

const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, '../../..');
const repo = join(web, '../../..');
const src = join(web, 'src');

function files(dir: string, keep: (path: string) => boolean): string[] {
	return readdirSync(dir).flatMap((name) => {
		const path = join(dir, name);
		if (statSync(path).isDirectory()) return files(path, keep);
		return keep(path) ? [path] : [];
	});
}

/** Prettier rewrites `.55` as `0.55` and `4.20px` as `4.2px`; those are the same value. */
function normalise(value: string): string {
	return value
		.replace(/\s*,\s*/g, ',')
		.replace(/(^|[^\d])\.(\d)/g, '$10.$2')
		.replace(/(\d\.\d*?)0+(?=[^\d]|$)/g, '$1')
		.replace(/\.(?=[^\d]|$)/g, '')
		.trim();
}

/** `--name: value` pairs of every rule in a stylesheet, keyed by the rule's selector. */
function rules(css: string): Map<string, Map<string, string>> {
	const out = new Map<string, Map<string, string>>();
	const bare = css.replace(/\/\*[\s\S]*?\*\//g, '');
	for (const match of bare.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
		const body = new Map<string, string>();
		for (const d of match[2].matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) {
			body.set(d[1], normalise(d[2]));
		}
		out.set(match[1].replace(/\s+/g, ' ').trim(), body);
	}
	return out;
}

const asMap = (list: Declaration[]) => new Map(list.map((d) => [d.name, normalise(d.value)]));

const themes = registry.map((entry) => {
	const css = readFileSync(join(here, `${entry.id}.css`), 'utf8');
	const source = /from (\S+\.md)/.exec(css)?.[1];
	return { entry, css, source };
});

describe('an imported theme', () => {
	it('names the export it was generated from', () => {
		for (const { entry, source } of themes) expect(source, entry.id).toBeTruthy();
	});

	it('carries every declaration of its export, unchanged', () => {
		for (const { entry, css, source } of themes) {
			const exported = parseExport(readFileSync(join(repo, source!), 'utf8'));
			const generated = [...rules(css).entries()];
			const find = (test: (selector: string) => boolean) =>
				generated.find(([selector]) => test(selector))?.[1];
			const palette = `:root[data-palette='${entry.id}']`;

			expect(
				find((s) => s.endsWith(palette)),
				`${entry.id} shared`
			).toEqual(asMap(exported.shared));
			expect(
				find((s) => s.includes(`${palette}[data-theme='dark']`)),
				`${entry.id} dark`
			).toEqual(asMap(exported.dark));
			expect(
				find((s) => s.includes(`${palette}[data-theme='light']`)),
				`${entry.id} light`
			).toEqual(asMap(exported.light));
		}
	});

	it('has exactly one default', () => {
		expect(registry.filter((entry) => entry.default)).toHaveLength(1);
	});

	it('defines every token the default theme defines', () => {
		const tokens = (css: string) =>
			new Set([...css.matchAll(/(--[a-z0-9-]+)\s*:/g)].map((match) => match[1]));
		const reference = tokens(themes.find((t) => t.entry.default)!.css);
		for (const { entry, css } of themes) {
			const missing = [...reference].filter((token) => !tokens(css).has(token));
			expect(missing, entry.id).toEqual([]);
		}
	});

	it('is what the browser chrome shows before the page paints', () => {
		const ground = registry.find((entry) => entry.default)!.ground.dark;
		const html = readFileSync(join(src, 'app.html'), 'utf8');
		const manifest = JSON.parse(readFileSync(join(web, 'static/manifest.webmanifest'), 'utf8'));
		expect(/name="theme-color" content="([^"]+)"/.exec(html)?.[1].toLowerCase()).toBe(ground);
		expect(manifest.theme_color.toLowerCase()).toBe(ground);
		expect(manifest.background_color.toLowerCase()).toBe(ground);
	});
});

describe('parseExport', () => {
	const heaven = readFileSync(join(repo, 'docs/themes/hera-theme-heaven.md'), 'utf8');

	it('refuses an export of another schema', () => {
		expect(() => parseExport(heaven.replace('"hera-theme/1"', '"hera-theme/2"'))).toThrow(/schema/);
	});

	it('refuses a palette with a swatch missing', () => {
		// Renamed rather than deleted: it is the last key of its object, so deleting it would
		// leave a trailing comma and fail on JSON before the palette check is ever reached.
		const broken = heaven.replace('"danger": "#f07a62"', '"dangerous": "#f07a62"');
		expect(() => parseExport(broken)).toThrow(/dark palette is missing danger/);
	});

	it('reads the faces it will install', () => {
		expect(parseExport(heaven).faces).toEqual({
			display: 'Cormorant Garamond',
			body: 'Newsreader',
			ui: 'Albert Sans',
			mono: 'Fira Code'
		});
	});
});

describe('a component', () => {
	const components = files(src, (path) => path.endsWith('.svelte'));
	const styles = files(src, (path) => /\.(svelte|css)$/.test(path) && !path.startsWith(here));
	const code = files(src, (path) => /\.(svelte|css|ts)$/.test(path) && !path.startsWith(here));

	it('reads only tokens that something defines', () => {
		const defined = new Set<string>();
		for (const path of [...styles, ...files(here, (p) => p.endsWith('.css'))]) {
			for (const match of readFileSync(path, 'utf8').matchAll(/(--[a-z0-9-]+)\s*:/g)) {
				defined.add(match[1]);
			}
		}
		// Custom properties a component sets from script (`style:--x={…}`) count as defined too.
		for (const path of components) {
			for (const match of readFileSync(path, 'utf8').matchAll(/style:(--[a-z0-9-]+)/g)) {
				defined.add(match[1]);
			}
		}
		const undefinedReads: string[] = [];
		for (const path of code) {
			// A read with a fallback (`var(--x, …)`) is an optional override hook and needs no
			// definition; a name ending in `-` is prose about a family of tokens, not a read.
			for (const match of readFileSync(path, 'utf8').matchAll(
				/var\((--[a-z0-9-]*[a-z0-9])\s*([,)])/g
			)) {
				if (match[2] === ',' || defined.has(match[1])) continue;
				undefinedReads.push(`${relative(src, path)}: ${match[1]}`);
			}
		}
		expect(undefinedReads).toEqual([]);
	});

	it('names no colour of its own', () => {
		const literal = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/;
		// Comments are prose, and prose says "#158" about an issue rather than a colour.
		const offenders = components.flatMap((path) =>
			style(path)
				.replace(/\/\*[\s\S]*?\*\//g, '')
				.split('\n')
				.filter((line) => literal.test(line))
				.map((line) => `${relative(src, path)}: ${line.trim()}`)
		);
		expect(offenders).toEqual([]);
	});

	it('names no duration of its own', () => {
		// The ocellus is the one piece of choreography (docs/frontend.md § Motion): its beats are
		// tuned against each other and exported (`FOLD_MS`), so they are the mark's, not a slot's.
		const choreography = new Set(['lib/components/Ocellus.svelte']);
		const literal = /(transition|animation)[^;]*?\b\d*\.?\d+m?s\b/;
		const offenders = components
			.filter((path) => !choreography.has(relative(src, path)))
			.flatMap((path) =>
				style(path)
					.replace(/\/\*[\s\S]*?\*\//g, '')
					.replace(/;/g, ';\n')
					.split('\n')
					.filter((line) => literal.test(line))
					.map((line) => `${relative(src, path)}: ${line.trim()}`)
			);
		expect(offenders).toEqual([]);
	});
});

/** The `<style>` block of a component — script may legitimately hold a hex in a string. */
function style(path: string): string {
	return /<style[^>]*>([\s\S]*?)<\/style>/.exec(readFileSync(path, 'utf8'))?.[1] ?? '';
}
