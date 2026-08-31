<script lang="ts">
	/**
	 * The left rail: the mark, a new chat, projects that disclose their chats, then loose chats.
	 * Settings sits directly above the profile card at the bottom, where the brief put it.
	 *
	 * Projects disclose inline rather than navigating, because finding a chat under the thing it
	 * belongs to is genuinely easier than finding it in one flat list sorted by time.
	 *
	 * Every chat carries a **⋯** menu: rename in place, move to a project, delete behind a
	 * confirmation. A project carries the same menu with its own verbs. Renaming is an input
	 * where the title was rather than a prompt box, because the thing being renamed is a line in
	 * a list and you should be able to see the list while you retype it.
	 *
	 * Both row kinds share one set of menu state, keyed by `{ kind, id }` rather than by a bare
	 * id. Ids are UUIDs and would not collide, but *which menu is open* and *what its items mean*
	 * are the same question, and answering it with two parallel sets of fields is how a project
	 * ends up being renamed by the chat handler.
	 */
	import { api, type Chat, type Profile, type Project } from '$lib/api/client';
	import { t } from '$lib/i18n';
	import { colourOf } from '$lib/projects';
	import Ocellus from './Ocellus.svelte';

	interface Props {
		chats: Chat[];
		projects: Project[];
		profile: Profile | null;
		activeId?: string | null;
		activeProjectId?: string | null;
		onnew?: (projectId?: string) => void;
		onsettings?: () => void;
		onprofile?: () => void;
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
		profile,
		activeId = null,
		activeProjectId = null,
		onnew,
		onsettings,
		onprofile,
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

	/** The row whose ⋯ menu is open, the one being renamed, and the one being confirmed for
	 * deletion. Three separate fields rather than one mode, because only one of each can be true
	 * at a time and a single field would let "renaming" survive the menu closing. */
	let menuFor = $state<Target | null>(null);
	let renaming = $state<Target | null>(null);
	let confirming = $state<Target | null>(null);
	/** The chat whose **Move to…** list is showing. A second level inside the menu rather than a
	 * submenu that opens sideways: the rail is 264px wide and there is nowhere sideways to go. */
	let moving = $state<string | null>(null);
	let draft = $state('');
	/** How many artifacts the chat being confirmed for deletion would take with it (ADR 13).
	 * Asked for when the confirmation opens rather than counted for every row: one request at
	 * the moment it matters, instead of a directory listing per chat in the rail. */
	let publishedHere = $state(0);
	/** Naming a new project happens in the list, in the place the project will appear, rather
	 * than in a dialog — the same reasoning as renaming in place. */
	let creating = $state(false);

	const loose = $derived(chats.filter((chat) => !chat.project_id));

	function inside(projectId: string): Chat[] {
		return chats.filter((chat) => chat.project_id === projectId);
	}

	function is(target: Target | null, kind: Kind, id: string): boolean {
		return target?.kind === kind && target.id === id;
	}

	function closeMenu() {
		menuFor = null;
		confirming = null;
		moving = null;
		publishedHere = 0;
	}

	/** Open the confirmation, and go and find out what else goes with it.
	 *
	 * The count arrives a moment after the question, which is the right way round: the sentence
	 * that stops you is *delete this chat?*, and *and the two things she made in it* is the
	 * detail that changes your mind. A confirmation that waited for a request before appearing
	 * would be a menu that changes shape under the pointer. */
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

	/** Both of these are reached twice for one commit, and only the first may act.
	 *
	 * Enter runs the handler, which unmounts the input, which fires `blur` on the way out — so
	 * the same name is submitted a second time. Renaming survived that by accident, because the
	 * second call compares against the name it just set and does nothing. Creating did not:
	 * pressing Enter made *two* projects, and the pair raced for the same slug closely enough
	 * that the loser came back a 500. The guard is the state field that is already there. */
	function commitRename(kind: Kind, id: string, current: string) {
		if (!renaming) return;
		const name = draft.trim();
		renaming = null;
		if (!name || name === current) return;
		if (kind === 'chat') onrename?.(id, name);
		else onprojectrename?.(id, name);
	}

	function commitCreate() {
		if (!creating) return;
		const name = draft.trim();
		creating = false;
		if (name) onnewproject?.(name);
	}

	function startCreate() {
		closeMenu();
		renaming = null;
		draft = '';
		creating = true;
	}

	function move(chatId: string, projectId: string | null) {
		closeMenu();
		onmove?.(chatId, projectId);
	}

	function onkeydown(event: KeyboardEvent) {
		if (event.key !== 'Escape') return;
		closeMenu();
		renaming = null;
		creating = false;
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
		{#if is(renaming, 'chat', chat.id)}
			<input
				class="rename"
				use:takeover
				bind:value={draft}
				aria-label={t.rail.rename}
				onblur={() => commitRename('chat', chat.id, chat.title)}
				onkeydown={(event) => {
					if (event.key === 'Enter') commitRename('chat', chat.id, chat.title);
					if (event.key === 'Escape') renaming = null;
				}}
			/>
		{:else}
			<a class="entry" class:active={chat.id === activeId} href="/chat/{chat.id}">
				<span class="label">{chat.title || t.empty.title}</span>
			</a>
			<button
				class="more"
				class:shown={is(menuFor, 'chat', chat.id)}
				type="button"
				aria-label={t.rail.chatOptions}
				aria-haspopup="menu"
				aria-expanded={is(menuFor, 'chat', chat.id)}
				onclick={() => {
					confirming = null;
					moving = null;
					menuFor = is(menuFor, 'chat', chat.id) ? null : { kind: 'chat', id: chat.id };
				}}
			>
				<span aria-hidden="true">⋯</span>
			</button>
		{/if}

		{#if is(menuFor, 'chat', chat.id)}
			<div class="menu" role="menu">
				{#if is(confirming, 'chat', chat.id)}
					<p class="ask caption">{t.rail.deleteAsk}</p>
					{#if publishedHere}
						<!-- ADR 13: deleting a chat takes what she published in it. *A chat is a
						     thing you throw away* and *the page I made last week* have to be
						     reconciled by a sentence rather than by a surprise. Asked for when the
						     confirmation opens rather than carried on every row — one request at
						     the moment it matters beats a directory listing per chat in the rail. -->
						<p class="ask caption warn">{t.rail.deleteTakes(publishedHere)}</p>
					{/if}
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
				{:else if moving === chat.id}
					<!-- The project it is already in is listed and marked rather than left out: a
					     list that silently drops one entry makes you check twice which one. -->
					{#each projects as project (project.id)}
						<button
							class="option"
							type="button"
							role="menuitemradio"
							aria-checked={chat.project_id === project.id}
							disabled={chat.project_id === project.id}
							onclick={() => move(chat.id, project.id)}
						>
							{project.name}
						</button>
					{/each}
					<button
						class="option"
						type="button"
						role="menuitemradio"
						aria-checked={chat.project_id === null}
						disabled={chat.project_id === null}
						onclick={() => move(chat.id, null)}
					>
						{t.rail.noProject}
					</button>
				{:else}
					<button
						class="option"
						type="button"
						role="menuitem"
						onclick={() => startRename('chat', chat.id, chat.title)}
					>
						{t.rail.rename}
					</button>
					{#if projects.length}
						<button class="option" type="button" role="menuitem" onclick={() => (moving = chat.id)}>
							{t.rail.moveTo}
						</button>
					{/if}
					<button
						class="option danger"
						type="button"
						role="menuitem"
						onclick={() => confirmChat(chat.id)}
					>
						{t.rail.delete}
					</button>
				{/if}
			</div>
		{/if}
	</li>
{/snippet}

{#snippet projectRow(project: Project)}
	{@const open = expanded[project.id] ?? false}
	{@const accent = colourOf(project.color)}
	<li>
		<!-- The project's own line gets the positioning context, not the `li`. A disclosed project
		     `li` is as tall as the whole group inside it, and `.more` is centred on its containing
		     block — so the ⋯ drifted down into the chat list and sat on top of a row, which is
		     both unreachable and unclickable-through. The menu hangs off this too, so it opens
		     under the project rather than under the last chat in it. -->
		<div class="item head">
			{#if is(renaming, 'project', project.id)}
				<input
					class="rename"
					use:takeover
					bind:value={draft}
					aria-label={t.rail.rename}
					onblur={() => commitRename('project', project.id, project.name)}
					onkeydown={(event) => {
						if (event.key === 'Enter') commitRename('project', project.id, project.name);
						if (event.key === 'Escape') renaming = null;
					}}
				/>
			{:else}
				<button
					class="entry project"
					class:active={project.id === activeProjectId}
					type="button"
					aria-expanded={open}
					onclick={() => (expanded = { ...expanded, [project.id]: !open })}
				>
					<span class="chevron" aria-hidden="true">{open ? '▾' : '▸'}</span>
					<span class="dot" style:background={accent ?? 'var(--text-faint)'} aria-hidden="true"
					></span>
					<span class="label">{project.name}</span>
				</button>
				<button
					class="more"
					class:shown={is(menuFor, 'project', project.id)}
					type="button"
					aria-label={t.rail.projectOptions}
					aria-haspopup="menu"
					aria-expanded={is(menuFor, 'project', project.id)}
					onclick={() => {
						confirming = null;
						moving = null;
						menuFor = is(menuFor, 'project', project.id)
							? null
							: { kind: 'project', id: project.id };
					}}
				>
					<span aria-hidden="true">⋯</span>
				</button>
			{/if}

			{#if is(menuFor, 'project', project.id)}
				<div class="menu" role="menu">
					{#if is(confirming, 'project', project.id)}
						<!-- "Its chats are kept" is on the card because it is true and surprising:
						     the API revokes rather than deletes, and nothing anybody said goes away. -->
						<p class="ask caption">{t.rail.removeProjectAsk}</p>
						<button
							class="option danger"
							type="button"
							role="menuitem"
							onclick={() => {
								closeMenu();
								onprojectdelete?.(project.id);
							}}
						>
							{t.rail.removeProject}
						</button>
						<button class="option" type="button" role="menuitem" onclick={closeMenu}>
							{t.rail.cancel}
						</button>
					{:else}
						<a class="option" role="menuitem" href="/project/{project.id}" onclick={closeMenu}>
							{t.rail.open}
						</a>
						<button
							class="option"
							type="button"
							role="menuitem"
							onclick={() => startRename('project', project.id, project.name)}
						>
							{t.rail.rename}
						</button>
						<button
							class="option danger"
							type="button"
							role="menuitem"
							onclick={() => (confirming = { kind: 'project', id: project.id })}
						>
							{t.rail.removeProject}
						</button>
					{/if}
				</div>
			{/if}
		</div>

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

	<!-- Always shown, where it used to appear only once a project existed. A heading with a ＋
	     under it is how you find out projects are a thing; a section that is invisible until you
	     already have one can only be discovered by accident. -->
	<div class="heading-row">
		<p class="heading">{t.rail.projects}</p>
		<button class="new" type="button" aria-label={t.rail.newProject} onclick={startCreate}>
			<span aria-hidden="true">＋</span>
		</button>
	</div>

	<ul class="list">
		{#each projects as project (project.id)}
			{@render projectRow(project)}
		{/each}

		{#if creating}
			<li class="item">
				<input
					class="rename"
					use:takeover
					bind:value={draft}
					aria-label={t.rail.newProject}
					placeholder={t.rail.projectNamePlaceholder}
					onblur={commitCreate}
					onkeydown={(event) => {
						if (event.key === 'Enter') commitCreate();
						if (event.key === 'Escape') creating = false;
					}}
				/>
			</li>
		{:else if !projects.length}
			<li class="hint caption">{t.rail.noProjects}</li>
		{/if}
	</ul>

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

	.heading-row {
		display: flex;
		align-items: center;
	}

	.heading-row .heading {
		flex: 1;
	}

	/* Always visible, unlike a row's ⋯. This is the only way to make a project, so hiding it
	   until the pointer finds it would hide the feature. */
	.new {
		display: grid;
		place-items: center;
		width: 22px;
		height: 22px;
		margin-right: 6px;
		border-radius: 6px;
		color: var(--text-faint);
		font-size: 13px;
		line-height: 1;
		transition:
			background var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	.new:hover {
		background: var(--surface-raised);
		color: var(--text);
	}

	/* The project's colour, if it has one. Four pixels is enough to group a list and not enough
	   to compete with the chat you are in, which is the only thing in this rail that is brass. */
	.dot {
		width: 4px;
		height: 4px;
		flex: none;
		border-radius: 50%;
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

	/* One row: the link, the ⋯, and the popup either of them can open. On a chat this is the
	   `li`; on a project it is a wrapper around the project's own line, because the `li` there
	   also holds the disclosed chats and is as tall as all of them. */
	.item {
		position: relative;
	}

	/* The project's own line. `.item` alone would be enough; the class exists so that what the
	   wrapper is for is legible from the markup rather than only from this comment. */
	.head {
		display: block;
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

	/* The same popup `Select` and the skill picker draw: raised surface, hairline, the large
	   radius, the same shadow and the same fade in. A menu and a dropdown are not the same
	   control, but they are the same *gesture* — a small list, next to the thing it is about —
	   and three different frames for that was the thing that read as unfinished. */
	.menu {
		position: absolute;
		top: calc(100% + 1px);
		right: 4px;
		z-index: 21;
		display: flex;
		flex-direction: column;
		min-width: 168px;
		max-height: 44vh;
		overflow-y: auto;
		padding: 5px;
		background: var(--surface-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow);
		animation: fade var(--fade) var(--ease);
	}

	@keyframes fade {
		from {
			opacity: 0;
		}
	}

	.option {
		display: block;
		width: 100%;
		padding: 7px 8px;
		border-radius: var(--radius);
		text-align: left;
		font-size: 13px;
		color: var(--text-muted);
		text-decoration: none;
		transition: background var(--fade) var(--ease);
	}

	.option:hover,
	.option:focus-visible {
		background: var(--surface);
		color: var(--text);
		outline: none;
	}

	.option.danger:hover {
		color: var(--danger);
	}

	/* The project a chat is already in, in the move list. Shown rather than dropped, so the list
	   is the same length every time you open it and you can see what the answer currently is. */
	.option:disabled {
		color: var(--brass);
		cursor: default;
	}

	.option:disabled:hover {
		background: none;
		color: var(--brass);
	}

	.ask {
		margin: 4px 8px 6px;
		color: var(--text-muted);
	}

	/* The consequence, under the question. Quieter than the question rather than louder: it is a
	   fact about what you are about to lose, not a second alarm. */
	.ask + .ask {
		margin-top: -2px;
	}

	.warn {
		color: var(--text-faint);
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
