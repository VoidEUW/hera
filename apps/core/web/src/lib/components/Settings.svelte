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
	import Input from './Input.svelte';
	import Modal from './Modal.svelte';
	import SettingsIcon, { type SettingsIconName } from './SettingsIcon.svelte';
	import Dreaming from './settings/Dreaming.svelte';
	import Account from './settings/Account.svelte';
	import General from './settings/General.svelte';
	import Memory from './settings/Memory.svelte';
	import Mind from './settings/Mind.svelte';
	import Models from './settings/Models.svelte';
	import Permissions from './settings/Permissions.svelte';
	import Screen from './settings/Screen.svelte';
	import Servers from './settings/Servers.svelte';
	import Skills from './settings/Skills.svelte';

	export type Tab =
		| 'account'
		| 'general'
		| 'models'
		| 'skills'
		| 'servers'
		| 'permissions'
		| 'memory'
		| 'mind'
		| 'dreaming';

	interface Props {
		onclose?: () => void;
		/** Which tab to land on. Defaults to the account — who this is for — but
		 * a caller opening this from, say, the composer's server sheet wants to land on the
		 * tab it was already talking about, not send a person back to the start. */
		tab?: Tab;
	}

	let { onclose, tab: initialTab = 'account' }: Props = $props();

	interface Entry {
		id: Tab;
		label: string;
		blurb: string;
		icon: SettingsIconName;
		soon?: boolean;
	}

	const GROUPS: Array<{ label: string; entries: Entry[] }> = [
		{
			label: t.settings.groupApp,
			entries: [
				{
					id: 'account',
					label: t.settings.account,
					blurb: t.settings.blurbAccount,
					icon: 'account'
				},
				{
					id: 'general',
					label: t.settings.general,
					blurb: t.settings.blurbGeneral,
					icon: 'general'
				}
			]
		},
		{
			label: t.settings.groupHera,
			entries: [
				{ id: 'mind', label: t.settings.mind, blurb: t.settings.blurbMind, icon: 'mind' },
				{ id: 'memory', label: t.settings.memory, blurb: t.settings.blurbMemory, icon: 'memory' },
				{ id: 'models', label: t.settings.models, blurb: t.settings.blurbModels, icon: 'models' },
				{
					id: 'dreaming',
					label: t.settings.dreaming,
					blurb: t.settings.blurbDreaming,
					icon: 'dreaming',
					soon: true
				}
			]
		},
		{
			label: t.settings.groupAdjust,
			entries: [
				{ id: 'skills', label: t.settings.skills, blurb: t.settings.blurbSkills, icon: 'skills' },
				{
					id: 'servers',
					label: t.settings.servers,
					blurb: t.settings.blurbServers,
					icon: 'servers'
				},
				{
					id: 'permissions',
					label: t.settings.permissions,
					blurb: t.settings.blurbPermissions,
					icon: 'permissions'
				}
			]
		}
	];

	const ENTRIES = GROUPS.flatMap((group) => group.entries);

	let tab = $state<Tab>(initialTab);
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
		<aside class="side">
			<label class="search">
				<span class="sr-only">{t.settings.search}</span>
				<Input
					kind="search"
					value={query}
					placeholder={t.settings.search}
					onchange={(value) => (query = value)}
				/>
			</label>

			<nav class="tabs">
				{#each GROUPS as group (group.label)}
					<div class="group">
						<p class="heading">{group.label}</p>
						{#each group.entries as entry (entry.id)}
							<button
								class="tab"
								class:active={tab === entry.id}
								type="button"
								onclick={() => (tab = entry.id)}
							>
								<SettingsIcon name={entry.icon} />
								{entry.label}
								{#if entry.soon}<span class="soon">{t.settings.soon}</span>{/if}
							</button>
						{/each}
					</div>
				{/each}
			</nav>
		</aside>

		<div class="panel">
			<Screen title={current.label} blurb={current.blurb}>
				{#if tab === 'account'}
					<Account {filter} />
				{:else if tab === 'general'}
					<General {filter} />
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
	</div>
</Modal>

<style>
	/* The one sheet with a height of its own: every tab holds a different amount, and a sheet
	   that resized itself around each one made switching between them the loudest thing on the
	   screen. The panel scrolls inside it instead. */
	:global(.sheet.settings) {
		height: min(92vh, 860px);
	}

	.body {
		display: flex;
		min-height: 0;
		flex: 1;
	}

	.side {
		display: flex;
		flex-direction: column;
		gap: 14px;
		width: 224px;
		flex: none;
		min-height: 0;
		padding: 14px 10px;
		border-right: 1px solid var(--line);
	}

	/* Level with the close button on the far side of the sheet. */
	.search {
		display: block;
	}

	.tabs {
		display: flex;
		flex-direction: column;
		gap: 16px;
		min-height: 0;
		overflow-y: auto;
	}

	.group {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.heading {
		margin: 0 0 4px;
		padding: 0 10px;
		font-size: 11.5px;
		letter-spacing: 0.04em;
		color: var(--text-faint);
	}

	.tab {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 7px 10px;
		border-radius: var(--radius);
		text-align: left;
		font-size: 13.5px;
		color: var(--text-muted);
	}

	.tab:hover {
		background: var(--surface);
		color: var(--text);
	}

	.tab.active {
		background: var(--surface);
		color: var(--text);
	}

	.soon {
		margin-left: auto;
		font-size: 10.5px;
		letter-spacing: 0.05em;
		color: var(--text-faint);
	}

	/* Right padding clears the floating close button, which sits over the panel's top corner. */
	.panel {
		flex: 1;
		min-width: 0;
		padding: 18px 44px 28px 28px;
		overflow-y: auto;
	}

	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
		border: 0;
	}

	@media (max-width: 640px) {
		.body {
			flex-direction: column;
		}

		.side {
			width: auto;
			border-right: 0;
			border-bottom: 1px solid var(--line);
			padding-right: 44px;
		}

		.tabs {
			flex-direction: row;
			gap: 4px;
			overflow-x: auto;
			overflow-y: hidden;
		}

		.group {
			flex-direction: row;
		}

		.heading {
			display: none;
		}

		.tab {
			white-space: nowrap;
		}

		.panel {
			padding: 14px 16px 24px;
		}
	}
</style>
