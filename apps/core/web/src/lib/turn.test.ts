/**
 * The reducer, which is the one piece of real logic in the browser.
 *
 * The property that matters most is at the bottom: reducing the live stream and reducing the
 * persisted list produce the same thing. That is what "the server render is authoritative"
 * means in practice — if they differed, an answer would visibly change the instant it finished.
 */

import { describe, expect, it } from 'vitest';

import type { AnyEvent } from './api/events';
import { reduce } from './turn';

const text = (t: string): AnyEvent => ({ type: 'text_delta', text: t });
const closed = (reason = 'completed'): AnyEvent => ({
	type: 'turn_closed',
	reason,
	usage: null,
	iterations: 1,
	error: ''
});
const call = (id: string, name: string, args: Record<string, unknown> = {}): AnyEvent => ({
	type: 'tool_call_ready',
	id,
	name,
	arguments: args,
	raw_arguments: '',
	parse_error: null
});
const result = (callId: string, tool: string, over: Record<string, unknown> = {}): AnyEvent => ({
	type: 'tool_result',
	call_id: callId,
	tool,
	ok: true,
	failure: null,
	text: 'done',
	structured: null,
	blocks: [],
	duration_ms: 12,
	...over
});

describe('prose', () => {
	it('joins the fragments of an answer', () => {
		const turn = reduce([text('Hel'), text('lo.'), closed()]);
		expect(turn.inline.map((item) => [item.kind, item.text])).toEqual([['prose', 'Hello.']]);
	});

	it('leaves the thinking out of the prose', () => {
		const turn = reduce([{ type: 'thinking_delta', text: 'hmm' }, text('Yes.'), closed()]);
		expect(turn.inline.map((i) => i.text)).toEqual(['Yes.']);
		expect(turn.thinking).toBe('hmm');
	});

	it('collapses every thinking fragment into one gutter row', () => {
		const turn = reduce([
			{ type: 'thinking_delta', text: 'a' },
			{ type: 'thinking_delta', text: 'b' },
			text('Yes.')
		]);
		expect(turn.activity.filter((row) => row.kind === 'thinking')).toHaveLength(1);
		expect(turn.thinking).toBe('ab');
	});
});

describe('the activity gutter', () => {
	it('shows a skill with the reason it was chosen', () => {
		const turn = reduce([
			{ type: 'skill_selected', skill: 'tdd', reason: 'pinned', score: null },
			text('ok')
		]);
		expect(turn.activity[0].kind).toBe('skill');
	});

	it('pairs a tool result with the call that produced it', () => {
		const turn = reduce([call('c1', 'fs__read_file'), result('c1', 'fs__read_file'), text('ok')]);

		expect(turn.activity).toHaveLength(1);
		expect(turn.activity[0].result?.text).toBe('done');
	});

	it('leaves a call without a result unpaired, which is what "running" renders from', () => {
		const turn = reduce([call('c1', 'fs__read_file')]);
		expect(turn.activity[0].result).toBeUndefined();
	});

	it('keeps a result whose call it never saw', () => {
		// Half a turn, reloaded after a cancellation. Dropping it would hide the one record of
		// something that actually ran.
		const turn = reduce([result('c9', 'fs__read_file')]);
		expect(turn.activity).toHaveLength(1);
	});

	it('shows an unknown variant rather than dropping it', () => {
		// An interface that silently drops what it does not recognise is one where a missing
		// feature and a broken one look identical.
		const turn = reduce([{ type: 'invented_later', detail: 'x' } as AnyEvent, closed()]);
		expect(turn.activity.map((row) => row.kind)).toEqual(['unknown']);
	});
});

describe('emotions', () => {
	it('renders inline, where she called it', () => {
		const turn = reduce([
			text('Before. '),
			call('e1', 'hera__emotion', { kind: 'doubt', text: 'Slide 14 contradicts slide 9.' }),
			text('After.'),
			closed()
		]);

		expect(turn.inline.map((i) => i.kind)).toEqual(['prose', 'emotion', 'prose']);
		expect(turn.activity).toHaveLength(0);
	});

	it('never appears in the gutter', () => {
		const turn = reduce([call('e1', 'hera__emotion', { kind: 'agree' })]);
		expect(turn.activity).toHaveLength(0);
	});
});

describe('permission cards', () => {
	const card: AnyEvent = {
		type: 'permission_required',
		call_id: 'c1',
		tool: 'fs__write_file',
		arguments: { path: 'a' },
		reason: 'it writes to disk'
	};

	it('blocks while unanswered', () => {
		const turn = reduce([call('c1', 'fs__write_file'), card, closed('awaiting_permission')]);
		expect(turn.awaiting).toHaveLength(1);
	});

	it('stops blocking once it has been decided', () => {
		// Read from the persisted decision rather than inferred from a later result: an
		// ordering rule living in the browser is what this design exists to avoid.
		const turn = reduce([
			call('c1', 'fs__write_file'),
			card,
			{ type: 'permission_decided', call_id: 'c1', allowed: true, remembered: false },
			result('c1', 'fs__write_file'),
			text('done'),
			closed()
		]);

		expect(turn.awaiting).toHaveLength(0);
		expect(turn.activity[0].result).toBeDefined();
	});
});

describe('the terminator', () => {
	it('is null while the turn is running', () => {
		expect(reduce([text('partial')]).closed).toBeNull();
	});

	it('carries the reason a turn ended badly', () => {
		const turn = reduce([{ ...closed('failed'), error: 'endpoint unreachable' } as AnyEvent]);
		expect(turn.closed?.reason).toBe('failed');
		expect(turn.closed?.error).toBe('endpoint unreachable');
	});
});

describe('the live view and the reload cannot disagree', () => {
	it('reduces a coalesced list to the same thing as the streamed one', () => {
		// The server stores one text_delta where it streamed three. Same variant, different
		// count -- and the reducer has to be blind to the difference or an answer would
		// visibly change the moment it finished.
		const streamed = [text('Hel'), text('lo, '), text('world.'), closed()];
		const persisted = [text('Hello, world.'), closed()];

		expect(reduce(persisted).inline.map((i) => i.text)).toEqual(
			reduce(streamed).inline.map((i) => i.text)
		);
	});

	it('is stable across a whole turn with tools in it', () => {
		const streamed = [
			{ type: 'skill_selected', skill: 'tdd', reason: 'slash', score: null } as AnyEvent,
			text('Let me '),
			text('look. '),
			call('c1', 'fs__read_file'),
			result('c1', 'fs__read_file'),
			text('It says done.'),
			closed()
		];
		const persisted = [
			{ type: 'skill_selected', skill: 'tdd', reason: 'slash', score: null } as AnyEvent,
			text('Let me look. '),
			call('c1', 'fs__read_file'),
			result('c1', 'fs__read_file'),
			text('It says done.'),
			closed()
		];

		const a = reduce(streamed);
		const b = reduce(persisted);

		expect(a.inline.map((i) => [i.kind, i.text])).toEqual(b.inline.map((i) => [i.kind, i.text]));
		expect(a.activity.map((r) => r.kind)).toEqual(b.activity.map((r) => r.kind));
	});
});

describe('an emotion is drawn once', () => {
	const emotion = call('e1', 'hera__emotion', { kind: 'agree' });

	it('does not also get a gutter row for its result', () => {
		// The card *is* the record. A row beside it draws the same thing twice.
		const turn = reduce([emotion, result('e1', 'hera__emotion'), text('ok'), closed()]);

		expect(turn.inline.map((i) => i.kind)).toEqual(['emotion', 'prose']);
		expect(turn.activity).toHaveLength(0);
	});

	it('keeps the row when the call failed', () => {
		// An emotion she showed and the system refused is exactly what openness means you see.
		const turn = reduce([
			emotion,
			result('e1', 'hera__emotion', { ok: false, failure: 'denied', text: 'not allowed' }),
			closed()
		]);

		expect(turn.inline.map((i) => i.kind)).toEqual(['emotion']);
		expect(turn.activity).toHaveLength(1);
	});
});
