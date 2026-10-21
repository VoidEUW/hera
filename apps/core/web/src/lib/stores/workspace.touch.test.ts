/**
 * Opening a chat must not reorder the rail (#112).
 *
 * ⌥↑ and ⌥↓ walk the chats in the order the rail lists them. If opening one moved it to the top,
 * the next step would be relative to a list that had just rearranged itself, and the walk would
 * bounce between the top two forever. Only *activity* — something said — moves a chat up.
 *
 * `@vitest-environment jsdom` for the same reason the other store tests are: a Svelte 5 class
 * holding `$state` needs a rune-aware runtime.
 */

import { beforeEach, describe, expect, it } from 'vitest';

import type { Chat } from '$lib/api/client';
import { Workspace } from './workspace.svelte';

function chat(id: string, at: string | null): Chat {
	return {
		id,
		title: id,
		project_id: null,
		profile_id: null,
		pinned: false,
		pinned_skills: [],
		created_at: '2026-01-01T00:00:00Z',
		last_message_at: at
	};
}

describe('touching a chat', () => {
	let workspace: Workspace;

	beforeEach(() => {
		workspace = new Workspace();
		workspace.chats = [chat('a', '2026-01-03T00:00:00Z'), chat('b', '2026-01-02T00:00:00Z')];
	});

	it('leaves the order alone when nothing was said', () => {
		workspace.touch(chat('b', '2026-01-02T00:00:00Z'));
		expect(workspace.chats.map((entry) => entry.id)).toEqual(['a', 'b']);
	});

	it('takes the fresh copy of the chat in place', () => {
		workspace.touch({ ...chat('b', '2026-01-02T00:00:00Z'), title: 'Renamed' });
		expect(workspace.chats[1]?.title).toBe('Renamed');
	});

	it('moves a chat to the top when something was said in it', () => {
		workspace.touch(chat('b', '2026-01-04T00:00:00Z'));
		expect(workspace.chats.map((entry) => entry.id)).toEqual(['b', 'a']);
	});

	it('puts a chat the rail had not seen on top', () => {
		workspace.touch(chat('c', null));
		expect(workspace.chats.map((entry) => entry.id)).toEqual(['c', 'a', 'b']);
	});
});
