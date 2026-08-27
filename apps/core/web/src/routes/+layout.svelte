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
	import Settings from '$lib/components/Settings.svelte';
	import { workspace } from '$lib/stores/workspace.svelte';
	import { theme } from '$lib/theme.svelte';
	import '../app.css';

	let { children } = $props();
	let settingsOpen = $state(false);

	// Called directly rather than from an $effect. `ssr = false`, so this only ever runs in the
	// browser -- and `theme.load()` both reads and writes the appearance, which inside an effect
	// is a dependency it also invalidates: Svelte answers that with effect_update_depth_exceeded
	// and stops rendering the page entirely.
	theme.load();
	void workspace.load();

	const activeId = $derived(page.params.id ?? null);

	async function newChat(projectId?: string) {
		const chat = await workspace.createChat(projectId);
		if (chat) await goto(`/chat/${chat.id}`);
	}

	function onkeydown(event: KeyboardEvent) {
		// ⌘K opens settings for now; search lands with the command palette.
		if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
			event.preventDefault();
			settingsOpen = true;
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
		onnew={newChat}
		onsettings={() => (settingsOpen = true)}
	/>

	<main>
		{@render children()}
	</main>
</div>

{#if settingsOpen}
	<Settings onclose={() => (settingsOpen = false)} />
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
