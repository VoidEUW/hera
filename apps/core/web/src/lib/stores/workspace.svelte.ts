/**
 * The sidebar's world: chats, projects and profiles.
 *
 * One instance for the whole application, held by the layout, so navigating between chats does
 * not re-fetch the rail and a chat created in one place appears in the list everywhere.
 */

import {
	api,
	type Chat,
	type Profile,
	type Project,
	type ProjectPatch,
	type Provider,
	type Server
} from '$lib/api/client';
import type { Attachment } from '$lib/attachments';

class Workspace {
	chats = $state<Chat[]>([]);
	projects = $state<Project[]>([]);
	profiles = $state<Profile[]>([]);
	/** The endpoints she can answer from, and which one she is on. The composer shows the
	 * active model and switches it; there is one active endpoint for the whole application,
	 * because that is what `config.toml` holds. */
	providers = $state<Provider[]>([]);
	activeProvider = $state('');
	/** Connected MCP servers, so the composer can say what she can reach without asking again
	 * on every keystroke. Refreshed when settings closes, since that is where it changes. */
	servers = $state<Server[]>([]);
	/** What version of her is running, as the server reports it.
	 *
	 * Here rather than fetched by whoever wants to draw it, so a second place that shows the
	 * version costs a `workspace.version` and not another request. It comes from
	 * `hera_core.__version__`, which reads the installed distribution — one number, from
	 * packaging, which `release.yml` refuses to let a tag disagree with.
	 *
	 * Empty until the first load answers, and empty is what a component should render as
	 * nothing: a version is not worth a spinner, and `Hera v…` flickering into `Hera v0.1.0`
	 * is worse than it arriving. */
	version = $state('');
	error = $state<string | null>(null);
	loaded = $state(false);

	/** Whether the settings modal is open. Here rather than in the layout because three places
	 * open it — the rail, ⌘K, and the composer's model and context chips — and the two of them
	 * that are not the layout would otherwise need a callback threaded through every route. */
	settingsOpen = $state(false);

	/** Skills switched on from the start screen, where there is no chat to pin them to yet.
	 *
	 * The picker is offered there because deciding *use this one* before you have typed the
	 * question is the ordinary case — you know what you are about to ask. They are applied to
	 * the chat the moment it is created and cleared, because a pin is a fact about one
	 * conversation and carrying it silently into every future one is not what a toggle means. */
	pendingSkills = $state<string[]>([]);

	/** The project a chat started from the start screen belongs to, or `null` for a loose one.
	 *
	 * Set by a project's **＋** in the rail and read once when the chat is created. Held here
	 * rather than in the URL for the same reason the first message is: a refresh must not
	 * re-enact a decision somebody has walked away from. */
	pendingProject = $state<string | null>(null);

	openSettings() {
		this.settingsOpen = true;
	}

	get activeProfile(): Profile | null {
		return this.profiles.find((profile) => profile.is_default) ?? this.profiles[0] ?? null;
	}

	/** The endpoint she is pointed at, or null when none is registered yet. */
	get model(): Provider | null {
		return this.providers.find((entry) => entry.name === this.activeProvider) ?? null;
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
		// Deliberately after, and deliberately not fatal. Neither of these is needed to hold a
		// conversation: with no endpoint the composer says so, and with no servers it shows
		// nothing. An error here must not be what stops the rail from rendering.
		await Promise.all([this.loadProviders(), this.loadServers(), this.loadVersion()]);
	}

	async loadVersion() {
		try {
			this.version = (await api.health()).version;
		} catch {
			/* the About panel is where a server that will not answer gets explained */
		}
	}

	async loadProviders() {
		try {
			const found = await api.providers();
			this.providers = found.providers;
			this.activeProvider = found.active;
		} catch {
			/* the Models screen is where this gets explained */
		}
	}

	async loadServers() {
		try {
			this.servers = await api.servers();
		} catch {
			/* the Servers screen is where this gets explained */
		}
	}

	/** Point her at another registered endpoint. Takes effect on the next turn, no restart. */
	async useProvider(name: string) {
		if (name === this.activeProvider) return;
		try {
			const found = await api.activateProvider(name);
			this.providers = found.providers;
			this.activeProvider = found.active;
		} catch (cause) {
			this.error = cause instanceof Error ? cause.message : String(cause);
		}
	}

	async createChat(projectId?: string): Promise<Chat | null> {
		const project = projectId ?? this.pendingProject;
		try {
			let chat = await api.createChat(project ? { project_id: project } : {});
			this.pendingProject = null;
			// Skills chosen on the start screen land on the chat before the first message is
			// sent, so the turn they were chosen for is the turn that gets them. A failure here
			// is not worth losing the chat over -- the picker is still one click away inside it.
			if (this.pendingSkills.length) {
				try {
					chat = await api.pinSkills(chat.id, this.pendingSkills);
				} catch {
					/* the composer's picker says what is actually pinned */
				}
				this.pendingSkills = [];
			}
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

	/** Rename a chat. A name typed by hand sticks — she only ever names an unnamed chat. */
	async renameChat(id: string, title: string): Promise<boolean> {
		const previous = this.chats;
		// Optimistic, because the rail is the thing being looked at while this happens. The
		// list is put back if the server disagrees.
		this.chats = this.chats.map((chat) => (chat.id === id ? { ...chat, title } : chat));
		try {
			const updated = await api.renameChat(id, title);
			this.chats = this.chats.map((chat) => (chat.id === id ? updated : chat));
			return true;
		} catch (cause) {
			this.chats = previous;
			this.error = cause instanceof Error ? cause.message : String(cause);
			return false;
		}
	}

	async deleteChat(id: string): Promise<boolean> {
		try {
			await api.deleteChat(id);
			this.chats = this.chats.filter((chat) => chat.id !== id);
			return true;
		} catch (cause) {
			this.error = cause instanceof Error ? cause.message : String(cause);
			return false;
		}
	}

	/** Move a chat into a project, or out of every project with `null`.
	 *
	 * Optimistic like renaming, and for the same reason: the rail is what is being looked at
	 * while it happens, and a row that jumps a beat after the click reads as a glitch rather
	 * than as an answer. */
	async moveChat(id: string, projectId: string | null): Promise<boolean> {
		const previous = this.chats;
		this.chats = this.chats.map((chat) =>
			chat.id === id ? { ...chat, project_id: projectId } : chat
		);
		try {
			const updated = await api.moveChat(id, projectId);
			this.chats = this.chats.map((chat) => (chat.id === id ? updated : chat));
			return true;
		} catch (cause) {
			this.chats = previous;
			this.error = cause instanceof Error ? cause.message : String(cause);
			return false;
		}
	}

	/** Make a project. Returns it so the caller can navigate into it, which is what the rail's
	 * ＋ does — a project with no instructions is not yet a project, and the screen is where
	 * they get written. */
	async createProject(name: string): Promise<Project | null> {
		try {
			const project = await api.createProject(name);
			this.projects = [...this.projects, project];
			return project;
		} catch (cause) {
			this.error = cause instanceof Error ? cause.message : String(cause);
			return null;
		}
	}

	/** Patch one or more fields of a project and fold the answer back into the rail.
	 *
	 * Not optimistic: unlike a rename, most of what this changes — instructions, pins, the
	 * default profile — is not what the rail is drawing, so there is nothing to keep in step
	 * and a rollback would be invisible anyway. */
	async patchProject(id: string, patch: ProjectPatch): Promise<Project | null> {
		try {
			const updated = await api.updateProject(id, patch);
			this.projects = this.projects.map((project) => (project.id === id ? updated : project));
			return updated;
		} catch (cause) {
			this.error = cause instanceof Error ? cause.message : String(cause);
			return null;
		}
	}

	/** Revoke a project. Its chats keep their `project_id` on the server and come back as loose
	 * ones here, which is what the API means by revoke rather than delete — nothing a person
	 * said is thrown away because the container around it was. */
	async deleteProject(id: string): Promise<boolean> {
		try {
			await api.deleteProject(id);
			this.projects = this.projects.filter((project) => project.id !== id);
			this.chats = this.chats.map((chat) =>
				chat.project_id === id ? { ...chat, project_id: null } : chat
			);
			return true;
		} catch (cause) {
			this.error = cause instanceof Error ? cause.message : String(cause);
			return false;
		}
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
