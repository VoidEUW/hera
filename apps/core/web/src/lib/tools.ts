/**
 * Turning `docker__mcp-find` into something a person reads, and choosing the mark beside it.
 *
 * Every tool arrives namespaced `server__tool` — that is `hera_tools`' doing and it is the
 * right shape for a catalogue, a permission pattern and a log line. It is the wrong shape for a
 * sentence. A row that says *ran docker__mcp-find* asks the reader to do the parsing, and the
 * double underscore is the part that reads as machinery rather than as an action.
 *
 * `toolName` is a **string transformation and nothing else**, and there is deliberately no
 * table of foreign tools anywhere in this file: the interface would then render servers it
 * recognises differently from servers it does not, which is how a server you have not set up
 * yet starts looking like a server that is broken. The qualified name stays available beside
 * the readable one, because it is what a permission rule is written against.
 *
 * `mark` is the one exception and is narrow on purpose — see the note above it. It reads
 * `hera__*` and refuses to know anything else.
 */

import { HERA, type AnyEvent, type ToolCallReady } from './api/events';

/** Which mark a row draws in the gutter. */
export type Mark = 'thinking' | 'skill' | 'search' | 'note' | 'memory' | 'tool';

/**
 * The marks her own tools get, and nothing else's.
 *
 * This is the one table of tool names in the interface and it is allowed to exist because
 * `hera__*` is **her** namespace: every tool on it is shipped in this repository, the emotion
 * one is already drawn as a card rather than a row, and knowing what her own capabilities look
 * like is not the same as knowing somebody else's server. What this must never grow is an entry
 * for a name that arrives over `mcp.json` — the moment a familiar tool is drawn differently from
 * an unfamiliar one, a server you have not configured yet looks like a server that is broken.
 *
 * Everything unlisted, hers included, falls through to the wrench. That is the point of the
 * `default` below rather than an exhaustive map: adding a tool to `hera_mcp` must not be able to
 * break this file, and a tool this build has never heard of gets the honest generic mark.
 *
 * Adding one when the scratchpad lands (`docs/tooling.md` § 2) is one line: writing to it is a
 * `note`, and so is reading it back — the reader's question is *did she write something down*,
 * not which call carried it.
 */
export function mark(qualified: string): Mark {
	if (!qualified.startsWith(HERA)) return 'tool';
	switch (qualified.slice(HERA.length)) {
		case 'skill':
			return 'skill';
		case 'search':
		case 'fetch':
			return 'search';
		case 'note':
			return 'note';
		case 'remember':
			return 'memory';
		default:
			return 'tool';
	}
}

/** The mark for a gutter row, from whichever event it was built out of. */
export function markOf(event: AnyEvent): Mark {
	if (event.type === 'tool_call_ready') return mark((event as ToolCallReady).name);
	if (event.type === 'tool_result') return mark((event as { tool?: string }).tool ?? '');
	return 'tool';
}

/**
 * Which argument a row shows as what she did it *to*.
 *
 * Her own tools read as a sentence with the tool's own name as the verb — *skill
 * rust-best-practices*, *search llama.cpp tool grammar* — because the mark beside the row has
 * already said whose tool it is and *called **Hera** skill* then spends two of the four words
 * on that same fact. What a reader wants in the space is the subject: which skill, what query.
 *
 * Foreign tools keep *called **Docker** mcp find*, and that asymmetry is the point: the server
 * something came from is the most important thing about it when it is not hers, and noise when
 * it is.
 *
 * Ordered candidates, because an argument can be there and empty — `note` has a title only
 * sometimes, and falling back to the text is better than a row that names nothing.
 */
const SUBJECT: Record<string, readonly string[]> = {
	skill: ['name'],
	search: ['query'],
	note: ['title', 'text'],
	remember: ['text'],
	emotion: ['kind']
};

/** The subject of one of her calls, or `''` when there is nothing worth showing. */
export function subject(qualified: string, args: Record<string, unknown>): string {
	if (!qualified.startsWith(HERA)) return '';
	// An unlisted tool of hers falls back to its first argument, so adding one to `hera_mcp`
	// gives a readable row before anybody remembers to come back here.
	const keys = SUBJECT[qualified.slice(HERA.length)] ?? Object.keys(args);
	for (const key of keys) {
		const value = args[key];
		const text = typeof value === 'string' ? value.trim() : '';
		if (text) return text;
	}
	return '';
}

export interface ToolName {
	/** The server it came from, with its first letter raised: `docker` → `Docker`. The only
	 * liberty taken with somebody else's word, and it is taken because the name sits inside a
	 * sentence — *called **Docker** mcp find* — where a lowercase proper noun reads as a typo. */
	server: string;
	/** The tool, with its separators opened up: `mcp-find` → `mcp find`. */
	action: string;
	/** The original, for a tooltip, a rule, or a person who wants the real thing. */
	qualified: string;
}

const SEPARATOR = '__';

export function toolName(qualified: string): ToolName {
	const at = qualified.indexOf(SEPARATOR);
	const server = at > 0 ? qualified.slice(0, at) : '';
	const local = at > 0 ? qualified.slice(at + SEPARATOR.length) : qualified;
	return { server: capitalise(server), action: humanise(local), qualified };
}

/** `mcp-find` → `mcp find`, `read_file` → `read file`. Nothing cleverer: the tool's author
 * chose these words, and a browser second-guessing them is how `fs` becomes "Filesystem" on
 * one screen and `fs` on the next. */
function humanise(local: string): string {
	return local.replace(/[-_]+/g, ' ').trim() || local;
}

function capitalise(server: string): string {
	return server ? server[0].toUpperCase() + server.slice(1) : '';
}
