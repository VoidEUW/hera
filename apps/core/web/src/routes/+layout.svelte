<script lang="ts">
	/**
	 * The shell: the rail on the left, the route on the right, settings over the top.
	 *
	 * Everything the rail shows lives here rather than in each page, so navigating between
	 * chats does not re-fetch the sidebar — and so a new chat appears in the list the moment it
	 * is created rather than on the next load.
	 */
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import Scrim from '$lib/components/ui/Scrim.svelte';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import Offline from '$lib/components/Offline.svelte';
	import ChatSidebar from '$lib/components/ChatSidebar.svelte';
	import CommandPalette from '$lib/components/CommandPalette.svelte';
	import Settings from '$lib/components/Settings.svelte';
	import Toaster from '$lib/components/ui/Toaster.svelte';
	import { api, whenSignedOut } from '$lib/api/client';
	import { dialog } from '$lib/dialog';
	import { SIGNED_OUT_ROUTES, toSignIn } from '$lib/errors';
	import { t } from '$lib/i18n';
	import { keys } from '$lib/keys';
	import { sidebar } from '$lib/stores/sidebar.svelte';
	import { notifications } from '$lib/notifications.svelte';
	import { workspace } from '$lib/stores/workspace.svelte';
	import { theme } from '$lib/theme.svelte';
	import '../app.css';

	let { children } = $props();

	// Called directly rather than from an $effect. `ssr = false`, so this only ever runs in the
	// browser -- and `theme.load()` both reads and writes the appearance, which inside an effect
	// is a dependency it also invalidates: Svelte answers that with effect_update_depth_exceeded
	// and stops rendering the page entirely.
	theme.load();
	sidebar.load();
	notifications.load();

	/** The sign-in screen and the setup wizard are drawn on their own, with no rail: there is
	 * nothing in a rail for somebody who is not signed in. */
	const bare = $derived((SIGNED_OUT_ROUTES as readonly string[]).includes(page.route.id ?? ''));

	/** Whether the shell may draw: only once the server has said who is signed in. Drawing it
	 * first and taking it away a moment later is a flash of somebody's chats. */
	let admitted = $state(false);

	whenSignedOut(toSignIn);
	void (async () => {
		try {
			const state = await api.authState();
			if (state.setup_required) {
				if (page.route.id !== '/setup') await goto(resolve('/setup'));
				return;
			}
			if (!state.user) {
				toSignIn();
				return;
			}
		} catch {
			// The workspace's own load is what draws the offline screen or the error, so it runs
			// and says which.
		}
		admitted = true;
		if (!bare) await workspace.load();
	})();

	// Scoped to the chat route, not just `page.params.id`. `/project/<uuid>` fills the same
	// parameter name, and a rail that compared it against chat ids would go quiet the moment you
	// opened a project — nothing would match, so nothing would be marked as where you are.
	const activeId = $derived(page.route.id?.startsWith('/chat') ? (page.params.id ?? null) : null);
	const activeProjectId = $derived(
		page.route.id?.startsWith('/project') ? (page.params.id ?? null) : null
	);

	// Below the phone breakpoint the rail is a sheet you open, pick something in, and leave —
	// closing it here rather than wherever `onnew`/rename/etc. fire means every way of leaving
	// the rail (a chat, a project, the start screen) closes it the same way, once.
	$effect(() => {
		void page.url.pathname;
		workspace.railOpen = false;
	});

	// On a phone the shell is the part of the screen the browser is actually showing (#41). iOS
	// Safari does not shrink the page for the keyboard: it slides the whole page up under it, so
	// the top bar went off the top and the conversation scrolled as one sheet with the bar and
	// the composer. Following `visualViewport` keeps the bar at the top and the composer on the
	// keyboard, with only the transcript scrolling between them. The CSS that reads these is
	// below the breakpoint only, so the desktop is untouched; a pinch-zoomed view is left alone,
	// because then the visible part is meant to be smaller than the page.
	$effect(() => {
		const view = window.visualViewport;
		if (!view) return;
		const root = document.documentElement;
		const follow = () => {
			if (view.scale > 1.01) return;
			root.style.setProperty('--view-height', `${view.height}px`);
			root.style.setProperty('--view-top', `${view.offsetTop}px`);
		};
		follow();
		view.addEventListener('resize', follow);
		view.addEventListener('scroll', follow);
		return () => {
			view.removeEventListener('resize', follow);
			view.removeEventListener('scroll', follow);
			root.style.removeProperty('--view-height');
			root.style.removeProperty('--view-top');
		};
	});

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
		await goto(resolve('/'));
	}

	async function removeChat(id: string) {
		const removed = await workspace.deleteChat(id);
		// Only when the conversation on screen is the one that just went. Deleting another
		// chat from the rail must not take you away from what you were reading.
		if (removed && page.params.id === id) await goto(resolve('/'));
	}

	/** A new project opens its own screen. A project is instructions and pinned skills; one with
	 * neither is a name, and the screen is where it becomes a project. */
	async function newProject(name: string) {
		const project = await workspace.createProject(name);
		if (project) await goto(resolve('/project/[id]', { id: project.id }));
	}

	async function removeProject(id: string) {
		const removed = await workspace.deleteProject(id);
		// Same rule as a chat: only navigate away if you were looking at the thing that went.
		if (removed && page.url.pathname === `/project/${id}`) await goto(resolve('/'));
	}

	/** Signed out, and reloaded at the sign-in screen so nothing of this person stays in memory. */
	async function signOut() {
		try {
			await api.signOut();
		} finally {
			window.location.assign(resolve('/login'));
		}
	}

	/** The composer shows what she can reach, and settings is where that changes. */
	async function closeSettings() {
		workspace.settingsOpen = false;
		await Promise.all([workspace.loadProviders(), workspace.loadServers()]);
	}

	const shown = $derived(admitted && !bare);

	/** The command palette, and which question it was opened with. */
	let palette = $state<'all' | 'chats' | null>(null);

	/** Walk the chats in the order the rail lists them: ⌥↑ is the one above, ⌥↓ the one below. A
	 * chord with nowhere to go declines, so the browser keeps it. */
	function step(by: 1 | -1): boolean {
		const list = workspace.chats;
		const here = list.findIndex((chat) => chat.id === activeId);
		const next = list[here === -1 ? (by === 1 ? 0 : list.length - 1) : here + by];
		if (!next) return false;
		void goto(resolve('/chat/[id]', { id: next.id }));
		return true;
	}

	// The chords that exist on every screen (#112). Screens add their own while they are mounted.
	$effect(() => {
		const off = [
			keys.on('palette', () => {
				if (workspace.unreachable || !shown) return false;
				palette = palette ? null : 'all';
			}),
			keys.on('palette.chats', () => {
				if (workspace.unreachable || !shown) return false;
				palette = 'chats';
			}),
			keys.on('settings', () => {
				if (workspace.unreachable || !shown) return false;
				palette = null;
				workspace.openSettings();
			}),
			keys.on('hotkeys', () => {
				if (workspace.unreachable || !shown) return false;
				palette = null;
				workspace.openSettings('hotkeys');
			}),
			keys.on('newChat', () => {
				if (workspace.unreachable || !shown) return false;
				palette = null;
				void newChat();
			}),
			keys.on('chat.previous', () => shown && step(-1)),
			keys.on('chat.next', () => shown && step(1))
		];
		return () => off.forEach((undo) => undo());
	});
</script>

<svelte:window onkeydown={(event) => keys.dispatch(event)} />

{#if bare}
	{@render children()}
{:else if workspace.unreachable}
	<!-- Instead of the shell, not over it. Nothing below works without that first answer: no
	     rail, no profile, no endpoint, no conversation — and drawing the chrome anyway is an
	     invitation to click seven things that cannot work. -->
	<Offline />
{:else if admitted}
	<div class="shell">
		<!-- Below the phone breakpoint the rail below is off-canvas by default; this is the one
	     control that brings it on screen, placed once here rather than in every route's own
	     header because it has to reach the start screen (no header at all), the chat screen and
	     the project screen alike. -->
		<div class="menu">
			<IconButton
				icon="menu"
				label={t.rail.openMenu}
				bordered
				onclick={() => (workspace.railOpen = true)}
			/>
		</div>

		{#if workspace.railOpen}
			<!-- The same scrim every dialog uses, so a sheet reads as one idea across the
			     application. -->
			<Scrim onclick={() => (workspace.railOpen = false)} />
		{/if}

		<!-- On a phone the sidebar opens as a sheet, and then it *is* a dialog: focus moves in, Tab
		     stays in, Escape closes it and focus goes back to the menu button (#121) — the same
		     `dialog` action every Modal uses, switched on only while the sheet is open. -->
		<div
			class="rail-slot"
			class:sheet={workspace.railOpen}
			role={workspace.railOpen ? 'dialog' : undefined}
			aria-modal={workspace.railOpen ? 'true' : undefined}
			aria-label={workspace.railOpen ? t.rail.title : undefined}
			use:dialog={{ active: workspace.railOpen, onclose: () => (workspace.railOpen = false) }}
		>
			<ChatSidebar
				sheet={workspace.railOpen}
				chats={workspace.chats}
				projects={workspace.projects}
				account={workspace.account}
				loading={!workspace.loaded}
				shape={workspace.shape}
				{activeId}
				{activeProjectId}
				onnew={newChat}
				onsettings={() => workspace.openSettings()}
				onsignout={signOut}
				onsearch={() => {
					// The sheet steps aside for the palette, as it does for Settings (#41).
					workspace.railOpen = false;
					palette = 'all';
				}}
				settingsOpen={workspace.settingsOpen}
				onrename={(id, title) => workspace.renameChat(id, title)}
				ondelete={removeChat}
				onmove={(id, projectId) => workspace.moveChat(id, projectId)}
				onnewproject={newProject}
				onprojectrename={(id, name) => workspace.patchProject(id, { name })}
				onprojectdelete={removeProject}
			/>
		</div>

		<main>
			{@render children()}
		</main>
	</div>

	<!-- Inside the reachable branch, not beside it. ⌘K can open settings while the first request
	     is still in flight; if that request then fails, a sheet left mounted out here would sit
	     over the screen explaining that nothing is answering — and every control in it needs the
	     server that is not. -->
	{#if workspace.settingsOpen}
		<Settings
			onclose={closeSettings}
			tab={workspace.settingsTab}
			ontab={(next) => (workspace.settingsTab = next)}
		/>
	{/if}

	{#if palette}
		<CommandPalette
			scope={palette}
			onnewchat={() => void newChat()}
			onclose={() => (palette = null)}
		/>
	{/if}
{/if}

<!-- Outside the reachable branch, so a confirmation can still say something on the offline
     screen. -->
<Toaster />

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

	.menu {
		display: none;
	}

	@keyframes fade {
		from {
			opacity: 0;
		}
	}

	/* The sidebar floats inside this slot; the slot only gives it the full height. */
	.rail-slot {
		display: flex;
	}

	@media (max-width: 780px) {
		/* Pinned to what the browser is showing (see the `visualViewport` effect above), so the page
		   itself never scrolls — only the transcript inside it does. */
		.shell {
			position: fixed;
			inset: var(--view-top, 0px) 0 auto 0;
			height: var(--view-height, 100dvh);
		}

		/* A screen with a top bar carries its own menu button in it (`Topbar`'s `onmenu`); this
		   floating one is for the screens without a bar — the start screen and a project. */
		.shell:has(:global(.topbar .lead)) .menu {
			display: none;
		}

		/* Off-canvas by default and brought on screen by `.menu` — nothing slides in from
		   off-screen (the interface's one rule about motion), so this is the same plain
		   `animation: fade` Settings already draws its own sheet with, not a translate. */
		.rail-slot {
			display: none;
		}

		.rail-slot.sheet {
			/* No explicit width: the rail keeps its own `var(--rail)`, and a fixed box with only
			   its left edge pinned shrinks to fit it — a mobile-specific width here would either
			   fight that number or duplicate it. */
			display: block;
			position: fixed;
			inset: 0 auto 0 0;
			z-index: 11;
			max-width: 92vw;
			height: 100%;
			padding-top: env(safe-area-inset-top);
			animation: fade var(--fade) var(--ease);
		}

		.menu {
			display: block;
			/* Inside the shell rather than the viewport, so it moves with the shell. */
			position: absolute;
			top: calc(14px + env(safe-area-inset-top));
			left: max(14px, env(safe-area-inset-left));
			z-index: 9;
			border-radius: 50%;
			background: var(--surface);
		}
	}
</style>
