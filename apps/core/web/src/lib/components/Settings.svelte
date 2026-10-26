<script lang="ts">
	/**
	 * Settings.
	 *
	 * Grouped by what kind of thing a setting is, so the eye can tell them apart before reading:
	 * **App** is about this browser and this machine; **Hera** is who she is — her mind, what she
	 * remembers, what she runs on; **Adjust** is what she can reach and what she may do with it.
	 * Within a group the order is what a person reaches for, with **Models** first among hers
	 * because until she is pointed at an endpoint nothing else in Hera does anything.
	 * **Dreaming** is listed and disabled rather than hidden: a v0.3 feature you can see coming
	 * is a promise, and one you cannot is a surprise.
	 *
	 * The search field sits at the top of the sidebar, beside the navigation it is about, and the
	 * title lives in the content: the modal's own header is only a way out. Every screen is a
	 * file in `settings/` that takes the `filter` and fetches for itself.
	 *
	 * A modal, because settings is somewhere you go and come back from, and a modal keeps the
	 * conversation visible behind it.
	 */
	import { t } from '$lib/i18n';
	import SearchBar from '$lib/components/ui/SearchBar.svelte';
	import Modal from '$lib/components/ui/Modal.svelte';
	import Ocellus from '$lib/components/ui/Ocellus.svelte';
	import { ENTRIES, GROUPS, type Tab } from '$lib/settingsTabs';
	import Sidebar from '$lib/components/ui/sidebar/Sidebar.svelte';
	import SidebarEntry from '$lib/components/ui/sidebar/SidebarEntry.svelte';
	import SidebarGroup from '$lib/components/ui/sidebar/SidebarGroup.svelte';
	import Dreaming from './settings/Dreaming.svelte';
	import Account from './settings/Account.svelte';
	import General from './settings/General.svelte';
	import Hotkeys from './settings/Hotkeys.svelte';
	import Memory from './settings/Memory.svelte';
	import Mind from './settings/Mind.svelte';
	import Models from './settings/Models.svelte';
	import Permissions from './settings/Permissions.svelte';
	import Screen from './settings/Screen.svelte';
	import Servers from './settings/Servers.svelte';
	import Skills from './settings/Skills.svelte';
	import Usage from './settings/Usage.svelte';

	interface Props {
		onclose?: () => void;
		/** Which tab to land on. Defaults to the account — who this is for — but
		 * a caller opening this from, say, the composer's server sheet wants to land on the
		 * tab it was already talking about, not send a person back to the start. */
		tab?: Tab;
		/** The person chose another screen. The caller owns which one is showing, so a chord that
		 * asks for a screen — ⌘/ for the Hotkeys — moves a Settings that is already open. */
		ontab?: (tab: Tab) => void;
	}

	let { onclose, tab = 'account', ontab }: Props = $props();

	let query = $state('');

	const filter = $derived(query.trim().toLowerCase());
	const current = $derived(ENTRIES.find((entry) => entry.id === tab) ?? ENTRIES[0]);
</script>

<Modal
	label={t.settings.title}
	placement="centre"
	width="min(1180px, 94vw)"
	sheetclass="settings"
	{onclose}
>
	<div class="body">
		<Sidebar variant="settings" label={t.settings.title}>
			{#snippet head()}
				<div class="brand">
					<Ocellus size={22} />
					<span class="display title">{t.settings.title}</span>
				</div>
				<div class="search">
					<SearchBar
						value={query}
						placeholder={t.settings.search}
						onchange={(value) => (query = value)}
					/>
				</div>
			{/snippet}
			{#each GROUPS as group (group.label)}
				<SidebarGroup label={group.label} fixed>
					{#each group.entries as entry (entry.id)}
						<SidebarEntry
							icon={entry.icon}
							label={entry.label}
							active={tab === entry.id}
							meta={entry.soon ? t.settings.soon : undefined}
							onclick={() => ontab?.(entry.id)}
						/>
					{/each}
				</SidebarGroup>
			{/each}
		</Sidebar>

		<div class="panel">
			<!-- Keyed by the tab, so a new pane arrives on the theme's `settings.switch` fade rather
			     than replacing the old one in place. -->
			{#key tab}
				<div class="pane">
					<Screen title={current.label} blurb={current.blurb}>
						{#if tab === 'account'}
							<Account {filter} />
						{:else if tab === 'general'}
							<General {filter} />
						{:else if tab === 'hotkeys'}
							<Hotkeys {filter} />
						{:else if tab === 'usage'}
							<Usage />
						{:else if tab === 'models'}
							<Models {filter} />
						{:else if tab === 'memory'}
							<Memory {filter} />
						{:else if tab === 'dreaming'}
							<Dreaming />
						{:else if tab === 'mind'}
							<Mind {filter} />
						{:else if tab === 'skills'}
							<Skills {filter} />
						{:else if tab === 'servers'}
							<Servers {filter} />
						{:else}
							<Permissions {filter} />
						{/if}
					</Screen>
				</div>
			{/key}
		</div>
	</div>
</Modal>

<style>
	/* The one sheet with a height of its own: every tab holds a different amount, and a sheet
	   that resized itself around each one made switching between them the loudest thing on the
	   screen. The panel scrolls inside it instead. */
	.pane {
		animation: pane-in var(--motion-settings-switch);
	}

	@keyframes pane-in {
		from {
			opacity: 0;
		}
	}

	:global(.sheet.settings) {
		height: min(92vh, 860px);
	}

	/* The ground the sidebar floats on, as in the chat screen. */
	.body {
		display: flex;
		min-height: 0;
		flex: 1;
		border-radius: inherit;
		background: var(--ground);
	}

	.brand {
		display: flex;
		align-items: center;
		gap: calc(var(--sb-gap) - 2px);
		height: calc(var(--space) * 10);
		padding: 0 var(--sb-ir) 0 calc(var(--sb-ix) - 3px);
		margin-bottom: calc(var(--space) * 1);
	}

	.title {
		font-size: 21px;
		line-height: 1;
	}

	.search {
		margin: calc(var(--space) * 1.5) 0 calc(var(--space) * 1);
	}

	/* Right padding clears the floating close button, which sits over the panel's top corner. */
	.panel {
		flex: 1;
		min-width: 0;
		padding: 18px 44px 28px 28px;
		overflow-y: auto;
	}

	@media (max-width: 600px) {
		.body {
			flex-direction: column;
		}

		.panel {
			padding: 14px 16px 24px;
		}
	}
</style>
