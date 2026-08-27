/**
 * The sidebar's world: chats, projects and profiles.
 *
 * One instance for the whole application, held by the layout, so navigating between chats does
 * not re-fetch the rail and a chat created in one place appears in the list everywhere.
 */

import { api, type Chat, type Profile, type Project } from '$lib/api/client';
import type { Attachment } from '$lib/attachments';

class Workspace {
	chats = $state<Chat[]>([]);
	projects = $state<Project[]>([]);
	profiles = $state<Profile[]>([]);
	error = $state<string | null>(null);
	loaded = $state(false);

	get activeProfile(): Profile | null {
		return this.profiles.find((profile) => profile.is_default) ?? this.profiles[0] ?? null;
	}

	async load() {
		try {
			const [chats, projects, profiles] = await Promise.all([
				api.chats(),
				api.projects(),
				api.profiles()
			]);
			this.chats = chats;
			this.projects = projects;
			this.profiles = profiles;
			this.error = null;
		} catch (cause) {
			this.error = cause instanceof Error ? cause.message : String(cause);
		} finally {
			this.loaded = true;
		}
	}

	async createChat(projectId?: string): Promise<Chat | null> {
		try {
			const chat = await api.createChat(projectId ? { project_id: projectId } : {});
			this.chats = [chat, ...this.chats];
			return chat;
		} catch (cause) {
			this.error = cause instanceof Error ? cause.message : String(cause);
			return null;
		}
	}

	/** Fold a chat's new title and activity back into the rail without a round trip. */
	touch(updated: Chat) {
		const rest = this.chats.filter((chat) => chat.id !== updated.id);
		this.chats = [updated, ...rest];
	}

	/** A message typed on the start screen, waiting for the chat route to pick it up.
	 *
	 * Held here rather than in history state: `goto`'s `state` option does not reliably reach
	 * `page.state`, and a first message quietly lost to a navigation is the worst possible
	 * first impression. A field is also honest about the lifetime -- it is read once and
	 * cleared, and a refresh must not send it again. */
	#handoff: { text: string; files: Attachment[] } | null = null;

	handOff(text: string, files: Attachment[] = []) {
		this.#handoff = { text, files };
	}

	takeHandoff(): { text: string; files: Attachment[] } | null {
		const carried = this.#handoff;
		this.#handoff = null;
		return carried;
	}
}

export const workspace = new Workspace();
