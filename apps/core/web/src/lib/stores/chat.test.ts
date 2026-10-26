/**
 * `ChatSession.usage` — the composer's context-window bar reads this. The one piece of new
 * branching logic this feature adds to the store (everything else is markup): which event list
 * to read usage off of, live versus after a reload.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';

import type { AnyEvent } from '../api/events';
import type { Chat, ChatDetail, Message } from '../api/client';
import { ChatSession } from './chat.svelte';

function deferred<T>() {
	let resolve!: (value: T) => void;
	const promise = new Promise<T>((r) => {
		resolve = r;
	});
	return { promise, resolve };
}

function chatDetail(id: string): ChatDetail {
	const chat: Chat = {
		id,
		title: id,
		project_id: null,
		profile_id: null,
		pinned: false,
		pinned_skills: [],
		created_at: '',
		last_message_at: null
	};
	return { chat, messages: [] };
}

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

describe('context', () => {
	it('is null before anything has been said', () => {
		const session = new ChatSession();
		expect(session.context).toBeNull();
	});

	it('reads the live turn once it has closed with usage', () => {
		const session = new ChatSession();
		session.draft = [usage(120)];
		expect(session.context).toBe(120);
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
		expect(session.context).toBe(340);
	});

	it('falls back to the last persisted message once the draft is cleared', () => {
		const session = new ChatSession();
		session.messages = [
			message({ id: 'a', role: 'user', content: 'hi', sequence: 1 }),
			message({ id: 'b', role: 'assistant', sequence: 2, events: [usage(340)] })
		];
		expect(session.context).toBe(340);
	});

	it('is null when the last message is the person’s own, not an answer', () => {
		const session = new ChatSession();
		session.messages = [message({ role: 'user', content: 'hi', events: [] })];
		expect(session.context).toBeNull();
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
		expect(session.context).toBeNull();
	});

	it('is the last round, not the turn’s total, when the turn recorded it', () => {
		// Three tool rounds at about 10k each: 30k spent, 10k in the window.
		const session = new ChatSession();
		session.draft = [
			{
				type: 'turn_closed',
				reason: 'completed',
				usage: { prompt_tokens: 30_300, completion_tokens: 380, total_tokens: 30_680 },
				context_tokens: 10_500,
				iterations: 3,
				error: ''
			}
		];
		expect(session.context).toBe(10_500);
	});
});

describe('open', () => {
	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('drops a chat load that resolves after a faster later switch already landed', async () => {
		const pending = new Map<string, ReturnType<typeof deferred<Response>>>();
		vi.stubGlobal('fetch', (url: string) => {
			const id = url.split('/').pop() as string;
			const waiter = deferred<Response>();
			pending.set(id, waiter);
			return waiter.promise;
		});

		const session = new ChatSession();
		const first = session.open('a');
		const second = session.open('b');

		// 'b' answers before 'a' does, even though 'a' was asked for first.
		pending.get('b')!.resolve(new Response(JSON.stringify(chatDetail('b'))));
		await second;
		pending.get('a')!.resolve(new Response(JSON.stringify(chatDetail('a'))));
		await first;

		expect(session.chat?.id).toBe('b');
	});

	it('drops an earlier load of the same chat, which an id alone cannot tell apart', async () => {
		const waiting: ReturnType<typeof deferred<Response>>[] = [];
		vi.stubGlobal('fetch', () => {
			const waiter = deferred<Response>();
			waiting.push(waiter);
			return waiter.promise;
		});

		const session = new ChatSession();
		const first = session.open('a');
		const second = session.open('b');
		const third = session.open('a');

		// The *second* load of 'a' answers first; the first one is stale by the time it lands.
		waiting[2].resolve(new Response(JSON.stringify(chatDetail('a'))));
		waiting[1].resolve(new Response(JSON.stringify(chatDetail('b'))));
		waiting[0].resolve(new Response(JSON.stringify(chatDetail('a'))));

		expect(await third).toBe(true);
		expect(await second).toBe(false);
		expect(await first).toBe(false);
		expect(session.chat?.id).toBe('a');
	});

	it('reports a superseded load as not current, so the caller does not act on it', async () => {
		const waiting: ReturnType<typeof deferred<Response>>[] = [];
		vi.stubGlobal('fetch', () => {
			const waiter = deferred<Response>();
			waiting.push(waiter);
			return waiter.promise;
		});

		const session = new ChatSession();
		const first = session.open('a');
		const second = session.open('b');

		waiting[1].resolve(new Response(JSON.stringify(chatDetail('b'))));
		waiting[0].resolve(new Response(JSON.stringify(chatDetail('a'))));

		// The route sends a chat's first message only when this is `true` -- otherwise it would
		// go to whichever conversation overtook this one.
		expect(await first).toBe(false);
		expect(await second).toBe(true);
	});
});

describe('cancel', () => {
	afterEach(() => {
		vi.useRealTimers();
		vi.unstubAllGlobals();
	});

	/** A session mid-turn: the question is pending, a fragment has arrived, the stream is open. */
	function streaming(): ChatSession {
		const session = new ChatSession();
		session.chat = chatDetail('a').chat;
		session.pending = 'Talk for a long time';
		session.draft = [{ type: 'text_delta', text: 'word0 ' }];
		session.streaming = true;
		return session;
	}

	const interrupted = (): ChatDetail => ({
		...chatDetail('a'),
		messages: [
			message({ id: 'u', role: 'user', content: 'Talk for a long time', sequence: 1 }),
			message({
				id: 'h',
				sequence: 2,
				events: [
					{ type: 'text_delta', text: 'word0 ' },
					{
						type: 'turn_closed',
						reason: 'cancelled',
						usage: null,
						iterations: 1,
						error: ''
					} as AnyEvent
				]
			})
		]
	});

	it('hands the composer back and shows what the server kept', async () => {
		vi.useFakeTimers();
		vi.stubGlobal('fetch', async () => new Response(JSON.stringify(interrupted())));

		const session = streaming();
		const done = session.cancel();
		expect(session.cancelling).toBe(true);
		expect(session.streaming).toBe(false);

		await vi.runAllTimersAsync();
		await done;

		expect(session.busy).toBe(false);
		expect(session.cancelling).toBe(false);
		expect(session.draft).toEqual([]);
		expect(session.messages.at(-1)?.id).toBe('h');
	});

	it('reads again while the server has not written the stopped turn down yet', async () => {
		vi.useFakeTimers();
		let reads = 0;
		vi.stubGlobal('fetch', async () => {
			reads += 1;
			// The row as it was before the disconnect was seen: the empty answer, no outcome.
			const early: ChatDetail = {
				...chatDetail('a'),
				messages: [message({ id: 'h', sequence: 2, events: [] })]
			};
			return new Response(JSON.stringify(reads < 3 ? early : interrupted()));
		});

		const session = streaming();
		const done = session.cancel();
		await vi.runAllTimersAsync();
		await done;

		expect(reads).toBe(3);
		expect(session.messages.at(-1)?.events.length).toBe(2);
		expect(session.busy).toBe(false);
	});

	it('gives the composer back even when the server cannot be reached', async () => {
		vi.useFakeTimers();
		vi.stubGlobal('fetch', async () => {
			throw new Error('offline');
		});

		const session = streaming();
		const done = session.cancel();
		await vi.runAllTimersAsync();
		await done;

		expect(session.busy).toBe(false);
		expect(session.cancelling).toBe(false);
		expect(session.error).toBe('offline');
	});

	it('does nothing when no turn is running', async () => {
		const session = new ChatSession();
		session.chat = chatDetail('a').chat;
		await session.cancel();
		expect(session.cancelling).toBe(false);
	});
});
