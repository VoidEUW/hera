import { describe, expect, it } from 'vitest';
import { describePattern, qualified } from './permissions';

describe('describePattern', () => {
	it('reads a bare star as every tool', () => {
		expect(describePattern('*')).toEqual({ kind: 'everything' });
	});

	it('reads server__* as one whole server', () => {
		expect(describePattern('fs__*')).toEqual({ kind: 'server', server: 'fs' });
	});

	it('reads an exact name as one tool of one server', () => {
		expect(describePattern('fs__read_file')).toEqual({
			kind: 'tool',
			server: 'fs',
			tool: 'read_file'
		});
	});

	it('keeps a tool name that has underscores of its own whole', () => {
		expect(describePattern('git__show_ref__x')).toEqual({
			kind: 'tool',
			server: 'git',
			tool: 'show_ref__x'
		});
	});

	it('leaves anything it cannot paraphrase as the pattern itself', () => {
		for (const pattern of [
			'fs__read*',
			'*__write',
			'f?__x',
			'fs__[rw]ead',
			'nodoublescore',
			'__x'
		]) {
			expect(describePattern(pattern), pattern).toEqual({ kind: 'glob', pattern });
		}
	});

	it('is not fooled by a wildcard in the server part', () => {
		expect(describePattern('f*__read')).toEqual({ kind: 'glob', pattern: 'f*__read' });
	});
});

describe('qualified', () => {
	it('joins a server and a tool the way the namespace does', () => {
		expect(qualified('fs', 'read_file')).toBe('fs__read_file');
	});
});
