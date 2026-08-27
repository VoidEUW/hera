<script lang="ts">
	/**
	 * The left rail: the mark, a new chat, projects that disclose their chats, then loose chats.
	 * Settings sits directly above the profile card at the bottom, where the brief put it.
	 *
	 * Projects disclose inline rather than navigating, because finding a chat under the thing it
	 * belongs to is genuinely easier than finding it in one flat list sorted by time.
	 */
	import { goto } from '$app/navigation';
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
	}

	let { chats, projects, profile, activeId = null, onnew, onsettings }: Props = $props();

	let expanded = $state<Record<string, boolean>>({});

	const loose = $derived(chats.filter((chat) => !chat.project_id));

	function inside(projectId: string): Chat[] {
		return chats.filter((chat) => chat.project_id === projectId);
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
								<li>
									<a class="entry" class:active={chat.id === activeId} href="/chat/{chat.id}">
										<span class="label">{chat.title || t.empty.title}</span>
									</a>
								</li>
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
			<li>
				<a class="entry" class:active={chat.id === activeId} href="/chat/{chat.id}">
					<span class="label">{chat.title || t.empty.title}</span>
				</a>
			</li>
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
			<button class="card" type="button" onclick={() => goto('/')}>
				<span class="initials">{initials(profile.name)}</span>
				<span class="label">{profile.name}</span>
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

	.entry.active {
		color: var(--pomegranate);
		background: var(--surface-raised);
	}

	.label {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
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
