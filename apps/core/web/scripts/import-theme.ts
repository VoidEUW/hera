/**
 * Turn a Hera Theme Builder export into the files the interface reads (ADR 21).
 *
 *     npm run theme:import -- ../../../docs/themes/hera-theme-heaven.md [--default]
 *
 * An export is one Markdown file with two fenced blocks this script cares about: the ```css token
 * block (the builder's own output, including the tokens it derives from the palette — `--hover`,
 * the `-soft` tints, `--on-*`, `--scrim`, the shadows) and the ```json `hera-theme/1` block that
 * names the theme and its faces. It writes, under `src/lib/themes/`:
 *
 * - `<id>.css` — the export's declarations, re-scoped to `:root[data-palette='<id>']` so several
 *   themes can be loaded at once. The default theme is emitted on bare `:root` as well, so the page
 *   has every token before a script has run.
 * - `<id>.fonts.css` — the `@fontsource-variable` imports for its four faces.
 * - `registry.json` — what the application needs to know about every theme without loading it.
 * - `index.css` — one import per registered theme, which is all `app.css` imports.
 *
 * The declarations are copied, never recomputed: the builder owns the derivation, and a second
 * implementation of it here would be the drift this whole arrangement exists to end. Generated
 * files are formatted with the project's Prettier so `npm run lint` holds for them, and running
 * the import again on an unchanged export changes nothing.
 *
 * Runs on Node's own type stripping, so this file sticks to syntax that can be erased.
 */

import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const SCHEMA = 'hera-theme/1';

/** The palette keys every theme has to define in both modes — the eleven swatches of an export. */
export const PALETTE = [
	'ground',
	'surface',
	'surface-raised',
	'line',
	'text',
	'text-muted',
	'text-faint',
	'brass',
	'laurel',
	'pomegranate',
	'danger'
] as const;

const ROLES = ['display', 'body', 'ui', 'mono'] as const;

/** One custom property as the export wrote it, comment and all. */
export interface Declaration {
	name: string;
	value: string;
	comment: string;
}

export interface ThemeExport {
	id: string;
	name: string;
	description: string;
	/** Faces by role, as family names: `{ display: 'Cormorant Garamond', … }`. */
	faces: Record<(typeof ROLES)[number], string>;
	ground: { dark: string; light: string };
	/** Mode-independent tokens: type, shape, density, icons, motion. */
	shared: Declaration[];
	dark: Declaration[];
	light: Declaration[];
}

export interface RegistryEntry {
	id: string;
	name: string;
	description: string;
	ground: { dark: string; light: string };
	default: boolean;
}

/** The body of the first fenced block in `markdown` with this language, or `null`. */
function fenced(markdown: string, language: string): string | null {
	const match = new RegExp('```' + language + '\\n([\\s\\S]*?)\\n```').exec(markdown);
	return match ? match[1] : null;
}

/** Every `--name: value;` inside one rule body, keeping a trailing comment if there is one. */
function declarations(body: string): Declaration[] {
	const found: Declaration[] = [];
	const pattern = /(--[a-z0-9-]+)\s*:\s*([^;]+);[ \t]*(\/\*[^*]*\*+(?:[^/*][^*]*\*+)*\/)?/g;
	for (const match of body.matchAll(pattern)) {
		found.push({ name: match[1], value: match[2].trim(), comment: match[3] ?? '' });
	}
	return found;
}

/**
 * Split the export's token block into its three rules by what their selectors say — not by
 * position, so a builder that reorders the blocks or adds a selector does not silently file the
 * light palette under dark.
 */
function rules(css: string): Pick<ThemeExport, 'shared' | 'dark' | 'light'> {
	const out: Pick<ThemeExport, 'shared' | 'dark' | 'light'> = { shared: [], dark: [], light: [] };
	const stripped = css.replace(/\/\*[^*]*\*+(?:[^/*][^*]*\*+)*\/\s*(?=[:[])/g, '');
	for (const match of stripped.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
		const selector = match[1].trim();
		const into = selector.includes("data-theme='light'")
			? out.light
			: selector.includes("data-theme='dark'")
				? out.dark
				: selector === ':root'
					? out.shared
					: null;
		if (!into) throw new Error(`unexpected selector in the token block: ${selector}`);
		into.push(...declarations(match[2]));
	}
	return out;
}

/** Read an export. Throws with a sentence naming what is wrong, never a stack of `undefined`. */
export function parseExport(markdown: string): ThemeExport {
	const css = fenced(markdown, 'css');
	const json = fenced(markdown, 'json');
	if (!css) throw new Error('no ```css token block in the export');
	if (!json) throw new Error('no ```json source-of-truth block in the export');

	const source = JSON.parse(json) as {
		schema?: string;
		id?: string;
		name?: string;
		description?: string;
		color?: Record<'dark' | 'light', Record<string, string>>;
		type?: Record<string, string>;
	};
	if (source.schema !== SCHEMA) throw new Error(`schema is ${source.schema}, expected ${SCHEMA}`);
	if (!source.id || !/^[a-z0-9-]+$/.test(source.id)) {
		throw new Error(`theme id ${JSON.stringify(source.id)} is not a lowercase slug`);
	}
	for (const mode of ['dark', 'light'] as const) {
		const missing = PALETTE.filter((key) => !source.color?.[mode]?.[key]);
		if (missing.length) throw new Error(`${mode} palette is missing ${missing.join(', ')}`);
	}
	const faces = {} as ThemeExport['faces'];
	for (const role of ROLES) {
		const family = source.type?.[role];
		if (!family) throw new Error(`no ${role} face named`);
		faces[role] = family;
	}

	const parsed = rules(css);
	for (const mode of ['dark', 'light'] as const) {
		const declared = new Set(parsed[mode].map((d) => d.name));
		const missing = PALETTE.filter((key) => !declared.has(`--${key}`));
		if (missing.length) throw new Error(`the ${mode} token rule does not declare ${missing}`);
	}

	return {
		id: source.id,
		name: source.name ?? source.id,
		description: source.description ?? '',
		faces,
		ground: { dark: source.color!.dark.ground, light: source.color!.light.ground },
		...parsed
	};
}

/** `Cormorant Garamond` → `@fontsource-variable/cormorant-garamond`. */
export function fontPackage(family: string): string {
	return `@fontsource-variable/${family.trim().toLowerCase().replace(/\s+/g, '-')}`;
}

function rule(selectors: string[], body: Declaration[]): string {
	const lines = body.map((d) => `\t${d.name}: ${d.value};${d.comment ? ' ' + d.comment : ''}`);
	return `${selectors.join(',\n')} {\n${lines.join('\n')}\n}\n`;
}

const HEADER = (theme: ThemeExport, source: string) =>
	`/* Generated by scripts/import-theme.ts from ${source} — do not edit; re-run the import.\n` +
	`   ${theme.name}: ${theme.description} */\n`;

/** The theme's token file. Selectors are ours rather than the export's, so every theme is scoped
 * the same way whatever the builder happened to write. */
export function renderTheme(theme: ThemeExport, isDefault: boolean, source: string): string {
	const palette = `:root[data-palette='${theme.id}']`;
	const shared = isDefault ? [':root', palette] : [palette];
	const dark = isDefault
		? [':root', "[data-theme='dark']", palette, `${palette}[data-theme='dark']`]
		: [palette, `${palette}[data-theme='dark']`];
	const light = isDefault
		? ["[data-theme='light']", `${palette}[data-theme='light']`]
		: [`${palette}[data-theme='light']`];
	return [
		HEADER(theme, source),
		rule(shared, theme.shared),
		rule(dark, [...theme.dark, { name: 'color-scheme', value: 'dark', comment: '' }]),
		rule(light, [...theme.light, { name: 'color-scheme', value: 'light', comment: '' }])
	].join('\n');
}

/** The faces, plus the body face's italic: her prose has emphasis in it, and a synthesised
 * oblique of a serif is the one thing a reader notices without knowing why. */
export function renderFonts(theme: ThemeExport, source: string): string {
	const packages = [...new Set(ROLES.map((role) => fontPackage(theme.faces[role])))];
	const imports = packages.map((name) => `@import '${name}';`);
	imports.push(`@import '${fontPackage(theme.faces.body)}/wght-italic.css';`);
	return `${HEADER(theme, source)}\n${imports.join('\n')}\n`;
}

export function upsert(
	registry: RegistryEntry[],
	theme: ThemeExport,
	makeDefault: boolean
): RegistryEntry[] {
	const others = registry.filter((entry) => entry.id !== theme.id);
	const isDefault =
		makeDefault || others.length === 0 || registry.some((e) => e.id === theme.id && e.default);
	const entry: RegistryEntry = {
		id: theme.id,
		name: theme.name,
		description: theme.description,
		ground: theme.ground,
		default: isDefault
	};
	return [...others.map((e) => (isDefault ? { ...e, default: false } : e)), entry].sort((a, b) =>
		a.id.localeCompare(b.id)
	);
}

export function renderIndex(registry: RegistryEntry[]): string {
	// The default theme last, so its bare `:root` rule cannot be overridden by another theme's
	// palette-scoped one being read after it — specificity already decides that, and the order
	// makes it obvious to someone reading the generated file.
	const ordered = [...registry].sort((a, b) => Number(a.default) - Number(b.default));
	const lines = ordered.flatMap((e) => [
		`@import './${e.id}.fonts.css';`,
		`@import './${e.id}.css';`
	]);
	return `/* Generated by scripts/import-theme.ts — every registered theme. Do not edit. */\n\n${lines.join('\n')}\n`;
}

function main(argv: string[]): void {
	const web = resolve(dirname(fileURLToPath(import.meta.url)), '..');
	const out = join(web, 'src/lib/themes');
	const makeDefault = argv.includes('--default');
	const path = argv.find((arg) => !arg.startsWith('--'));
	if (!path) {
		console.error('usage: npm run theme:import -- <export.md> [--default]');
		process.exit(2);
	}

	const absolute = resolve(process.cwd(), path);
	const theme = parseExport(readFileSync(absolute, 'utf8'));
	const source = absolute.slice(resolve(web, '../../..').length + 1);

	const registryPath = join(out, 'registry.json');
	const registry = upsert(
		existsSync(registryPath)
			? (JSON.parse(readFileSync(registryPath, 'utf8')) as RegistryEntry[])
			: [],
		theme,
		makeDefault
	);
	const isDefault = registry.find((e) => e.id === theme.id)!.default;

	const written = [
		[join(out, `${theme.id}.css`), renderTheme(theme, isDefault, source)],
		[join(out, `${theme.id}.fonts.css`), renderFonts(theme, source)],
		[registryPath, JSON.stringify(registry, null, '\t') + '\n'],
		[join(out, 'index.css'), renderIndex(registry)]
	];
	mkdirSync(out, { recursive: true });
	for (const [file, text] of written) writeFileSync(file, text);
	execFileSync('npx', ['prettier', '--write', ...written.map(([file]) => file)], {
		cwd: web,
		stdio: 'ignore'
	});

	const manifest = JSON.parse(readFileSync(join(web, 'package.json'), 'utf8')) as {
		dependencies?: Record<string, string>;
	};
	const missing = [...new Set(ROLES.map((role) => fontPackage(theme.faces[role])))].filter(
		(name) => !manifest.dependencies?.[name]
	);
	console.log(`imported ${theme.name} (${theme.id})${isDefault ? ', the default' : ''}`);
	if (missing.length) console.log(`install its faces: npm install ${missing.join(' ')}`);
	// A theme that just stopped being the default still carries bare `:root` rules, and its
	// declarations live only in its own export — so say so rather than guess where that is.
	if (makeDefault && registry.length > 1) {
		console.log('the previous default still has bare :root rules — re-import it without --default');
	}
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	main(process.argv.slice(2));
}
