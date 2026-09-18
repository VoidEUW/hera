/**
 * What an artifact's *name* says about it, and nothing else (ADR 13).
 *
 * There is no `kind` field anywhere in this feature. The filename is the identity and the
 * extension is the kind, so a model cannot disagree with its own filename — and the whole of
 * that decision is implemented in this file, in one map.
 *
 * `sanitiseSvg` is the other half. A drawing she made is markup a *model* wrote, drawn into the
 * page with `{@html}`, so it goes through the same DOMPurify that `$lib/markdown` uses for her
 * prose and for the same reason: a model can be talked into emitting a `<script>` by the page it
 * was asked to read. An `.html` artifact is *not* sanitised and is not drawn in this document at
 * all — it goes into a sandboxed frame with an opaque origin, which is what makes it safe to run
 * as a page rather than to strip until it is not one.
 */

import DOMPurify from 'dompurify';

import { API, type ArtifactSummary } from './api/client';
import { humanise } from './tools';

/** How one artifact is drawn. */
export type Kind = 'html' | 'svg' | 'markdown' | 'code' | 'mermaid' | 'file';

const KINDS: Record<string, Kind> = {
	html: 'html',
	htm: 'html',
	svg: 'svg',
	md: 'markdown',
	markdown: 'markdown',
	mmd: 'mermaid',
	mermaid: 'mermaid',
	txt: 'code',
	json: 'code',
	yaml: 'code',
	yml: 'code',
	toml: 'code',
	csv: 'code',
	py: 'code',
	ts: 'code',
	js: 'code',
	css: 'code',
	sh: 'code',
	sql: 'code',
	rs: 'code',
	go: 'code'
};

/** The extension, lowercased, or `''` for a name with none. */
export function extensionOf(name: string): string {
	const at = name.lastIndexOf('.');
	return at > 0 ? name.slice(at + 1).toLowerCase() : '';
}

/** Which renderer draws this one.
 *
 * `file` is the honest fallback rather than a failure: something this build cannot draw is still
 * a file she made, and offering the download says so. Guessing — treating an unknown extension as
 * text and hoping — is how a person is shown a screen of replacement characters.
 */
export function kindOf(name: string): Kind {
	return KINDS[extensionOf(name)] ?? 'file';
}

/** The name without its extension: `theme-workshop.html` → `theme-workshop`.
 *
 * What you build another filename out of — a diagram saved as the page that draws it keeps the
 * name she gave it and changes only the kind.
 */
export function stemOf(name: string): string {
	const extension = extensionOf(name);
	return extension ? name.slice(0, -(extension.length + 1)) : name;
}

/** The heading a card shows: `theme-workshop.html` → `Theme workshop`.
 *
 * The same transformation `$lib/tools` applies to a tool name, for the reason written there —
 * the author chose those words, and a browser second-guessing them is how one screen disagrees
 * with the next. There is deliberately no title field anywhere for this to compete with.
 */
export function titleOf(name: string): string {
	const opened = humanise(stemOf(name));
	return opened ? opened[0].toUpperCase() + opened.slice(1) : name;
}

/** One drawing, safe to put into the document.
 *
 * `svg` only: `USE_PROFILES` without `html` means a `<div>` or an `<iframe>` smuggled into the
 * markup is removed rather than rendered, so what lands in the page is a picture and cannot be a
 * document.
 */
export function sanitiseSvg(source: string): string {
	return DOMPurify.sanitize(source, { USE_PROFILES: { svg: true, svgFilters: true } });
}

/** Where the file itself is, for a `download` link.
 *
 * A plain URL rather than a fetch and a blob: the browser already knows how to save a file, and
 * the response says `attachment` with a neutral media type — so a page she wrote is never a
 * document rendered at Hera's own origin.
 */
export function downloadUrl(chatId: string, name: string): string {
	return `${API}/chats/${chatId}/artifacts/${encodeURIComponent(name)}/download`;
}

/** `2.4 KB`, for a caption. Bytes below a kilobyte, because *0.0 KB* says less than *812 B*. */
export function size(bytes: number): string {
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** The one to open when nothing has been chosen: the most recently written.
 *
 * The listing arrives sorted by **name** — `list_artifacts` walks the directory in `sorted()`
 * order — so *the last one in the list* is alphabetical and means nothing. What a person coming
 * back to a conversation wants is the thing she made last, which is what `modified_at` says.
 *
 * Ties go to the later entry, so a conversation that published two files in the same second
 * opens the one further down the bar rather than the one whose name happens to sort first.
 */
export function newest(files: readonly ArtifactSummary[]): ArtifactSummary | null {
	let best: ArtifactSummary | null = null;
	let at = -Infinity;
	for (const file of files) {
		// Parsed rather than compared as text. Two ISO 8601 stamps in the same shape do sort
		// correctly as strings, which is exactly why it is worth not relying on: the shape is the
		// server's to change, and a silent fallback to alphabetical is the bug this replaces.
		const when = Date.parse(file.modified_at);
		if (Number.isNaN(when)) continue;
		if (when >= at) {
			at = when;
			best = file;
		}
	}
	// Every stamp unreadable, and there are still files: the last of them beats nothing at all.
	return best ?? files.at(-1) ?? null;
}
