/**
 * The one rule this file has to keep: it transforms, it does not recognise. A table of known
 * *foreign* tools would make an unfamiliar server look broken next to a familiar one.
 *
 * `mark` is the single exception, and the tests below pin its edges rather than its middle:
 * what matters is not that `hera__search` gets a globe, it is that `docker__search` does not.
 */

import { describe, expect, it } from 'vitest';

import type { AnyEvent } from './api/events';
import { mark, markOf, subject, toolName } from './tools';

describe('toolName', () => {
	it('splits the server off the action', () => {
		expect(toolName('docker__mcp-find')).toEqual({
			server: 'Docker',
			action: 'mcp find',
			qualified: 'docker__mcp-find'
		});
	});

	it('opens up both separators', () => {
		expect(toolName('fs__read_file').action).toBe('read file');
	});

	it('leaves an unnamespaced tool alone', () => {
		expect(toolName('emotion')).toEqual({ server: '', action: 'emotion', qualified: 'emotion' });
	});

	it('treats her own tools like anybody elses', () => {
		expect(toolName('hera__skill')).toEqual({
			server: 'Hera',
			action: 'skill',
			qualified: 'hera__skill'
		});
	});

	it('keeps the qualified name, which is what a rule is written against', () => {
		expect(toolName('docker__fetch_content').qualified).toBe('docker__fetch_content');
	});

	it('does not invent a name for something that has none', () => {
		expect(toolName('').action).toBe('');
		expect(toolName('__odd').server).toBe('');
	});
});

describe('mark', () => {
	it('gives her own capabilities their own picture', () => {
		expect(mark('hera__skill')).toBe('skill');
		expect(mark('hera__search')).toBe('search');
		expect(mark('hera__note')).toBe('note');
		expect(mark('hera__remember')).toBe('memory');
	});

	it('refuses to recognise anybody elses server', () => {
		// The rule this whole file exists for. A server you have not configured yet must not be
		// drawn differently from one you have, or a missing setup looks like a broken one.
		expect(mark('docker__search')).toBe('tool');
		expect(mark('fs__note')).toBe('tool');
		expect(mark('search')).toBe('tool');
	});

	it('falls back to the wrench for a tool of hers it has never heard of', () => {
		// Adding a tool to hera_mcp must not be able to break this file.
		expect(mark('hera__invented_later')).toBe('tool');
	});

	it('reads a mark off a call or off its result', () => {
		expect(markOf({ type: 'tool_call_ready', name: 'hera__search' } as AnyEvent)).toBe('search');
		expect(markOf({ type: 'tool_result', tool: 'hera__search' } as AnyEvent)).toBe('search');
		expect(markOf({ type: 'thinking_delta', text: 'x' } as AnyEvent)).toBe('tool');
	});
});

describe('subject', () => {
	it('names what one of her calls was about', () => {
		// `skill rust-best-practices`, not `called Hera skill` — the mark has already said
		// whose tool it is, and the space is worth more spent on which skill.
		expect(subject('hera__skill', { name: 'rust-best-practices' })).toBe('rust-best-practices');
		expect(subject('hera__search', { query: 'llama.cpp tool grammar' })).toBe(
			'llama.cpp tool grammar'
		);
		expect(subject('hera__remember', { text: 'Void prefers short answers' })).toBe(
			'Void prefers short answers'
		);
	});

	it('falls past an argument that is there and empty', () => {
		// A note has a title only sometimes, and naming nothing is worse than naming the body.
		expect(subject('hera__note', { title: '', text: 'the plan' })).toBe('the plan');
		expect(subject('hera__note', { title: 'kerberos', text: 'x' })).toBe('kerberos');
	});

	it('takes the first argument of a tool of hers it has never heard of', () => {
		expect(subject('hera__invented_later', { url: 'https://example.test' })).toBe(
			'https://example.test'
		);
	});

	it('says nothing about somebody elses tool, which keeps its server name instead', () => {
		expect(subject('docker__mcp-find', { q: 'postgres' })).toBe('');
	});

	it('says nothing when there is nothing to say', () => {
		expect(subject('hera__skill', {})).toBe('');
		expect(subject('hera__search', { query: '   ' })).toBe('');
		expect(subject('hera__skill', { name: 42 })).toBe('');
	});
});
