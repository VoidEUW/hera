/**
 * The reducer, which is the one piece of real logic in the browser.
 *
 * The property that matters most is at the bottom: reducing the live stream and reducing the
 * persisted list produce the same thing. That is what "the server render is authoritative"
 * means in practice — if they differed, an answer would visibly change the instant it finished.
 */

import { describe, expect, it } from 'vitest';

import type { AnyEvent } from './api/events';
import { isAnswered, reduce, replyTo } from './turn';

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
const started = (id: string, name: string): AnyEvent => ({ type: 'tool_call_started', id, name });
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

	it('opens a new block after a card, which is on screen even though it is not a row', () => {
		const turn = reduce([
			{ type: 'thinking_delta', text: 'a' },
			call('q1', 'hera__ask'),
			{
				type: 'answer_required',
				call_id: 'q1',
				tool: 'hera__ask',
				question: 'Which deck?',
				kind: 'choice'
			},
			{ type: 'thinking_delta', text: 'b' },
			closed('awaiting_answer')
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

describe('question cards', () => {
	const asked: AnyEvent = {
		type: 'answer_required',
		call_id: 'q1',
		tool: 'hera__ask',
		question: 'Which deck?',
		kind: 'unsure'
	};

	it('renders inline, where she asked it', () => {
		const turn = reduce([
			text('Before I start — '),
			call('q1', 'hera__ask'),
			asked,
			closed('awaiting_answer')
		]);

		expect(turn.inline.map((item) => item.kind)).toEqual(['prose', 'question']);
	});

	it('blocks the composer while unanswered', () => {
		const turn = reduce([call('q1', 'hera__ask'), asked, closed('awaiting_answer')]);
		expect(turn.awaiting).toHaveLength(1);
	});

	it('draws the question once, not three times', () => {
		// The call, the card and the synthesised result are all about the same question. Only
		// the card is a thing a person is meant to read.
		const turn = reduce([
			call('q1', 'hera__ask'),
			asked,
			{ type: 'answer_given', call_id: 'q1', text: 'The 2024 one.' },
			result('q1', 'hera__ask', { text: 'The 2024 one.' }),
			text('Right.'),
			closed()
		]);

		expect(turn.activity).toHaveLength(0);
		expect(turn.inline.filter((item) => item.kind === 'question')).toHaveLength(1);
	});

	it('stops blocking once it has been replied to', () => {
		const events = [
			call('q1', 'hera__ask'),
			asked,
			{ type: 'answer_given', call_id: 'q1', text: 'The 2024 one.' } as AnyEvent,
			result('q1', 'hera__ask'),
			closed()
		];

		expect(reduce(events).awaiting).toHaveLength(0);
		expect(isAnswered(events, 'q1')).toBe(true);
		expect(replyTo(events, 'q1')).toBe('The 2024 one.');
	});

	it('leaves an unanswered question with no reply to show', () => {
		const events = [call('q1', 'hera__ask'), asked, closed('awaiting_answer')];
		expect(isAnswered(events, 'q1')).toBe(false);
		expect(replyTo(events, 'q1')).toBe('');
	});
});

describe('a turn is one list, in order', () => {
	const think = (t: string): AnyEvent => ({ type: 'thinking_delta', text: t });

	it('puts a second thought below the sentence that prompted it', () => {
		// The bug this replaced: every gutter row was drawn first and all the prose after, so a
		// turn that speaks, thinks again and speaks again showed the second thought above the
		// first answer — and could not be read downwards at all.
		const turn = reduce([
			think('first'),
			text('An answer.'),
			think('second'),
			text('More.'),
			closed()
		]);

		expect(turn.blocks.map((b) => b.kind)).toEqual(['gutter', 'prose', 'gutter', 'prose']);
	});

	it('groups consecutive rows into one block', () => {
		const turn = reduce([
			think('planning'),
			call('c1', 'fs__read_file'),
			result('c1', 'fs__read_file'),
			text('Done.'),
			closed()
		]);

		const gutters = turn.blocks.filter((b) => b.kind === 'gutter');
		expect(gutters).toHaveLength(1);
		expect(gutters[0].kind === 'gutter' && gutters[0].rows.map((r) => r.kind)).toEqual([
			'thinking',
			'tool'
		]);
	});

	it('does not let prose written after a tool call jump above it', () => {
		// Prose used to accumulate across a tool call and land as one block, so the call showed
		// up after both halves of what it produced.
		const turn = reduce([
			text('Looking that up.'),
			call('c1', 'fs__read_file'),
			result('c1', 'fs__read_file'),
			text('It said so.'),
			closed()
		]);

		expect(turn.blocks.map((b) => b.kind)).toEqual(['prose', 'gutter', 'prose']);
	});

	it('keeps the flat views as views over the same list', () => {
		const turn = reduce([think('a'), text('one'), think('b'), text('two'), closed()]);

		expect(turn.activity).toHaveLength(2);
		expect(turn.inline).toHaveLength(2);
		expect(turn.activity.every((row) => row.kind === 'thinking')).toBe(true);
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

describe('a call she has begun but not finished writing', () => {
	// `tool_call_started` carries the name and nothing else, and arrives as soon as the model
	// has named the call — which on a real endpoint is minutes before the arguments finish when
	// the arguments are a document. It is never persisted, so these tests are also the contract
	// that a reload draws the same rows from strictly fewer events.

	it('draws a running row as soon as she names it', () => {
		const turn = reduce([started('c1', 'hera__scratch_write')]);

		expect(turn.activity.map((row) => [row.kind, row.event.type])).toEqual([
			['tool', 'tool_call_started']
		]);
		expect(turn.activity[0].result).toBeUndefined();
	});

	it('fills the same row in rather than drawing a second one', () => {
		const turn = reduce([
			started('c1', 'hera__scratch_write'),
			call('c1', 'hera__scratch_write', { name: 'plan.md' }),
			closed()
		]);

		expect(turn.activity).toHaveLength(1);
		expect(turn.activity[0].event.type).toBe('tool_call_ready');
	});

	it('keeps the row key stable across the two, so nothing is rebuilt mid-turn', () => {
		const begun = reduce([started('c1', 'fs__read_file')]);
		const done = reduce([started('c1', 'fs__read_file'), call('c1', 'fs__read_file'), closed()]);

		expect(begun.activity[0].key).toBe(done.activity[0].key);
	});

	it('still pairs the result with it', () => {
		const turn = reduce([
			started('c1', 'fs__read_file'),
			call('c1', 'fs__read_file'),
			result('c1', 'fs__read_file'),
			closed()
		]);

		expect(turn.activity).toHaveLength(1);
		expect(turn.activity[0].result?.call_id).toBe('c1');
	});

	it('reduces to the same rows as the persisted list, which has no started event', () => {
		// The property the whole design rests on. A reload has strictly fewer events and has to
		// draw the same turn; if it did not, the answer would visibly change at `done`.
		const live = reduce([
			text('Let me look. '),
			started('c1', 'fs__read_file'),
			call('c1', 'fs__read_file', { path: 'a' }),
			result('c1', 'fs__read_file'),
			text('It says so.'),
			closed()
		]);
		const stored = reduce([
			text('Let me look. '),
			call('c1', 'fs__read_file', { path: 'a' }),
			result('c1', 'fs__read_file'),
			text('It says so.'),
			closed()
		]);

		// Kinds and content, which is the guarantee this file has always made — not keys. Those
		// already differ between the two lists because the server coalesces text, and a prose
		// block being rebuilt at `done` is invisible. What must not differ is how many rows
		// there are and what they say.
		expect(live.blocks.map((b) => b.kind)).toEqual(stored.blocks.map((b) => b.kind));
		expect(live.inline.map((i) => [i.kind, i.text])).toEqual(
			stored.inline.map((i) => [i.kind, i.text])
		);
		expect(live.activity.map((r) => r.event)).toEqual(stored.activity.map((r) => r.event));
	});

	it('draws no gutter row for a question she has begun', () => {
		const turn = reduce([
			started('a1', 'hera__ask'),
			call('a1', 'hera__ask', { question: 'Which deck?' }),
			{
				type: 'answer_required',
				call_id: 'a1',
				tool: 'hera__ask',
				question: 'Which deck?',
				kind: ''
			},
			closed('awaiting_answer')
		]);

		expect(turn.activity).toHaveLength(0);
		expect(turn.inline.map((i) => i.kind)).toEqual(['question']);
	});

	it('leaves a call that never finished arriving as a running row', () => {
		// What the reader sees when the endpoint stops answering mid-argument. Nothing is
		// persisted for it, which is correct: the call never ran.
		const turn = reduce([started('c1', 'hera__scratch_write'), closed('failed')]);

		expect(turn.activity[0].result).toBeUndefined();
		expect(turn.closed?.reason).toBe('failed');
	});
});

describe('what she published', () => {
	const published = (callId: string, name: string, inline = false, bytes = 11): AnyEvent =>
		result(callId, 'hera__artifact_create', {
			text: `published ${name} (${bytes} bytes)`,
			structured: { artifact: { name, inline, bytes } }
		});

	it('draws a card in the flow of the answer', () => {
		const turn = reduce([
			text('Here it is.'),
			call('a1', 'hera__artifact_create', { name: 'page.html', content: '<h1>Hi</h1>' }),
			published('a1', 'page.html'),
			closed()
		]);

		const card = turn.inline.find((item) => item.kind === 'artifact');
		expect(card?.artifact).toEqual({ name: 'page.html', inline: false, bytes: 11 });
	});

	it('keeps the gutter row for the call as well', () => {
		// The row is the act and how long it took; the card is the thing. While 40 KB of
		// arguments are still arriving, the row is the only thing on screen — which is the whole
		// reason `tool_call_started` exists.
		const turn = reduce([
			started('a1', 'hera__artifact_create'),
			call('a1', 'hera__artifact_create', { name: 'page.html', content: 'x' }),
			published('a1', 'page.html'),
			closed()
		]);

		expect(turn.activity.map((row) => row.kind)).toEqual(['tool']);
		expect(turn.activity[0].result).toBeDefined();
		expect(turn.inline.filter((item) => item.kind === 'artifact')).toHaveLength(1);
	});

	it('lands after the prose that introduced it rather than above it', () => {
		const turn = reduce([
			text('Have a look:'),
			call('a1', 'hera__artifact_create', { name: 'flow.svg', content: '<svg/>' }),
			published('a1', 'flow.svg', true),
			text('The middle step is the slow one.'),
			closed()
		]);

		expect(turn.blocks.map((block) => block.kind)).toEqual([
			'prose',
			'gutter',
			'artifact',
			'prose'
		]);
	});

	it('carries the inline flag the model chose', () => {
		const turn = reduce([published('a1', 'flow.svg', true), closed()]);

		expect(turn.inline.find((item) => item.kind === 'artifact')?.artifact?.inline).toBe(true);
	});

	it('draws nothing for an edit, because the card already shows the file', () => {
		// An artifact has one current state everywhere it appears (ADR 13): editing it in turn
		// nine changes what the card in turn four draws, so a second card would be one file
		// drawn twice.
		const turn = reduce([
			call('a2', 'hera__artifact_edit', { name: 'page.html', find: 'red', replace: 'brass' }),
			result('a2', 'hera__artifact_edit', { text: 'edited page.html (5 bytes)' }),
			closed()
		]);

		expect(turn.inline.filter((item) => item.kind === 'artifact')).toHaveLength(0);
		expect(turn.activity.map((row) => row.kind)).toEqual(['tool']);
	});

	it('ignores a foreign tool that happens to answer with an artifact key', () => {
		// `hera__*` is her namespace and this is the one thing the interface is allowed to know
		// about it. A server called `notion` using the word "artifact" for something else must
		// not put a card in her transcript.
		const turn = reduce([
			result('x1', 'notion__export', { structured: { artifact: { name: 'page.html' } } }),
			closed()
		]);

		expect(turn.inline.filter((item) => item.kind === 'artifact')).toHaveLength(0);
	});

	it('draws no card for a publish that failed', () => {
		const turn = reduce([
			result('a1', 'hera__artifact_create', {
				ok: false,
				failure: 'tool_error',
				text: 'that filename is too long',
				structured: null
			}),
			closed()
		]);

		expect(turn.inline.filter((item) => item.kind === 'artifact')).toHaveLength(0);
		expect(turn.activity.map((row) => row.kind)).toEqual(['tool']);
	});

	it('reduces to the same blocks streamed and reloaded', () => {
		// The persisted list has no `tool_call_started` in it, so this is the property the whole
		// file exists for, applied to the newest variant.
		const live = [
			text('Here:'),
			started('a1', 'hera__artifact_create'),
			call('a1', 'hera__artifact_create', { name: 'page.html', content: 'x' }),
			published('a1', 'page.html'),
			closed()
		];
		const stored = live.filter((event) => event.type !== 'tool_call_started');

		expect(reduce(stored).blocks.map((block) => block.kind)).toEqual(
			reduce(live).blocks.map((block) => block.kind)
		);
	});
});
