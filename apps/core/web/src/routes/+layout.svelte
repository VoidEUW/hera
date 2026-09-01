<script lang="ts">
	/**
	 * The shell: the rail on the left, the route on the right, settings over the top.
	 *
	 * Everything the rail shows lives here rather than in each page, so navigating between
	 * chats does not re-fetch the sidebar — and so a new chat appears in the list the moment it
	 * is created rather than on the next load.
	 */
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import Rail from '$lib/components/Rail.svelte';
	import ProfileMenu from '$lib/components/ProfileMenu.svelte';
	import Settings from '$lib/components/Settings.svelte';
	import { workspace } from '$lib/stores/workspace.svelte';
	import { theme } from '$lib/theme.svelte';
	import '../app.css';

	let { children } = $props();
	let profileOpen = $state(false);

	// Called directly rather than from an $effect. `ssr = false`, so this only ever runs in the
	// browser -- and `theme.load()` both reads and writes the appearance, which inside an effect
	// is a dependency it also invalidates: Svelte answers that with effect_update_depth_exceeded
	// and stops rendering the page entirely.
	theme.load();
	void workspace.load();

	// Scoped to the chat route, not just `page.params.id`. `/project/<uuid>` fills the same
	// parameter name, and a rail that compared it against chat ids would go quiet the moment you
	// opened a project — nothing would match, so nothing would be marked as where you are.
	const activeId = $derived(page.route.id?.startsWith('/chat') ? (page.params.id ?? null) : null);
	const activeProjectId = $derived(
		page.route.id?.startsWith('/project') ? (page.params.id ?? null) : null
	);

	/** **New chat** goes to the start screen rather than making a chat.
	 *
	 * It used to create one and navigate into it, which meant every new conversation opened as
	 * an empty transcript with a "say something to start" line under it — the one screen in the
	 * application with nothing on it. The start screen is where beginning a conversation is
	 * already designed to happen: the mark, the greeting, the composer. It also means an
	 * abandoned "new chat" leaves no empty row in the rail, because nothing was created.
	 *
	 * A project's own **＋** carries the project through the store the same way the first
	 * message does — the start screen has no route parameter to put it in, and a query string
	 * would survive a refresh into a chat somebody has stopped meaning to create.
	 */
	async function newChat(projectId?: string) {
		workspace.pendingProject = projectId ?? null;
		await goto('/');
	}

	async function removeChat(id: string) {
		const removed = await workspace.deleteChat(id);
		// Only when the conversation on screen is the one that just went. Deleting another
		// chat from the rail must not take you away from what you were reading.
		if (removed && page.params.id === id) await goto('/');
	}

	/** A new project opens its own screen. A project is instructions and pinned skills; one with
	 * neither is a name, and the screen is where it becomes a project. */
	async function newProject(name: string) {
		const project = await workspace.createProject(name);
		if (project) await goto(`/project/${project.id}`);
	}

	async function removeProject(id: string) {
		const removed = await workspace.deleteProject(id);
		// Same rule as a chat: only navigate away if you were looking at the thing that went.
		if (removed && page.url.pathname === `/project/${id}`) await goto('/');
	}

	/** The composer shows what she can reach, and settings is where that changes. */
	async function closeSettings() {
		workspace.settingsOpen = false;
		await Promise.all([workspace.loadProviders(), workspace.loadServers()]);
	}

	function onkeydown(event: KeyboardEvent) {
		// ⌘K opens settings for now; search lands with the command palette.
		if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
			event.preventDefault();
			workspace.openSettings();
		}
	}
</script>

<svelte:window {onkeydown} />

<div class="shell">
	<Rail
		chats={workspace.chats}
		projects={workspace.projects}
		profile={workspace.activeProfile}
		{activeId}
		{activeProjectId}
		onnew={newChat}
		onsettings={() => workspace.openSettings()}
		onprofile={() => (profileOpen = true)}
		onrename={(id, title) => workspace.renameChat(id, title)}
		ondelete={removeChat}
		onmove={(id, projectId) => workspace.moveChat(id, projectId)}
		onnewproject={newProject}
		onprojectrename={(id, name) => workspace.patchProject(id, { name })}
		onprojectdelete={removeProject}
	/>

	<main>
		{@render children()}
	</main>
</div>

{#if workspace.settingsOpen}
	<Settings onclose={closeSettings} />
{/if}

{#if profileOpen}
	<ProfileMenu
		profiles={workspace.profiles}
		onclose={() => (profileOpen = false)}
		onprofiles={(found) => (workspace.profiles = found)}
	/>
{/if}

<style>
	.shell {
		display: flex;
		height: 100vh;
		height: 100dvh;
		overflow: hidden;
	}

	main {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	@media (max-width: 780px) {
		/* On a phone the rail becomes a sheet. Nothing is removed; for now it simply steps
		   aside, and the sheet lands with the mobile pass. */
		.shell {
			flex-direction: column;
		}
	}
</style>
