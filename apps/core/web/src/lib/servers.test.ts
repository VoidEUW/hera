import { describe, expect, it } from 'vitest';

import type { ServerEntry } from './api/client';
import { blank, draftOf, entryOf, lines, missing, record, rows } from './servers';

const stored: ServerEntry = {
	kind: 'stdio',
	command: 'npx',
	args: ['-y', 'thing'],
	env: { TOKEN: '${GH}', SECRET: null },
	cwd: '',
	url: '',
	headers: {},
	enabled: true
};

describe('rows', () => {
	it('marks a value the server kept back as hidden, and not as empty', () => {
		expect(rows({ A: 'x', B: null })).toEqual([
			{ key: 'A', value: 'x', hidden: false },
			{ key: 'B', value: '', hidden: true }
		]);
	});

	it('sends a hidden value back as null so the server keeps it', () => {
		expect(record(rows({ B: null }))).toEqual({ B: null });
	});

	it('sends a replacement once it is typed', () => {
		expect(record([{ key: 'B', value: 'new', hidden: false }])).toEqual({ B: 'new' });
	});

	it('drops a row with no key and lets the last of a repeated key win', () => {
		expect(
			record([
				{ key: ' ', value: 'x', hidden: false },
				{ key: 'A', value: '1', hidden: false },
				{ key: 'A', value: '2', hidden: false }
			])
		).toEqual({ A: '2' });
	});
});

describe('lines', () => {
	it('is one argument per line, blank lines gone, inner spaces kept', () => {
		expect(lines('-y\n\n  \n--root=/my files\r\nlast')).toEqual(['-y', '--root=/my files', 'last']);
	});
});

describe('a draft', () => {
	it('survives a round trip without losing a hidden secret', () => {
		const back = entryOf(draftOf('gh', stored));
		expect(back).toEqual(stored);
	});

	it('trims what is typed but not what is an argument', () => {
		const draft = { ...blank(), name: 'x', command: '  uvx ', args: ' a b ' };
		const entry = entryOf(draft);
		expect(entry.command).toBe('uvx');
		expect(entry.args).toEqual([' a b ']);
	});
});

describe('missing', () => {
	it('asks for a name, then for what the kind needs', () => {
		expect(missing(blank())).toBe('name');
		expect(missing({ ...blank(), name: 'a' })).toBe('command');
		expect(missing({ ...blank(), name: 'a', command: 'x' })).toBeNull();
		expect(missing({ ...blank(), name: 'a', kind: 'http' })).toBe('url');
		expect(missing({ ...blank(), name: 'a', kind: 'http', url: 'https://e.test/mcp' })).toBeNull();
	});
});
