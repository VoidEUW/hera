<script lang="ts">
	/**
	 * Settings: **how she works**.
	 *
	 * Everything here changes her behaviour — what she runs on, who she is, what she knows, what
	 * she may do. Nothing here is about you or about this browser; that lives behind the profile
	 * card at the bottom of the rail, which is a different question and deserves a different
	 * door.
	 *
	 * The nav is ordered by what a person reaches for. **Models** first, because until she is
	 * pointed at an endpoint nothing else in Hera does anything. Then **Skills** and **Servers**,
	 * which are the two you come back to. **Dreaming** is listed and disabled rather than hidden:
	 * a v0.2 feature you can see coming is a promise, and one you cannot is a surprise.
	 *
	 * A modal, because settings is somewhere you go and come back from, and a modal keeps the
	 * conversation visible behind it.
	 */
	import { api, type Region, type Rule, type Server } from '$lib/api/client';
	import { t } from '$lib/i18n';
	import { Placeholder } from '$lib/loading.svelte';
	import Input from './Input.svelte';
	import Modal from './Modal.svelte';
	import Memory from './settings/Memory.svelte';
	import Models from './settings/Models.svelte';
	import Rows from './settings/Rows.svelte';
	import Skills from './settings/Skills.svelte';

	export type Tab =
		'models' | 'skills' | 'servers' | 'permissions' | 'memory' | 'mind' | 'dreaming';

	interface Props {
		onclose?: () => void;
		/** Which tab to land on. Defaults to models — the one nothing else works without — but
		 * a caller opening this from, say, the composer's server sheet wants to land on the
		 * tab it was already talking about, not send a person back to the start. */
		tab?: Tab;
	}

	let { onclose, tab: initialTab = 'models' }: Props = $props();

	const TABS: Array<{ id: Tab; label: string; soon?: boolean }> = [
		{ id: 'models', label: t.settings.models },
		{ id: 'skills', label: t.settings.skills },
		{ id: 'servers', label: t.settings.servers },
		{ id: 'permissions', label: t.settings.permissions },
		{ id: 'memory', label: t.settings.memory },
		{ id: 'mind', label: t.settings.mind },
		{ id: 'dreaming', label: t.settings.dreaming, soon: true }
	];

	let tab = $state<Tab>(initialTab);
	let query = $state('');

	let regions = $state<Region[]>([]);
	let servers = $state<Server[]>([]);
	let rules = $state<Rule[]>([]);
	let fallback = $state('ask');
	let drafts = $state<Record<string, string>>({});
	let savedRegion = $state<string | null>(null);
	let error = $state<string | null>(null);

	const filter = $derived(query.trim().toLowerCase());

	const visibleServers = $derived(
		servers.filter((s) => !filter || s.name.toLowerCase().includes(filter))
	);
	const visibleRules = $derived(
		rules.filter((r) => !filter || `${r.pattern} ${r.reason}`.toLowerCase().includes(filter))
	);
	const visibleRegions = $derived(
		regions.filter(
			(r) => !filter || `${r.id} ${r.title} ${r.purpose} ${r.text}`.toLowerCase().includes(filter)
		)
	);

	/** The three tabs this component fetches for itself. The other four are components of their
	 * own and each holds its own placeholder, on the same beat. */
	const FETCHES = new Set<Tab>(['mind', 'servers', 'permissions']);

	/** Driven from `load` rather than from an `$effect` over a `loading` flag.
	 *
	 * A flag would be set and cleared inside one async function, and against a server on this
	 * machine both can happen before effects next flush — so the effect would only ever see the
	 * `false` and the placeholder would never be drawn at all. Calling it where the load begins
	 * and ends has no such window. */
	const settling = new Placeholder(true);
	$effect(() => () => settling.stop());
	const waiting = $derived(settling.shown);

	/** Which load owns the panel, counted rather than named — the same arrangement `ChatSession`
	 * uses, and for the same reason. Switching tabs while a fetch is in flight leaves two of them
	 * running: without this the older one lands, hides the placeholder the newer one is still
	 * behind, and writes its answer into fields the newer one is about to fill. A tab id is not
	 * enough, because *mind → servers → mind* gives two loads the same name. */
	let generation = 0;

	$effect(() => {
		void load(tab);
	});

	async function load(which: Tab) {
		const token = ++generation;
		error = null;
		if (!FETCHES.has(which)) {
			settling.set(false);
			return;
		}
		settling.set(true);
		try {
			// Every assignment below is guarded, not just the last: a load that has been overtaken
			// has nothing to say about the screen somebody is looking at now.
			if (which === 'mind') {
				const found = await api.regions();
				if (token !== generation) return;
				regions = found;
				drafts = Object.fromEntries(found.map((region) => [region.id, region.text]));
			} else if (which === 'servers') {
				const found = await api.servers();
				if (token !== generation) return;
				servers = found;
			} else if (which === 'permissions') {
				const found = await api.permissions();
				if (token !== generation) return;
				rules = found.rules;
				fallback = found.fallback;
			}
		} catch (cause) {
			if (token !== generation) return;
			error = cause instanceof Error ? cause.message : String(cause);
		} finally {
			// The placeholder belongs to the newest load. An older one lifting it would uncover a
			// screen that has not been fetched yet.
			if (token === generation) settling.set(false);
		}
	}

	async function saveRegion(region: Region) {
		try {
			const updated = await api.writeRegion(region.id, drafts[region.id] ?? '');
			regions = regions.map((existing) => (existing.id === updated.id ? updated : existing));
			savedRegion = region.id;
			setTimeout(() => (savedRegion = null), 1600);
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		}
	}
</script>

<Modal
	label={t.settings.title}
	title={t.settings.title}
	caption={t.settings.subtitle}
	placement="centre"
	width="min(900px, 92vw)"
	sheetclass="settings"
	{onclose}
>
	<div class="body">
		<nav class="tabs">
			{#each TABS as entry (entry.id)}
				<button
					class="tab"
					class:active={tab === entry.id}
					type="button"
					onclick={() => (tab = entry.id)}
				>
					{entry.label}
					{#if entry.soon}<span class="soon">{t.settings.soon}</span>{/if}
				</button>
			{/each}
		</nav>

		<div class="panel">
			<label class="search">
				<span class="sr-only">{t.settings.search}</span>
				<Input
					kind="search"
					value={query}
					placeholder={t.settings.search}
					onchange={(value) => (query = value)}
				/>
			</label>

			{#if error}
				<p class="error">{error}</p>
			{/if}

			{#if waiting}
				<Rows label={t.settings.loading} />
			{:else if tab === 'models'}
				<Models {filter} />
			{:else if tab === 'memory'}
				<Memory {filter} />
			{:else if tab === 'dreaming'}
				<p class="empty">{t.settings.dreamingSoon}</p>
			{:else if tab === 'mind'}
				{#each visibleRegions as region (region.id)}
					<section class="region">
						<div class="region-head">
							<h3>{region.title}</h3>
							<span class="caption">
								{region.tier === 'owner_fixed' ? t.settings.ownerFixed : t.settings.evolvable}
								· {t.settings.generation(region.generation)}
							</span>
						</div>
						<p class="caption purpose">{region.purpose}</p>
						<textarea bind:value={drafts[region.id]} rows="4"></textarea>
						<div class="region-foot">
							<button
								class="save"
								type="button"
								disabled={drafts[region.id] === region.text}
								onclick={() => saveRegion(region)}
							>
								{t.settings.save}
							</button>
							{#if savedRegion === region.id}
								<span class="caption saved">{t.settings.saved}</span>
							{/if}
						</div>
					</section>
				{:else}
					<p class="empty">{t.settings.noMatch}</p>
				{/each}
			{:else if tab === 'skills'}
				<Skills {filter} />
			{:else if tab === 'servers'}
				{#each visibleServers as server (server.name)}
					<section class="row">
						<div class="row-head">
							<h3>{server.name}</h3>
							<span class="caption" class:problem={!server.connected}>
								{server.connected ? t.settings.connected : t.settings.disconnected}
							</span>
						</div>
						<p class="caption">
							{server.tools}
							{server.tools === 1 ? 'tool' : 'tools'}
						</p>
						{#if server.failure}
							<p class="caption problem">{server.failure}</p>
						{/if}
					</section>
				{:else}
					<p class="empty">{filter ? t.settings.noMatch : t.settings.noServers}</p>
				{/each}
			{:else}
				<p class="caption">Anything not matched below: <strong>{fallback}</strong></p>
				{#each visibleRules as rule (rule.pattern + (rule.profile ?? ''))}
					<section class="row">
						<div class="row-head">
							<h3 class="mono">{rule.pattern}</h3>
							<span class="caption decision" data-decision={rule.decision}>{rule.decision}</span>
						</div>
						{#if rule.reason}
							<p class="caption">{rule.reason}</p>
						{/if}
					</section>
				{:else}
					<p class="empty">{filter ? t.settings.noMatch : t.settings.noPermissions}</p>
				{/each}
			{/if}
		</div>
	</div>
</Modal>

<style>
	/* The one sheet with a height of its own: every tab holds a different amount, and a sheet
	   that resized itself around each one made switching between them the loudest thing on the
	   screen. The panel scrolls inside it instead. */
	:global(.sheet.settings) {
		height: min(88vh, 720px);
	}

	.body {
		display: flex;
		min-height: 0;
		flex: 1;
	}

	.tabs {
		display: flex;
		flex-direction: column;
		gap: 2px;
		width: 168px;
		flex: none;
		padding: 14px 10px;
		border-right: 1px solid var(--line);
	}

	.tab {
		display: flex;
		align-items: baseline;
		gap: 6px;
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

	.panel {
		flex: 1;
		min-width: 0;
		padding: 14px 22px 24px;
		overflow-y: auto;
	}

	.search {
		display: block;
		margin-bottom: 14px;
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

	h3 {
		margin: 0;
		font-size: 14px;
		font-weight: 500;
	}

	.region,
	.row {
		padding: 14px 0;
		border-bottom: 1px solid var(--line);
	}

	.region-head,
	.row-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 12px;
	}

	.purpose {
		margin: 4px 0 8px;
	}

	textarea {
		width: 100%;
		padding: 10px 12px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-family: var(--font-body);
		font-size: 15px;
		line-height: 1.55;
		resize: vertical;
	}

	.region-foot {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-top: 8px;
	}

	.save {
		padding: 5px 12px;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 13px;
		color: var(--text-muted);
	}

	.save:not(:disabled):hover {
		border-color: var(--brass);
		color: var(--brass);
	}

	.save:disabled {
		opacity: 0.4;
		cursor: default;
	}

	.saved {
		color: var(--laurel);
	}

	.problem {
		color: var(--danger);
	}

	.decision[data-decision='allow'] {
		color: var(--laurel);
	}
	.decision[data-decision='deny'] {
		color: var(--danger);
	}
	.decision[data-decision='ask'] {
		color: var(--brass);
	}

	.empty {
		margin: 18px 0;
		max-width: 60ch;
		font-family: var(--font-body);
		font-size: 15px;
		line-height: 1.6;
		color: var(--text-muted);
	}

	.error {
		margin: 0 0 14px;
		color: var(--danger);
		font-size: 13px;
	}

	@media (max-width: 640px) {
		.body {
			flex-direction: column;
		}

		.tabs {
			width: auto;
			flex-direction: row;
			overflow-x: auto;
			border-right: 0;
			border-bottom: 1px solid var(--line);
		}
	}
</style>
