/**
 * One open conversation, and the turn currently streaming into it.
 *
 * The single place the "server render is authoritative" rule is enforced. While a turn is
 * running, events are appended to a **draft** list and rendered optimistically. When the `done`
 * frame arrives it carries the persisted message, and the draft is thrown away and replaced by
 * it wholesale — not merged, not reconciled. Merging would be a second implementation of what
 * the server already decided, and the two would drift.
 */

import {
	api,
	answerPermission,
	redoMessage,
	sendMessage,
	type Chat,
	type Message
} from '$lib/api/client';
import type { Attachment } from '$lib/attachments';
import type { AnyEvent } from '$lib/api/events';
import { frames } from '$lib/api/sse';
import { reduce, type Turn } from '$lib/turn';

export class ChatSession {
	chat = $state<Chat | null>(null);
	messages = $state<Message[]>([]);

	/** Events of the turn in flight. Empty when nothing is streaming. */
	draft = $state<AnyEvent[]>([]);
	streaming = $state(false);
	error = $state<string | null>(null);

	/** What the person just typed, shown immediately so the interface never looks asleep. */
	pending = $state<string | null>(null);
	pendingFiles = $state<Attachment[]>([]);

	#abort: AbortController | null = null;

	get turn(): Turn {
		return reduce(this.draft);
	}

	/** Calls waiting on a person — in the live turn, or in the last message after a reload. */
	get awaiting() {
		if (this.draft.length) return this.turn.awaiting;
		const last = this.messages.at(-1);
		return last?.role === 'assistant' ? reduce(last.events).awaiting : [];
	}

	get busy() {
		return this.streaming || this.pending !== null;
	}

	async open(id: string) {
		this.reset();
		try {
			const detail = await api.chat(id);
			this.chat = detail.chat;
			this.messages = detail.messages;
		} catch (cause) {
			this.error = message(cause);
		}
	}

	reset() {
		this.stop();
		this.chat = null;
		this.messages = [];
		this.draft = [];
		this.error = null;
		this.pending = null;
		this.pendingFiles = [];
	}

	/** Abort the stream. The server sees the disconnect and closes the turn as `cancelled`,
	 * keeping the text that arrived — so stopping is not the same as losing. */
	stop() {
		this.#abort?.abort();
		this.#abort = null;
		this.streaming = false;
	}

	async send(text: string, attachments: Attachment[] = []) {
		if (!this.chat || this.busy) return;
		this.pending = text;
		this.pendingFiles = attachments;
		await this.#consume(() => sendMessage(this.chat!.id, text, attachments, this.#begin()));
	}

	/** Switch skills on for this conversation. Optimistic: the picker is a set of toggles and
	 * a tick that waits for a round trip reads as a click that did not land. */
	async pinSkills(names: string[]) {
		if (!this.chat) return;
		const previous = this.chat.pinned_skills;
		this.chat = { ...this.chat, pinned_skills: names };
		try {
			this.chat = await api.pinSkills(this.chat.id, names);
		} catch (cause) {
			if (this.chat) this.chat = { ...this.chat, pinned_skills: previous };
			this.error = cause instanceof Error ? cause.message : String(cause);
		}
	}

	/** Ask again from this message. `text` given rewords the question — the interface calls
	 * that **edit**; left out it repeats it, which is **try again**. Pointed at an answer, the
	 * server replays the question above it.
	 *
	 * The messages from that question onwards are dropped here as well as on the server, so
	 * the screen is not still showing an answer to a question that no longer exists while the
	 * new one streams in. `#settle` refreshes from the server at `done` either way. */
	async redo(messageId: string, text?: string) {
		if (!this.chat || this.busy) return;
		const target = this.messages.find((message) => message.id === messageId);
		if (!target) return;
		const asked =
			target.role === 'user'
				? target
				: [...this.messages]
						.reverse()
						.find((message) => message.role === 'user' && message.sequence < target.sequence);
		if (!asked) return;

		this.messages = this.messages.filter((message) => message.sequence < asked.sequence);
		this.pending = text ?? asked.content;
		// The files travel with the question server-side; the chips come back with the refresh
		// at `done`. Redrawing them here would mean holding contents the browser threw away.
		this.pendingFiles = [];
		await this.#consume(() => redoMessage(this.chat!.id, messageId, text, this.#begin()));
	}

	async answer(callIds: string[], allow: boolean, remember = false) {
		if (!this.chat || this.streaming) return;
		await this.#consume(() =>
			answerPermission(this.chat!.id, { call_ids: callIds, allow, remember }, this.#begin())
		);
	}

	#begin(): AbortSignal {
		this.#abort?.abort();
		this.#abort = new AbortController();
		this.error = null;
		return this.#abort.signal;
	}

	async #consume(start: () => Promise<Response>) {
		this.streaming = true;
		// A resumed turn continues an assistant message that is already on screen; take it out
		// of `messages` so the draft is the only thing rendering it and it does not appear
		// twice while the second half streams in.
		const resuming = this.awaiting.length > 0;
		const carried = resuming ? this.messages.at(-1) : undefined;
		if (carried) {
			this.messages = this.messages.slice(0, -1);
			this.draft = [...carried.events];
		}

		try {
			const response = await start();
			if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);

			for await (const frame of frames(response)) {
				if (frame.name === 'done') {
					// The whole point. Everything drawn optimistically is discarded and the
					// persisted message takes its place, so a reload cannot show something
					// different from what was just watched.
					this.#settle(frame.data as Message);
					continue;
				}
				this.draft = [...this.draft, frame.data as AnyEvent];
			}
		} catch (cause) {
			if (!isAbort(cause)) this.error = message(cause);
		} finally {
			this.streaming = false;
			this.#abort = null;
			// A stream that ended without a `done` frame -- a dropped connection -- leaves the
			// draft on screen rather than blanking the answer. Reloading will show whatever the
			// server managed to persist.
			if (this.draft.length === 0) this.pending = null;
		}
	}

	#settle(persisted: Message) {
		this.pending = null;
		this.pendingFiles = [];
		this.draft = [];
		const rest = this.messages.filter((existing) => existing.id !== persisted.id);
		this.messages = [...rest, persisted].sort((a, b) => a.sequence - b.sequence);
		// The user message was written server-side in the same request, so it may not be in the
		// list yet. Refreshing is cheaper than guessing what it looked like.
		void this.#refresh();
	}

	async #refresh() {
		if (!this.chat) return;
		try {
			const detail = await api.chat(this.chat.id);
			this.chat = detail.chat;
			this.messages = detail.messages;
		} catch {
			/* the draft already showed the answer; a failed refresh is not worth an error */
		}
	}
}

function isAbort(cause: unknown): boolean {
	return cause instanceof DOMException && cause.name === 'AbortError';
}

function message(cause: unknown): string {
	return cause instanceof Error ? cause.message : String(cause);
}
