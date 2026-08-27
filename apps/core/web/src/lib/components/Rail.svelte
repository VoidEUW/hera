<script lang="ts">
	/**
	 * The left rail: the mark, a new chat, projects that disclose their chats, then loose chats.
	 * Settings sits directly above the profile card at the bottom, where the brief put it.
	 *
	 * Projects disclose inline rather than navigating, because finding a chat under the thing it
	 * belongs to is genuinely easier than finding it in one flat list sorted by time.
	 *
	 * Every chat carries a **⋯** menu: rename in place, delete behind a confirmation. Renaming
	 * is an input where the title was rather than a prompt box, because the thing being renamed
	 * is a line in a list and you should be able to see the list while you retype it.
	 */
	import type { Chat, Profile, Project } from '$lib/api/client';
	import { t } from '$lib/i18n';
	import Ocellus from './Ocellus.svelte';

	interface Props {
		chats: Chat[];
		projects: Project[];
		profile: Profile | null;
		activeId?: string | null;
		onnew?: (projectId?: string) => void;
		onsettings?: () => void;
		onprofile?: () => void;
		onrename?: (id: string, title: string) => void;
		ondelete?: (id: string) => void;
	}

	let {
		chats,
		projects,
		profile,
		activeId = null,
		onnew,
		onsettings,
		onprofile,
		onrename,
		ondelete
	}: Props = $props();

	let expanded = $state<Record<string, boolean>>({});

	/** The chat whose ⋯ menu is open, the one being renamed, and the one being confirmed for
	 * deletion. Three separate ids rather than one mode, because only one of each can be true
	 * at a time and a single field would let "renaming" survive the menu closing. */
	let menuFor = $state<string | null>(null);
	let renaming = $state<string | null>(null);
	let confirming = $state<string | null>(null);
	let draft = $state('');

	const loose = $derived(chats.filter((chat) => !chat.project_id));

	function inside(projectId: string): Chat[] {
		return chats.filter((chat) => chat.project_id === projectId);
	}

	function closeMenu() {
		menuFor = null;
		confirming = null;
	}

	function startRename(chat: Chat) {
		closeMenu();
		renaming = chat.id;
		draft = chat.title;
	}

	function commitRename(chat: Chat) {
		const title = draft.trim();
		renaming = null;
		if (title && title !== chat.title) onrename?.(chat.id, title);
	}

	function onkeydown(event: KeyboardEvent) {
		if (event.key !== 'Escape') return;
		closeMenu();
		renaming = null;
	}

	/** The field takes the cursor and the whole title with it. The menu item that opened it is
	 * gone by then, so leaving focus behind would leave it nowhere. */
	function takeover(node: HTMLInputElement) {
		node.focus();
		node.select();
	}

	function initials(name: string): string {
		return name
			.split(/\s+/)
			.filter(Boolean)
			.slice(0, 2)
			.map((part) => part[0]?.toUpperCase() ?? '')
			.join('');
	}
</script>

<svelte:window {onkeydown} />

{#snippet row(chat: Chat)}
	<li class="item">
		{#if renaming === chat.id}
			<input
				class="rename"
				use:takeover
				bind:value={draft}
				aria-label={t.rail.rename}
				onblur={() => commitRename(chat)}
				onkeydown={(event) => {
					if (event.key === 'Enter') commitRename(chat);
					if (event.key === 'Escape') renaming = null;
				}}
			/>
		{:else}
			<a class="entry" class:active={chat.id === activeId} href="/chat/{chat.id}">
				<span class="label">{chat.title || t.empty.title}</span>
			</a>
			<button
				class="more"
				class:shown={menuFor === chat.id}
				type="button"
				aria-label={t.rail.chatOptions}
				aria-haspopup="menu"
				aria-expanded={menuFor === chat.id}
				onclick={() => {
					confirming = null;
					menuFor = menuFor === chat.id ? null : chat.id;
				}}
			>
				<span aria-hidden="true">⋯</span>
			</button>
		{/if}

		{#if menuFor === chat.id}
			<div class="menu" role="menu">
				{#if confirming === chat.id}
					<p class="ask caption">{t.rail.deleteAsk}</p>
					<button
						class="option danger"
						type="button"
						role="menuitem"
						onclick={() => {
							closeMenu();
							ondelete?.(chat.id);
						}}
					>
						{t.rail.delete}
					</button>
					<button class="option" type="button" role="menuitem" onclick={closeMenu}>
						{t.rail.cancel}
					</button>
				{:else}
					<button class="option" type="button" role="menuitem" onclick={() => startRename(chat)}>
						{t.rail.rename}
					</button>
					<button
						class="option danger"
						type="button"
						role="menuitem"
						onclick={() => (confirming = chat.id)}
					>
						{t.rail.delete}
					</button>
				{/if}
			</div>
		{/if}
	</li>
{/snippet}

{#if menuFor}
	<!-- Catches the click that closes the menu. Transparent rather than dimmed: this is a
	     three-line popup, not a modal, and darkening the application behind it would say
	     otherwise. -->
	<div
		class="away"
		role="presentation"
		onclick={closeMenu}
		onkeydown={(event) => event.key === 'Enter' && closeMenu()}
	></div>
{/if}

<nav class="rail" aria-label={t.appName}>
	<a class="brand" href="/">
		<Ocellus size={22} />
		<span class="display wordmark">{t.appName}</span>
	</a>

	<button class="action" type="button" onclick={() => onnew?.()}>
		<span class="glyph" aria-hidden="true">＋</span>
		{t.rail.newChat}
	</button>

	{#if projects.length}
		<p class="heading">{t.rail.projects}</p>
		<ul class="list">
			{#each projects as project (project.id)}
				{@const open = expanded[project.id] ?? false}
				<li>
					<button
						class="entry project"
						type="button"
						aria-expanded={open}
						onclick={() => (expanded = { ...expanded, [project.id]: !open })}
					>
						<span class="chevron" aria-hidden="true">{open ? '▾' : '▸'}</span>
						<span class="label">{project.name}</span>
					</button>
					{#if open}
						<ul class="list nested">
							{#each inside(project.id) as chat (chat.id)}
								{@render row(chat)}
							{:else}
								<li class="hint caption">{t.rail.noChats}</li>
							{/each}
							<li>
								<button class="entry add" type="button" onclick={() => onnew?.(project.id)}>
									<span class="glyph" aria-hidden="true">＋</span>
									{t.rail.newChat}
								</button>
							</li>
						</ul>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}

	<p class="heading">{t.rail.chats}</p>
	<ul class="list scroll">
		{#each loose as chat (chat.id)}
			{@render row(chat)}
		{:else}
			<li class="hint caption">{t.rail.noChats}</li>
		{/each}
	</ul>

	<div class="foot">
		<button class="action" type="button" onclick={() => onsettings?.()}>
			<span class="glyph" aria-hidden="true">⚙</span>
			{t.rail.settings}
		</button>

		{#if profile}
			<!-- Everything that is about *you* rather than about her behaviour lives behind this:
			     appearance, which of her answers, where your data is. Settings above is the other
			     half, and keeping them apart is why neither of them is a scroll. -->
			<button class="card" type="button" onclick={() => onprofile?.()}>
				<span class="initials">{initials(profile.name)}</span>
				<span class="label">{profile.name}</span>
				<span class="chevron up" aria-hidden="true">▴</span>
			</button>
		{/if}
	</div>
</nav>

<style>
	.rail {
		display: flex;
		flex-direction: column;
		gap: 4px;
		width: var(--rail);
		flex: none;
		height: 100%;
		padding: 14px 10px;
		background: var(--surface);
		border-right: 1px solid var(--line);
		overflow: hidden;
	}

	.brand {
		display: flex;
		align-items: center;
		gap: 9px;
		padding: 6px 8px 12px;
		text-decoration: none;
	}

	.wordmark {
		font-size: 18px;
	}

	.heading {
		margin: 14px 8px 4px;
		font-size: 11px;
		letter-spacing: 0.09em;
		text-transform: uppercase;
		color: var(--text-faint);
	}

	.list {
		list-style: none;
		margin: 0;
		padding: 0;
	}

	.scroll {
		overflow-y: auto;
		flex: 1;
		min-height: 0;
	}

	.nested {
		padding-left: 14px;
	}

	.entry,
	.action {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		padding: 6px 8px;
		border-radius: var(--radius);
		color: var(--text-muted);
		text-decoration: none;
		font-size: 13.5px;
		text-align: left;
		transition:
			background var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	.entry:hover,
	.action:hover {
		background: var(--surface-raised);
		color: var(--text);
	}

	/* Brass, not pomegranate. Gold leads the interface now, and "which chat am I in" is a
	   statement about where you are rather than about her — the same kind of thing a skill row
	   and a permission card are saying. Pomegranate is kept for the two places that are her:
	   the send action and her name. */
	.entry.active {
		color: var(--brass);
		background: var(--surface-raised);
	}

	.label {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* One chat: the link, the ⋯, and the popup either of them can open. */
	.item {
		position: relative;
	}

	/* Room for the ⋯ so a long title is cut by the button rather than sliding under it. */
	.item .entry {
		padding-right: 30px;
	}

	.more {
		position: absolute;
		top: 50%;
		right: 4px;
		transform: translateY(-50%);
		display: grid;
		place-items: center;
		width: 22px;
		height: 22px;
		border-radius: 6px;
		color: var(--text-faint);
		font-size: 14px;
		line-height: 1;
		opacity: 0;
		transition:
			opacity var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	/* Shown on hover, on keyboard focus anywhere in the row, and while its own menu is open —
	   a control that only appears under a pointer is a control a keyboard cannot reach. */
	.item:hover .more,
	.item:focus-within .more,
	.more.shown {
		opacity: 1;
	}

	.more:hover {
		background: var(--surface);
		color: var(--text);
	}

	.rename {
		width: 100%;
		padding: 6px 8px;
		background: var(--ground);
		border: 1px solid var(--brass);
		border-radius: var(--radius);
		font-size: 13.5px;
	}

	.rename:focus {
		outline: none;
	}

	.away {
		position: fixed;
		inset: 0;
		z-index: 20;
	}

	.menu {
		position: absolute;
		top: calc(100% - 2px);
		right: 4px;
		z-index: 21;
		display: flex;
		flex-direction: column;
		min-width: 148px;
		padding: 4px;
		background: var(--surface-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		box-shadow: var(--shadow);
	}

	.option {
		padding: 6px 8px;
		border-radius: 6px;
		text-align: left;
		font-size: 13px;
		color: var(--text-muted);
	}

	.option:hover {
		background: var(--surface);
		color: var(--text);
	}

	.option.danger:hover {
		color: var(--danger);
	}

	.ask {
		margin: 4px 8px 6px;
		color: var(--text-muted);
	}

	.chevron {
		width: 10px;
		color: var(--text-faint);
	}

	.glyph {
		color: var(--text-faint);
	}

	.add {
		color: var(--text-faint);
	}

	.hint {
		padding: 4px 8px;
		color: var(--text-faint);
	}

	.foot {
		margin-top: auto;
		padding-top: 10px;
		border-top: 1px solid var(--line);
	}

	.card {
		display: flex;
		align-items: center;
		gap: 9px;
		width: 100%;
		margin-top: 6px;
		padding: 8px;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 13.5px;
	}

	.up {
		margin-left: auto;
	}

	.initials {
		display: grid;
		place-items: center;
		width: 24px;
		height: 24px;
		flex: none;
		border-radius: 6px;
		background: var(--surface-raised);
		font-size: 11px;
		letter-spacing: 0.04em;
		color: var(--text-muted);
	}
</style>
