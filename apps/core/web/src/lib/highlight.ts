/**
 * Syntax highlighting for anything that is shown as source, keyed by file extension.
 *
 * `hljs` core with the grammars fetched on demand — the same arrangement as `$lib/mermaid`, for
 * the same reason: a grammar is a chunk a person only pays for when they open a file in that
 * language. Adding a language is one line in `LANGUAGES`; nothing else changes.
 *
 * **The result is safe to `{@html}` and that is not this file's doing.** highlight.js escapes
 * the text it is given and wraps only its own `<span class="hljs-…">`; an extension without a
 * grammar goes through `escape` here instead. Nothing a model wrote reaches the page as markup.
 *
 * It draws text as what it is and reads no meaning back out of it (CLAUDE.md, *no second parser
 * in the browser*) — colour, not interpretation. The colours are in `app.css` under `.hljs-*`
 * so they follow the theme.
 */

import type { HLJSApi, LanguageFn } from 'highlight.js';

type Loader = () => Promise<{ default: LanguageFn }>;

/** extension → the grammar's name and how to fetch it. Aliases share a loader and a name. */
const LANGUAGES: Record<string, [name: string, load: Loader]> = {
	html: ['xml', () => import('highlight.js/lib/languages/xml')],
	htm: ['xml', () => import('highlight.js/lib/languages/xml')],
	svg: ['xml', () => import('highlight.js/lib/languages/xml')],
	md: ['markdown', () => import('highlight.js/lib/languages/markdown')],
	markdown: ['markdown', () => import('highlight.js/lib/languages/markdown')],
	json: ['json', () => import('highlight.js/lib/languages/json')],
	yaml: ['yaml', () => import('highlight.js/lib/languages/yaml')],
	yml: ['yaml', () => import('highlight.js/lib/languages/yaml')],
	toml: ['ini', () => import('highlight.js/lib/languages/ini')],
	py: ['python', () => import('highlight.js/lib/languages/python')],
	ts: ['typescript', () => import('highlight.js/lib/languages/typescript')],
	js: ['javascript', () => import('highlight.js/lib/languages/javascript')],
	css: ['css', () => import('highlight.js/lib/languages/css')],
	sh: ['bash', () => import('highlight.js/lib/languages/bash')],
	sql: ['sql', () => import('highlight.js/lib/languages/sql')],
	rs: ['rust', () => import('highlight.js/lib/languages/rust')],
	go: ['go', () => import('highlight.js/lib/languages/go')]
};

let core: Promise<HLJSApi> | null = null;

function engine(): Promise<HLJSApi> {
	core ??= import('highlight.js/lib/core').then((module) => module.default);
	return core;
}

/** Text as text, for what has no grammar. */
export function escape(source: string): string {
	return source.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/** Whether `highlight` will colour this extension — everything else comes back escaped only. */
export function canHighlight(extension: string): boolean {
	return extension in LANGUAGES;
}

/** `source` as HTML with the tokens wrapped in `hljs-*` spans; `extension` has no dot. */
export async function highlight(source: string, extension: string): Promise<string> {
	const entry = LANGUAGES[extension];
	if (!entry) return escape(source);
	const [name, load] = entry;
	try {
		const [hljs, grammar] = await Promise.all([engine(), load()]);
		if (!hljs.getLanguage(name)) hljs.registerLanguage(name, grammar.default);
		return hljs.highlight(source, { language: name, ignoreIllegals: true }).value;
	} catch {
		// A chunk that would not load must not cost the person the code they came to read.
		return escape(source);
	}
}
