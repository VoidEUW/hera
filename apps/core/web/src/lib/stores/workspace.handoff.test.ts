/**
 * The start-screen handoff, and the one thing it must never do.
 *
 * `handOff` carries the first sentence of a conversation from the start screen to the chat
 * route, which cannot take it as a parameter because the message is not a URL
 * (`+page.svelte`). The store holds it in the interval.
 *
 * That interval has a failure in it. Loading the chat can fail *after* the handoff is set --
 * `create_chat` and the `GET` that follows it race the server's own commit, and about one time
 * in eight the chat is not readable yet ([#136](https://github.com/VoidEUW/hera/issues/136)).
 * A load that fails must not consume the message, so the field outlives the failure. But a
 * field that outlives a failure and does not say *whose* message it is will hand a person's
 * sentence to whichever conversation is opened next.
 *
 * So these are about one invariant: **a handoff is delivered to the chat it was written for, or
 * to none of them.**
 *
 * `@vitest-environment jsdom` because the store is a Svelte 5 class holding `$state`, which
 * needs a rune-aware runtime rather than a DOM -- the same arrangement `chat.test.ts` uses.
 */

import { beforeEach, describe, expect, it } from 'vitest';

import { Workspace } from './workspace.svelte';

describe('the start-screen handoff', () => {
	let workspace: Workspace;

	beforeEach(() => {
		workspace = new Workspace();
	});

	it('is delivered to the chat it was typed for', () => {
		workspace.handOff('chat-1', 'what is kerberos', []);

		const taken = workspace.takeHandoff('chat-1');

		expect(taken?.text).toBe('what is kerberos');
	});

	it('is read once, so a refresh cannot send it again', () => {
		workspace.handOff('chat-1', 'what is kerberos', []);

		expect(workspace.takeHandoff('chat-1')).not.toBeNull();
		expect(workspace.takeHandoff('chat-1')).toBeNull();
	});

	it('is not delivered to a different chat', () => {
		// The case that matters. A load of chat-1 failed, its sentence is still here, and the
		// person opens chat-2 instead. Taking it would answer an unrelated question with a
		// question they had not asked there.
		workspace.handOff('chat-1', 'what is kerberos', []);

		expect(workspace.takeHandoff('chat-2')).toBeNull();
	});

	it('stays available to its own chat after another chat declines it', () => {
		// Refusing is not discarding. The chat that could not be read did exist, so walking
		// back to it is the correct recovery, and the sentence has to still be there.
		workspace.handOff('chat-1', 'what is kerberos', []);

		expect(workspace.takeHandoff('chat-2')).toBeNull();
		expect(workspace.takeHandoff('chat-1')?.text).toBe('what is kerberos');
	});

	it('is discarded for a chat that cannot be opened, and only for that one', () => {
		workspace.handOff('chat-1', 'gone', []);
		workspace.handOff('chat-2', 'kept', []);

		workspace.discardHandoff('chat-1');

		expect(workspace.takeHandoff('chat-1')).toBeNull();
		// The failure was chat-1's alone, and must not take chat-2's pending message with it.
		expect(workspace.takeHandoff('chat-2')?.text).toBe('kept');
	});

	it('discards nothing when the chat has no message waiting', () => {
		workspace.handOff('chat-2', 'kept', []);

		workspace.discardHandoff('chat-1');

		expect(workspace.takeHandoff('chat-2')?.text).toBe('kept');
	});

	it('carries its attachments with it', () => {
		const file = { name: 'notes.md', text: 'the body', bytes: 12 };
		workspace.handOff('chat-1', 'read this', [file]);

		expect(workspace.takeHandoff('chat-1')?.files).toEqual([file]);
	});
});
