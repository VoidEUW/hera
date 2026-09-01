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
		expect(toolName('ping')).toEqual({ server: '', action: 'ping', qualified: 'ping' });
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
		expect(mark('hera__forget')).toBe('memory');
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
		// The key, not the text: a memory is a paragraph and the row is one line — and the key
		// is what you would go looking for on Settings → Memory afterwards.
		expect(
			subject('hera__remember', {
				key: 'prefers-short-answers',
				text: 'They want two sentences, not five.'
			})
		).toBe('prefers-short-answers');
		expect(subject('hera__forget', { key: 'prefers-short-answers' })).toBe('prefers-short-answers');
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

describe('the scratchpad in the gutter', () => {
	it('draws all three of its calls with the quill', () => {
		// Writing something down and reading it back are one habit to a reader. Two marks for
		// one habit would make the second look like a different capability.
		expect(mark('hera__scratch_write')).toBe('note');
		expect(mark('hera__scratch_read')).toBe('note');
		expect(mark('hera__scratch_list')).toBe('note');
		expect(mark('hera__note')).toBe('note');
	});

	it('names the file, never the body', () => {
		// A write is a whole document and the row is one line.
		expect(subject('hera__scratch_write', { name: 'plan.md', text: '1. read it' })).toBe('plan.md');
		expect(subject('hera__scratch_read', { name: 'plan.md' })).toBe('plan.md');
	});

	it('says nothing for a listing, which takes no arguments', () => {
		expect(subject('hera__scratch_list', {})).toBe('');
	});
});

describe('artifacts in the gutter', () => {
	it('draws all three of its calls with the stele', () => {
		// The same reasoning as the scratchpad above, and the distinction between the two marks
		// is the one ADR 12 and ADR 13 are built on: the quill is where she thinks, unread, and
		// the stele is what she puts up for you to read.
		expect(mark('hera__artifact_create')).toBe('artifact');
		expect(mark('hera__artifact_edit')).toBe('artifact');
		expect(mark('hera__artifact_read')).toBe('artifact');
	});

	it('is not the same mark as the scratchpad', () => {
		expect(mark('hera__artifact_create')).not.toBe(mark('hera__scratch_write'));
	});

	it('does not recognise a foreign server that names a tool the same way', () => {
		expect(mark('notion__artifact_create')).toBe('tool');
	});

	it('names the file, never the page', () => {
		// The one that matters: `content` is 40 KB of HTML, and the fallback of *first string
		// argument* would put all of it through a row that ends in an ellipsis.
		expect(
			subject('hera__artifact_create', { name: 'page.html', content: '<h1>'.repeat(4000) })
		).toBe('page.html');
		expect(
			subject('hera__artifact_edit', { name: 'page.html', find: 'red', replace: 'brass' })
		).toBe('page.html');
		expect(subject('hera__artifact_read', { name: 'page.html' })).toBe('page.html');
	});
});
