<script lang="ts">
	/**
	 * What the command palette is *made of* (#112): the places and actions Hera has, as rows for
	 * `ui/Palette`, which owns how a list is searched and walked.
	 *
	 * Chats by title, projects, Settings screens, and the actions that already have a button — new
	 * chat, Settings, the keyboard shortcuts — each with the chord that does the same thing drawn
	 * at the end of its row, so the palette teaches the keys. Titles are matched in the browser:
	 * the rail already holds every chat, so a round trip would only make the list slower than the
	 * thing it lists. `scope="chats"` is the same palette asked a narrower question.
	 */
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { t } from '$lib/i18n';
	import { ENTRIES } from '$lib/settingsTabs';
	import { workspace } from '$lib/stores/workspace.svelte';
	import Palette, { type PaletteItem } from './ui/Palette.svelte';

	interface Props {
		scope?: 'all' | 'chats';
		onnewchat: () => void;
		onclose: () => void;
	}

	let { scope = 'all', onnewchat, onclose }: Props = $props();

	let query = $state('');

	const items = $derived.by(() => {
		const projectName = new Map(workspace.projects.map((project) => [project.id, project.name]));
		const chats: PaletteItem[] = workspace.chats.map((chat) => ({
			id: `chat-${chat.id}`,
			label: chat.title || t.empty.title,
			description: chat.project_id ? projectName.get(chat.project_id) : undefined,
			icon: 'chat',
			group: t.palette.chats,
			run: () => void goto(resolve('/chat/[id]', { id: chat.id }))
		}));
		if (scope === 'chats') return chats;

		const actions: PaletteItem[] = [
			{
				id: 'new-chat',
				label: t.rail.newChat,
				icon: 'plus',
				group: t.palette.actions,
				keyId: 'newChat',
				run: onnewchat
			},
			{
				id: 'settings',
				label: t.settings.title,
				icon: 'sliders',
				group: t.palette.actions,
				keyId: 'settings',
				run: () => workspace.openSettings()
			},
			{
				id: 'hotkeys',
				label: t.settings.hotkeys,
				icon: 'keyboard',
				group: t.palette.actions,
				keyId: 'hotkeys',
				run: () => workspace.openSettings('hotkeys')
			}
		];
		const projects: PaletteItem[] = workspace.projects.map((project) => ({
			id: `project-${project.id}`,
			label: project.name,
			icon: 'folder',
			group: t.palette.projects,
			run: () => void goto(resolve('/project/[id]', { id: project.id }))
		}));
		const screens: PaletteItem[] = ENTRIES.filter(
			(entry) => !entry.soon && entry.id !== 'hotkeys'
		).map((entry) => ({
			id: `settings-${entry.id}`,
			label: entry.label,
			description: entry.blurb,
			icon: entry.icon,
			group: t.palette.settings,
			run: () => workspace.openSettings(entry.id)
		}));
		return [...actions, ...chats, ...projects, ...screens];
	});
</script>

<Palette
	label={t.palette.label}
	placeholder={scope === 'chats' ? t.palette.chatsPlaceholder : t.palette.placeholder}
	empty={t.palette.empty}
	{items}
	bind:query
	{onclose}
/>
