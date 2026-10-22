/**
 * The add-a-server form as data (#108): what the editor holds while somebody types, and how it
 * becomes the entry the server stores.
 *
 * Pure, so the awkward parts — a secret that was hidden and must not be sent back as empty, a
 * list of arguments typed one per line — are tested without a browser.
 *
 * A **row** is one `KEY=value` of an environment or a header. A value the server holds but did not
 * send (`hidden`) is a secret somebody pasted earlier; it goes back as `null`, which means *keep
 * it*, until the person types a replacement.
 */

import type { ServerEntry } from '$lib/api/client';

export interface Row {
	key: string;
	value: string;
	hidden: boolean;
}

export interface Draft {
	name: string;
	kind: 'stdio' | 'http';
	command: string;
	args: string;
	env: Row[];
	cwd: string;
	url: string;
	headers: Row[];
	enabled: boolean;
}

export const blank = (): Draft => ({
	name: '',
	kind: 'stdio',
	command: '',
	args: '',
	env: [],
	cwd: '',
	url: '',
	headers: [],
	enabled: true
});

export function rows(record: Record<string, string | null>): Row[] {
	return Object.entries(record).map(([key, value]) => ({
		key,
		value: value ?? '',
		hidden: value === null
	}));
}

/** The server's record of it: a hidden value as `null`, a blank key dropped, the last of a
 * repeated key winning (an object cannot hold two). */
export function record(list: Row[]): Record<string, string | null> {
	const out: Record<string, string | null> = {};
	for (const row of list) {
		const key = row.key.trim();
		if (key) out[key] = row.hidden ? null : row.value;
	}
	return out;
}

/** One argument per line. Blank lines go; spaces inside a line are part of the argument. */
export function lines(text: string): string[] {
	return text
		.split('\n')
		.map((line) => line.replace(/\r$/, ''))
		.filter((line) => line.trim() !== '');
}

export function draftOf(name: string, entry: ServerEntry): Draft {
	return {
		name,
		kind: entry.kind,
		command: entry.command,
		args: entry.args.join('\n'),
		env: rows(entry.env),
		cwd: entry.cwd,
		url: entry.url,
		headers: rows(entry.headers),
		enabled: entry.enabled
	};
}

export function entryOf(draft: Draft): ServerEntry {
	return {
		kind: draft.kind,
		command: draft.command.trim(),
		args: lines(draft.args),
		env: record(draft.env),
		cwd: draft.cwd.trim(),
		url: draft.url.trim(),
		headers: record(draft.headers),
		enabled: draft.enabled
	};
}

/** What is missing before it can be saved, or `null`. The server checks the rest. */
export function missing(draft: Draft): 'name' | 'command' | 'url' | null {
	if (!draft.name.trim()) return 'name';
	if (draft.kind === 'stdio' && !draft.command.trim()) return 'command';
	if (draft.kind === 'http' && !draft.url.trim()) return 'url';
	return null;
}
