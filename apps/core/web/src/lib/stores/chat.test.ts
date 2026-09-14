/**
 * `ChatSession.usage` — the composer's context-window bar reads this. The one piece of new
 * branching logic this feature adds to the store (everything else is markup): which event list
 * to read usage off of, live versus after a reload.
 */

import { describe, expect, it } from 'vitest';

import type { AnyEvent } from '../api/events';
import type { Message } from '../api/client';
import { ChatSession } from './chat.svelte';

const usage = (total: number): AnyEvent => ({
	type: 'turn_closed',
	reason: 'completed',
	usage: { prompt_tokens: total - 1, completion_tokens: 1, total_tokens: total },
	iterations: 1,
	error: ''
});

const message = (over: Partial<Message>): Message => ({
	id: 'm1',
	role: 'assistant',
	content: 'hi',
	sequence: 1,
	created_at: '',
	events: [],
	attachments: [],
	...over
});

describe('usage', () => {
	it('is null before anything has been said', () => {
		const session = new ChatSession();
		expect(session.usage).toBeNull();
	});

	it('reads the live turn once it has closed with usage', () => {
		const session = new ChatSession();
		session.draft = [usage(120)];
		expect(session.usage?.total_tokens).toBe(120);
	});

	it('keeps the previous total while a new turn is streaming, rather than dropping to zero', () => {
		const session = new ChatSession();
		session.messages = [
			message({ id: 'a', role: 'user', content: 'hi', sequence: 1 }),
			message({ id: 'b', role: 'assistant', sequence: 2, events: [usage(340)] })
		];
		// A turn in flight has events but no `turn_closed` yet — that only arrives at the very
		// end of the stream.
		session.draft = [{ type: 'text_delta', text: 'thinking…' }];
		expect(session.usage?.total_tokens).toBe(340);
	});

	it('falls back to the last persisted message once the draft is cleared', () => {
		const session = new ChatSession();
		session.messages = [
			message({ id: 'a', role: 'user', content: 'hi', sequence: 1 }),
			message({ id: 'b', role: 'assistant', sequence: 2, events: [usage(340)] })
		];
		expect(session.usage?.total_tokens).toBe(340);
	});

	it('is null when the last message is the person’s own, not an answer', () => {
		const session = new ChatSession();
		session.messages = [message({ role: 'user', content: 'hi', events: [] })];
		expect(session.usage).toBeNull();
	});

	it('is null when the endpoint never reported usage', () => {
		const session = new ChatSession();
		session.messages = [
			message({
				events: [
					{ type: 'turn_closed', reason: 'completed', usage: null, iterations: 1, error: '' }
				]
			})
		];
		expect(session.usage).toBeNull();
	});
});
