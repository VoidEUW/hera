<script lang="ts">
	/**
	 * The chat sidebar: the mark, a new chat, projects that disclose their chats, the loose chats,
	 * and the account — which is the door into Settings, labelled with who you are.
	 *
	 * Built from the sidebar primitives (`ui/sidebar/`), so its shell, its rows, its groups and
	 * its resize handle are the same ones Settings uses. What is left here
	 * is the part that is about chats and projects:
	 *
	 * - Projects disclose inline rather than navigating, because finding a chat under the thing it
	 *   belongs to is easier than finding it in one flat list sorted by time.
	 * - Every chat and project carries a **more** menu: rename in place, export, move to a project,
	 *   delete behind a confirmation. Renaming is an input where the title was, because the thing
	 *   being renamed is a line in a list and you should see the list while you retype it.
	 * - Deleting a chat says how many artifacts go with it, asked for when the confirmation opens
	 *   rather than carried on every row (ADR 13).
	 */
	import { untrack } from 'svelte';
	import { resolve } from '$app/paths';
	import { API, api, type Account, type Chat, type Project } from '$lib/api/client';
	import { t } from '$lib/i18n';
	import { Placeholder } from '$lib/loading.svelte';
	import { disclose } from '$lib/motion';
	import { colourOf } from '$lib/projects';
	import type { Shape } from '$lib/stores/workspace.svelte';
	import Avatar from './ui/Avatar.svelte';
	import IconButton from './ui/IconButton.svelte';
	import Input from './ui/Input.svelte';
	import Menu from './ui/Menu.svelte';
	import MenuItem from './ui/MenuItem.svelte';
	import MenuNote from './ui/MenuNote.svelte';
	import Ocellus from './ui/Ocellus.svelte';
	import SearchBar from './ui/SearchBar.svelte';
	import Skeleton from './ui/Skeleton.svelte';
	import Sidebar from './ui/sidebar/Sidebar.svelte';
	import SidebarEntry from './ui/sidebar/SidebarEntry.svelte';
	import SidebarGroup from './ui/sidebar/SidebarGroup.svelte';

	interface Props {
		chats: Chat[];
		projects: Project[];
		account: Account | null;
		activeId?: string | null;
		activeProjectId?: string | null;
		loading?: boolean;
		shape?: Shape;
		/** Shown as the phone's sheet: never resized. */
		sheet?: boolean;
		onnew?: (projectId?: string) => void;
		onsettings?: () => void;
		settingsOpen?: boolean;
		onrename?: (id: string, title: string) => void;
		ondelete?: (id: string) => void;
		onmove?: (chatId: string, projectId: string | null) => void;
		onnewproject?: (name: string) => void;
		onprojectrename?: (id: string, name: string) => void;
		onprojectdelete?: (id: string) => void;
	}

	let {
		chats,
		projects,
		account,
		activeId = null,
		activeProjectId = null,
		loading = false,
		shape = { chats: 3, projects: 2 },
		sheet = false,
		onnew,
		onsettings,
		settingsOpen = false,
		onrename,
		ondelete,
		onmove,
		onnewproject,
		onprojectrename,
		onprojectdelete
	}: Props = $props();

	type Kind = 'chat' | 'project';
	type Target = { kind: Kind; id: string };

	let expanded = $state<Record<string, boolean>>({});
	let projectsOpen = $state(true);
	let chatsOpen = $state(true);

	/** The row whose menu is open, the one being renamed, the one being confirmed for deletion,
	 * and the chat whose *Move to…* list is showing — one set of state for both row kinds, keyed
	 * by `{ kind, id }`, so opening one menu closes any other. */
	let menuFor = $state<Target | null>(null);
	let renaming = $state<Target | null>(null);
	let confirming = $state<Target | null>(null);
	let moving = $state<string | null>(null);
	let draft = $state('');
	let publishedHere = $state(0);
	let creating = $state(false);

	/** Where each row's menu hangs from, keyed `kind:id`. */
	let anchors = $state<Record<string, HTMLElement | null>>({});

	const loose = $derived(chats.filter((chat) => !chat.project_id));

	/** The search bar's filter: titles containing it, across every project, in one list. */
	let query = $state('');
	let searchField = $state<HTMLInputElement | null>(null);
	const found = $derived.by(() => {
		const needle = query.trim().toLowerCase();
		return needle ? chats.filter((chat) => chat.title.toLowerCase().includes(needle)) : null;
	});

	/** ⌘K / Ctrl+K focuses the search from anywhere — the shortcut its hint shows. */
	function shortcut(event: KeyboardEvent) {
		if (event.key.toLowerCase() !== 'k' || !(event.metaKey || event.ctrlKey)) return;
		event.preventDefault();
		searchField?.focus();
	}

	/* The shape of the rows that are coming, held long enough that a list arrives rather than
	   appearing (`$lib/loading`). */
	const settling = new Placeholder(untrack(() => loading));
	$effect(() => settling.set(loading));
	$effect(() => () => settling.stop());
	const waiting = $derived(settling.shown);

	const shown = $derived(account?.name || t.rail.accountLabel);

	/** A skeleton bar is 15px; with this gap the bars land on the pitch of a sidebar row (eight
	 * density units plus the 2px between rows), so the placeholder is the height the list will be
	 * and nothing moves when the rows replace it. */
	const ROW_GAP = 21;

	function inside(projectId: string): Chat[] {
		return chats.filter((chat) => chat.project_id === projectId);
	}

	function is(target: Target | null, kind: Kind, id: string): boolean {
		return target?.kind === kind && target.id === id;
	}

	function toggleMenu(kind: Kind, id: string) {
		confirming = null;
		moving = null;
		menuFor = is(menuFor, kind, id) ? null : { kind, id };
	}

	function closeMenu() {
		menuFor = null;
		confirming = null;
		moving = null;
		publishedHere = 0;
	}

	function confirmChat(id: string) {
		confirming = { kind: 'chat', id };
		publishedHere = 0;
		api
			.artifacts(id)
			.then((found) => {
				if (is(confirming, 'chat', id)) publishedHere = found.length;
			})
			.catch(() => {
				/* a count that could not be read is not worth blocking a delete over */
			});
	}

	function startRename(kind: Kind, id: string, current: string) {
		closeMenu();
		renaming = { kind, id };
		draft = current;
	}

	function commitRename(kind: Kind, id: string, current: string) {
		if (!renaming) return;
		const name = draft.trim();
		renaming = null;
		if (!name || name === current) return;
		if (kind === 'chat') onrename?.(id, name);
		else onprojectrename?.(id, name);
	}

	function startCreate() {
		closeMenu();
		renaming = null;
		draft = '';
		creating = true;
		projectsOpen = true;
	}

	function commitCreate() {
		if (!creating) return;
		const name = draft.trim();
		creating = false;
		if (name) onnewproject?.(name);
	}

	function move(chatId: string, projectId: string | null) {
		closeMenu();
		onmove?.(chatId, projectId);
	}
</script>

{#snippet rename(kind: Kind, id: string, current: string, label: string)}
	<Input
		variant="inline"
		class="rename"
		autofocus
		value={draft}
		ariaLabel={label}
		onchange={(value) => (draft = value)}
		onblur={() => commitRename(kind, id, current)}
		onkeydown={(event) => {
			if (event.key === 'Enter') commitRename(kind, id, current);
			if (event.key === 'Escape') renaming = null;
		}}
	/>
{/snippet}

{#snippet more(kind: Kind, id: string, label: string)}
	<IconButton
		bind:ref={anchors[`${kind}:${id}`]}
		icon="more"
		size="sm"
		{label}
		aria-haspopup="menu"
		aria-expanded={is(menuFor, kind, id)}
		onclick={() => toggleMenu(kind, id)}
	/>
{/snippet}

{#snippet chatRow(chat: Chat, nested: boolean)}
	<div class="item">
		{#if is(renaming, 'chat', chat.id)}
			{@render rename('chat', chat.id, chat.title, t.rail.rename)}
		{:else}
			<SidebarEntry
				icon="chat"
				label={chat.title || t.empty.title}
				href={resolve('/chat/[id]', { id: chat.id })}
				active={chat.id === activeId}
				pinned={is(menuFor, 'chat', chat.id)}
				{nested}
			>
				{#snippet action()}{@render more('chat', chat.id, t.rail.chatOptions)}{/snippet}
			</SidebarEntry>
		{/if}

		<Menu
			open={is(menuFor, 'chat', chat.id)}
			anchor={anchors[`chat:${chat.id}`] ?? null}
			label={t.rail.chatOptions}
			onclose={closeMenu}
		>
			{#if is(confirming, 'chat', chat.id)}
				<MenuNote>{t.rail.deleteAsk}</MenuNote>
				{#if publishedHere}<MenuNote quiet>{t.rail.deleteTakes(publishedHere)}</MenuNote>{/if}
				<MenuItem
					icon="trash"
					danger
					onclick={() => {
						closeMenu();
						ondelete?.(chat.id);
					}}>{t.rail.delete}</MenuItem
				>
				<MenuItem onclick={closeMenu}>{t.rail.cancel}</MenuItem>
			{:else if moving === chat.id}
				{#each projects as project (project.id)}
					<MenuItem
						icon="folder"
						trail="check"
						on={chat.project_id === project.id}
						disabled={chat.project_id === project.id}
						onclick={() => move(chat.id, project.id)}>{project.name}</MenuItem
					>
				{/each}
				<MenuItem
					icon="chat"
					trail="check"
					on={chat.project_id === null}
					disabled={chat.project_id === null}
					onclick={() => move(chat.id, null)}>{t.rail.noProject}</MenuItem
				>
			{:else}
				<MenuItem icon="edit" onclick={() => startRename('chat', chat.id, chat.title)}>
					{t.rail.rename}
				</MenuItem>
				<MenuItem
					icon="download"
					href={`${API}/chats/${chat.id}/export.md`}
					download
					external
					onclick={closeMenu}>{t.rail.export}</MenuItem
				>
				{#if projects.length}
					<MenuItem icon="folder" onclick={() => (moving = chat.id)}>{t.rail.moveTo}</MenuItem>
				{/if}
				<MenuItem icon="trash" danger onclick={() => confirmChat(chat.id)}>
					{t.rail.delete}
				</MenuItem>
			{/if}
		</Menu>
	</div>
{/snippet}

{#snippet projectRow(project: Project)}
	{@const open = expanded[project.id] ?? false}
	<div class="item">
		{#if is(renaming, 'project', project.id)}
			{@render rename('project', project.id, project.name, t.rail.rename)}
		{:else}
			<!-- The folder is the disclosure and the colour at once: two tiny marks (a chevron and
			     a dot) used to do the job of one (#102). -->
			<SidebarEntry
				icon="folder"
				tint={colourOf(project.color) ?? undefined}
				label={project.name}
				expanded={open}
				active={project.id === activeProjectId}
				pinned={is(menuFor, 'project', project.id)}
				onclick={() => (expanded = { ...expanded, [project.id]: !open })}
			>
				{#snippet action()}{@render more('project', project.id, t.rail.projectOptions)}{/snippet}
			</SidebarEntry>
		{/if}

		<Menu
			open={is(menuFor, 'project', project.id)}
			anchor={anchors[`project:${project.id}`] ?? null}
			label={t.rail.projectOptions}
			onclose={closeMenu}
		>
			{#if is(confirming, 'project', project.id)}
				<MenuNote>{t.rail.removeProjectAsk}</MenuNote>
				<MenuItem
					icon="trash"
					danger
					onclick={() => {
						closeMenu();
						onprojectdelete?.(project.id);
					}}>{t.rail.removeProject}</MenuItem
				>
				<MenuItem onclick={closeMenu}>{t.rail.cancel}</MenuItem>
			{:else}
				<MenuItem
					icon="external"
					href={resolve('/project/[id]', { id: project.id })}
					onclick={closeMenu}>{t.rail.open}</MenuItem
				>
				<MenuItem icon="edit" onclick={() => startRename('project', project.id, project.name)}>
					{t.rail.rename}
				</MenuItem>
				<MenuItem
					icon="trash"
					danger
					onclick={() => (confirming = { kind: 'project', id: project.id })}
					>{t.rail.removeProject}</MenuItem
				>
			{/if}
		</Menu>
	</div>

	{#if open}
		<!-- A height, not a slide: the chats below make room rather than a panel arriving on top
		     of them, so the row under the pointer stays under it. -->
		<div
			class="nested"
			in:disclose={{ slot: 'group-disclose' }}
			out:disclose={{ slot: 'group-disclose' }}
		>
			{#each inside(project.id) as chat (chat.id)}
				{@render chatRow(chat, true)}
			{:else}
				<p class="hint">{t.rail.noChats}</p>
			{/each}
			<SidebarEntry icon="plus" label={t.rail.newChat} nested onclick={() => onnew?.(project.id)} />
		</div>
	{/if}
{/snippet}

<svelte:window onkeydown={shortcut} />

<Sidebar variant="chat" label={t.appName} resizable={!sheet}>
	{#snippet head()}
		<div class="brand-row">
			<a class="brand" href={resolve('/')} aria-label={t.appName}>
				<Ocellus size={22} />
				<span class="display wordmark">{t.appName}</span>
			</a>
		</div>
		<SidebarEntry icon="plus" label={t.rail.newChat} onclick={() => onnew?.()} />
		<div class="search">
			<SearchBar
				bind:ref={searchField}
				value={query}
				placeholder={t.rail.search}
				shortcut="⌘K"
				onchange={(value) => (query = value)}
			/>
		</div>
	{/snippet}

	{#if found}
		<SidebarGroup label={t.rail.results} count={found.length} fixed>
			{#each found as chat (chat.id)}
				{@render chatRow(chat, false)}
			{:else}
				<p class="hint">{t.settings.noMatch}</p>
			{/each}
		</SidebarGroup>
	{:else}
		<!-- Always shown, even with no projects: a heading with an add button under it is how you
	     find out projects are a thing. -->
		<SidebarGroup
			label={t.rail.projects}
			count={waiting ? undefined : projects.length}
			addLabel={t.rail.newProject}
			onadd={startCreate}
			bind:open={projectsOpen}
		>
			{#if waiting}
				<div class="waiting">
					<Skeleton
						rows={shape.projects}
						height={15}
						gap={ROW_GAP}
						widths={[70, 52, 63]}
						label={t.rail.loadingProjects}
					/>
				</div>
			{:else}
				{#each projects as project (project.id)}
					{@render projectRow(project)}
				{/each}
				{#if creating}
					<div class="item">
						<Input
							variant="inline"
							class="rename"
							autofocus
							value={draft}
							ariaLabel={t.rail.newProject}
							placeholder={t.rail.projectNamePlaceholder}
							onchange={(value) => (draft = value)}
							onblur={commitCreate}
							onkeydown={(event) => {
								if (event.key === 'Enter') commitCreate();
								if (event.key === 'Escape') creating = false;
							}}
						/>
					</div>
				{:else if !projects.length}
					<p class="hint">{t.rail.noProjects}</p>
				{/if}
			{/if}
		</SidebarGroup>

		<SidebarGroup
			label={t.rail.chats}
			count={waiting ? undefined : loose.length}
			bind:open={chatsOpen}
		>
			{#if waiting}
				<div class="waiting">
					<Skeleton
						rows={shape.chats}
						height={15}
						gap={ROW_GAP}
						widths={[82, 64, 74]}
						label={t.rail.loadingChats}
					/>
				</div>
			{:else}
				{#each loose as chat (chat.id)}
					{@render chatRow(chat, false)}
				{:else}
					<p class="hint">{t.rail.noChats}</p>
				{/each}
			{/if}
		</SidebarGroup>
	{/if}

	{#snippet foot()}
		{#if waiting}
			<!-- The foot is pinned to the bottom of the window, so arriving late would move it out
			     from under the pointer. Hold its height. -->
			<Skeleton rows={1} height={32} widths={[100]} />
		{:else}
			<!-- Who you are, and the way into Settings: the account screen is Settings' first page,
			     so this is the door to press. It draws before the account has answered (as
			     "Account") so a slow request cannot lock Settings away. -->
			<SidebarEntry
				label={shown}
				ariaLabel={t.rail.account(shown)}
				active={settingsOpen}
				onclick={() => onsettings?.()}
			>
				{#snippet lead()}
					<Avatar
						name={account?.name ?? ''}
						src={account?.avatar_version ? api.avatarUrl(account.avatar_version) : undefined}
						size={22}
					/>
				{/snippet}
			</SidebarEntry>
		{/if}
	{/snippet}
</Sidebar>

<style>
	.brand-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: calc(var(--space) * 10);
		padding: 0 var(--sb-ir) 0 calc(var(--sb-ix) - 3px);
		margin-bottom: calc(var(--space) * 1);
	}

	.brand {
		display: flex;
		align-items: center;
		gap: calc(var(--sb-gap) - 2px);
		min-width: 0;
		color: var(--text);
		text-decoration: none;
	}

	.wordmark {
		font-size: 21px;
		line-height: 1;
	}

	.search {
		margin: calc(var(--space) * 1.5) 0 calc(var(--space) * 1);
	}

	.item {
		position: relative;
		animation: arrive var(--fade) var(--ease);
	}

	@keyframes arrive {
		from {
			opacity: 0;
		}
	}

	.item :global(.rename) {
		margin: 1px 0;
	}

	.hint {
		margin: 0;
		padding: calc(var(--space) * 1) var(--sb-ix);
		color: var(--text-faint);
		font-size: calc(var(--ui-size) - 1.5px);
	}

	.nested .hint {
		padding-left: calc(var(--sb-ix) + var(--sb-lead) + var(--sb-gap) - 4px);
	}

	/* `Skeleton` draws no padding of its own; the rows it stands in for are inset by the row's
	   own inset. */
	.waiting {
		padding: calc(var(--space) * 2) var(--sb-ix);
	}
</style>
