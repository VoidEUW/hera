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

	it('collapses adjacent thinking fragments into one gutter row', () => {
		const turn = reduce([
			{ type: 'thinking_delta', text: 'a' },
			{ type: 'thinking_delta', text: 'b' },
			text('Yes.')
		]);
		expect(turn.activity.filter((row) => row.kind === 'thinking')).toHaveLength(1);
		expect(turn.thinking).toBe('ab');
	});

	it('opens a new block after a tool call, so the trace reads downwards', () => {
		// The reason this matters: she thinks, calls something, reads the answer and thinks
		// again. Appending the second stretch to the first puts it *above* the call that
		// caused it, and the turn can no longer be read in order.
		const turn = reduce([
			{ type: 'thinking_delta', text: 'before' },
			call('c1', 'fs__read_file'),
			result('c1', 'fs__read_file'),
			{ type: 'thinking_delta', text: 'after' },
			text('Yes.'),
			closed()
		]);

		expect(turn.activity.map((row) => row.kind)).toEqual(['thinking', 'tool', 'thinking']);
		expect(turn.activity.map((row) => (row.event as { text?: string }).text)).toEqual([
			'before',
			undefined,
			'after'
		]);
		// The whole turn's reasoning is still available as one string.
		expect(turn.thinking).toBe('beforeafter');
	});

	it('opens a new block after prose, so two thoughts do not run into one sentence', () => {
		// `…I can answer now.Nothing more to add…` — one row, no seam on screen, and the join
		// invented a sentence neither half contained.
		const turn = reduce([
			{ type: 'thinking_delta', text: 'I can answer now.' },
			text('Kerberos issues a ticket.'),
			{ type: 'thinking_delta', text: 'Nothing more to add.' },
			closed()
		]);

		expect(turn.activity.map((row) => (row.event as { text?: string }).text)).toEqual([
			'I can answer now.',
			'Nothing more to add.'
		]);
	});

	it('opens a new block after an emotion, which is on screen even though it is not a row', () => {
		const turn = reduce([
			{ type: 'thinking_delta', text: 'a' },
			call('e1', 'hera__emotion', { kind: 'agree' }),
			{ type: 'thinking_delta', text: 'b' },
			closed()
		]);
		expect(turn.activity.map((row) => row.kind)).toEqual(['thinking', 'thinking']);
	});

	it('leaves a block alone for bookkeeping nobody can see', () => {
		// `permission_decided` and `turn_closed` draw nothing. Splitting on those would put a
		// seam in her reasoning with nothing on screen to account for it.
		const turn = reduce([
			{ type: 'thinking_delta', text: 'a' },
			{ type: 'permission_decided', call_id: 'c1', allowed: true, remembered: false },
			{ type: 'thinking_delta', text: 'b' },
			closed()
		]);
		expect(turn.activity.map((row) => row.kind)).toEqual(['thinking']);
		expect((turn.activity[0].event as { text: string }).text).toBe('ab');
	});

	it('gives every block its own key so the rows are not confused for each other', () => {
		const turn = reduce([
			{ type: 'thinking_delta', text: 'a' },
			call('c1', 'fs__read_file'),
			{ type: 'thinking_delta', text: 'b' }
		]);
		const keys = turn.activity.map((row) => row.key);
		expect(new Set(keys).size).toBe(keys.length);
	});

	it('keeps a block’s key while it is still being written', () => {
		// The reducer runs again on every fragment that arrives. A key built from where the
		// block *ends* changes each time, Svelte rebuilds the row, and everything the component
		// was holding goes with it — which is why a thought could not be opened while she was
		// still having it.
		const growing = (...texts: string[]) =>
			reduce(texts.map((text) => ({ type: 'thinking_delta', text }) as AnyEvent));

		expect(growing('Che').activity[0].key).toBe(
			growing('Che', 'ck the', ' notes.').activity[0].key
		);
	});

	it('keeps a run of prose keyed from where it started, for the same reason', () => {
		expect(reduce([text('Hel')]).inline[0].key).toBe(
			reduce([text('Hel'), text('lo.')]).inline[0].key
		);
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

	it('agrees about where a block of reasoning ends', () => {
		// The rule here has to be the server's rule: `hera_chats.coalesce` merges consecutive
		// fragments and anything between two of them stops the merge. If the browser drew its
		// blocks by any other rule, the number of gutter rows would change at `done`.
		const streamed = [
			{ type: 'thinking_delta', text: 'Check ' } as AnyEvent,
			{ type: 'thinking_delta', text: 'the notes.' } as AnyEvent,
			call('c1', 'fs__read_file'),
			result('c1', 'fs__read_file'),
			{ type: 'thinking_delta', text: 'That ' } as AnyEvent,
			{ type: 'thinking_delta', text: 'settles it.' } as AnyEvent,
			text('Done.'),
			closed()
		];
		const persisted = [
			{ type: 'thinking_delta', text: 'Check the notes.' } as AnyEvent,
			call('c1', 'fs__read_file'),
			result('c1', 'fs__read_file'),
			{ type: 'thinking_delta', text: 'That settles it.' } as AnyEvent,
			text('Done.'),
			closed()
		];

		const shape = (events: AnyEvent[]) =>
			reduce(events).activity.map((r) => [r.kind, (r.event as { text?: string }).text]);

		expect(shape(streamed)).toEqual(shape(persisted));
		expect(shape(persisted)).toEqual([
			['thinking', 'Check the notes.'],
			['tool', undefined],
			['thinking', 'That settles it.']
		]);
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

describe('a block still being written', () => {
	it('is marked live when the list runs out mid-thought', () => {
		const turn = reduce([{ type: 'thinking_delta', text: 'still going' }]);
		expect(turn.activity[0].live).toBe(true);
	});

	it('is not marked on a block something else already closed', () => {
		const turn = reduce([
			{ type: 'thinking_delta', text: 'before' },
			call('c1', 'fs__read_file'),
			{ type: 'thinking_delta', text: 'after' }
		]);
		expect(turn.activity.map((row) => row.live)).toEqual([false, undefined, true]);
	});

	it('still marks the last block of a finished turn, which is why the caller also checks the stream', () => {
		// `turn_closed` draws nothing and so does not close a block. The flag means "the list
		// ended here", not "she is still thinking" — pairing it with `streaming` is what makes
		// the second claim, and a reloaded turn must not preview anything.
		const turn = reduce([{ type: 'thinking_delta', text: 'done' }, closed()]);
		expect(turn.activity[0].live).toBe(true);
	});
});
