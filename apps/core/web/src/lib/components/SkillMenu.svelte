<script lang="ts">
	/**
	 * Which skills are switched on — for a chat, or for a project. A chip that counts them (brass
	 * when any are), opening the shared menu with one checkbox row per enabled skill.
	 *
	 * ADR 5 says the *model* is never asked which skill applies — selection is code. This is the
	 * other half of that sentence: when code guesses wrong, a person needs somewhere to say *use
	 * this one*. A pin here outranks the profile's and the project's, because it is the most
	 * specific thing anybody said; retrieval still runs and can still add more. Applied as it is
	 * clicked: a switch that needs confirming is a switch you have to remember you flipped.
	 *
	 * `locked` are pins that come from somewhere else — the profile answering — shown on and not
	 * changeable here, so the count on the chip is the set she will actually be given.
	 */
	import { api, type Skill } from '$lib/api/client';
	import { t } from '$lib/i18n';
	import Chip from './ui/Chip.svelte';
	import Menu from './ui/Menu.svelte';
	import MenuHeading from './ui/MenuHeading.svelte';
	import MenuItem from './ui/MenuItem.svelte';
	import MenuNote from './ui/MenuNote.svelte';
	import SearchBar from './ui/SearchBar.svelte';

	interface Props {
		pinned: string[];
		locked?: string[];
		heading?: string;
		placement?: 'above' | 'below';
		onpick: (names: string[]) => void;
	}

	let {
		pinned,
		locked = [],
		heading = t.skills.title,
		placement = 'above',
		onpick
	}: Props = $props();

	let open = $state(false);
	let chip = $state<HTMLButtonElement | null>(null);
	let skills = $state<Skill[] | null>(null);
	let query = $state('');
	let error = $state<string | null>(null);

	const on = $derived([...pinned, ...locked.filter((name) => !pinned.includes(name))]);
	const shown = $derived.by(() => {
		const filter = query.trim().toLowerCase();
		return (skills ?? []).filter(
			(skill) =>
				skill.enabled &&
				(!filter || `${skill.id} ${skill.description}`.toLowerCase().includes(filter))
		);
	});

	async function toggleMenu() {
		open = !open;
		if (!open || skills) return;
		try {
			skills = (await api.skills()).skills;
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		}
	}

	function toggle(id: string) {
		onpick(pinned.includes(id) ? pinned.filter((name) => name !== id) : [...pinned, id]);
	}
</script>

<Chip
	bind:ref={chip}
	on={on.length > 0}
	haspopup="menu"
	expanded={open}
	hint={on.join(', ') || undefined}
	onclick={toggleMenu}
>
	{on.length ? t.composer.skillCount(on.length) : t.skills.pick}
</Chip>
<Menu {open} anchor={chip} label={heading} {placement} onclose={() => (open = false)}>
	<MenuHeading>{heading}</MenuHeading>
	{#if (skills?.length ?? 0) > 8}
		<div class="search">
			<SearchBar
				value={query}
				placeholder={t.skills.search}
				onchange={(value) => (query = value)}
			/>
		</div>
	{/if}
	{#if error}<MenuNote quiet>{error}</MenuNote>{/if}
	{#each shown as skill (skill.id)}
		{@const fixed = locked.includes(skill.id) && !pinned.includes(skill.id)}
		<MenuItem
			trail="checkbox"
			on={on.includes(skill.id)}
			disabled={fixed}
			description={fixed ? t.skills.fromProfile : skill.description || t.skills.nothing}
			onclick={() => toggle(skill.id)}>{skill.id}</MenuItem
		>
	{:else}
		{#if skills}
			<MenuNote quiet>{query ? t.settings.noMatch : t.settings.noSkills}</MenuNote>
		{/if}
	{/each}
</Menu>

<style>
	.search {
		padding: 2px 4px 6px;
	}
</style>
