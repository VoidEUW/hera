<script lang="ts">
	/**
	 * Settings, as a modal.
	 *
	 * Somewhere you go and come back from, with the conversation still visible behind it. Left
	 * nav, content on the right.
	 *
	 * The four lists are all *renderings of state the server already reports* — a server row is
	 * `ToolRegistry.status()`, a skill row is what the loader found wrong with it. Nothing here
	 * computes whether something is connected or broken, because a settings screen that derives
	 * its own view of that is a settings screen that can be wrong.
	 */
	import {
		api,
		type BrokenSkill,
		type Region,
		type Rule,
		type Server,
		type Skill
	} from '$lib/api/client';
	import { t } from '$lib/i18n';
	import { theme, type Appearance } from '$lib/theme.svelte';

	interface Props {
		onclose?: () => void;
	}

	let { onclose }: Props = $props();

	type Tab = 'general' | 'mind' | 'skills' | 'servers' | 'permissions';

	const TABS: Array<{ id: Tab; label: string }> = [
		{ id: 'general', label: t.settings.general },
		{ id: 'mind', label: t.settings.mind },
		{ id: 'skills', label: t.settings.skills },
		{ id: 'servers', label: t.settings.servers },
		{ id: 'permissions', label: t.settings.permissions }
	];

	const APPEARANCES: Array<{ id: Appearance; label: string }> = [
		{ id: 'system', label: t.settings.system },
		{ id: 'light', label: t.settings.light },
		{ id: 'dark', label: t.settings.dark }
	];

	let tab = $state<Tab>('general');
	let regions = $state<Region[]>([]);
	let skills = $state<Skill[]>([]);
	let broken = $state<BrokenSkill[]>([]);
	let servers = $state<Server[]>([]);
	let rules = $state<Rule[]>([]);
	let fallback = $state('ask');
	let drafts = $state<Record<string, string>>({});
	let savedRegion = $state<string | null>(null);
	let error = $state<string | null>(null);

	$effect(() => {
		void load(tab);
	});

	async function load(which: Tab) {
		error = null;
		try {
			if (which === 'mind') {
				regions = await api.regions();
				drafts = Object.fromEntries(regions.map((region) => [region.id, region.text]));
			} else if (which === 'skills') {
				const found = await api.skills();
				skills = found.skills;
				broken = found.broken;
			} else if (which === 'servers') {
				servers = await api.servers();
			} else if (which === 'permissions') {
				const found = await api.permissions();
				rules = found.rules;
				fallback = found.fallback;
			}
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
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

	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') onclose?.();
	}
</script>

<svelte:window {onkeydown} />

<div
	class="scrim"
	role="button"
	tabindex="-1"
	aria-label={t.settings.close}
	onclick={() => onclose?.()}
	onkeydown={(event) => event.key === 'Enter' && onclose?.()}
></div>

<div class="sheet" role="dialog" aria-modal="true" aria-label={t.settings.title}>
	<header>
		<h2 class="display">{t.settings.title}</h2>
		<button class="close" type="button" onclick={() => onclose?.()}>
			<span class="sr-only">{t.settings.close}</span>
			<span aria-hidden="true">✕</span>
		</button>
	</header>

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
				</button>
			{/each}
		</nav>

		<div class="panel">
			{#if error}
				<p class="error">{error}</p>
			{/if}

			{#if tab === 'general'}
				<h3>{t.settings.appearance}</h3>
				<div class="segments">
					{#each APPEARANCES as option (option.id)}
						<button
							class="segment"
							class:active={theme.appearance === option.id}
							type="button"
							onclick={() => theme.set(option.id)}
						>
							{option.label}
						</button>
					{/each}
				</div>
			{:else if tab === 'mind'}
				{#each regions as region (region.id)}
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
				{/each}
			{:else if tab === 'skills'}
				{#each skills as skill (skill.id)}
					<section class="row">
						<div class="row-head">
							<h3>{skill.id}</h3>
							<span class="caption">
								{skill.hits ? t.settings.usedTimes(skill.hits) : t.settings.never}
							</span>
						</div>
						<p class="caption">{skill.description}</p>
						{#each skill.problems as problem (problem)}
							<p class="caption problem">{problem}</p>
						{/each}
					</section>
				{:else}
					<p class="empty">{t.settings.noSkills}</p>
				{/each}
				{#each broken as item (item.id)}
					<section class="row">
						<div class="row-head">
							<h3>{item.id}</h3>
							<span class="caption problem">{t.settings.broken}</span>
						</div>
						<p class="caption problem">{item.reason}</p>
					</section>
				{/each}
			{:else if tab === 'servers'}
				{#each servers as server (server.name)}
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
					<p class="empty">{t.settings.noServers}</p>
				{/each}
			{:else}
				<p class="caption">Anything not matched below: <strong>{fallback}</strong></p>
				{#each rules as rule (rule.pattern + (rule.profile ?? ''))}
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
					<p class="empty">{t.settings.noPermissions}</p>
				{/each}
			{/if}
		</div>
	</div>
</div>

<style>
	.scrim {
		position: fixed;
		inset: 0;
		background: rgb(0 0 0 / 0.45);
		border: 0;
		animation: fade var(--fade) var(--ease);
		z-index: 10;
	}

	.sheet {
		position: fixed;
		inset: 6vh 50% auto auto;
		transform: translateX(50%);
		width: min(880px, 92vw);
		max-height: 88vh;
		display: flex;
		flex-direction: column;
		background: var(--surface-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow);
		overflow: hidden;
		z-index: 11;
		animation: fade var(--fade) var(--ease);
	}

	@keyframes fade {
		from {
			opacity: 0;
		}
	}

	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 16px 20px;
		border-bottom: 1px solid var(--line);
	}

	h2 {
		margin: 0;
		font-size: 20px;
	}

	.close {
		color: var(--text-muted);
		font-size: 15px;
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
		width: 160px;
		flex: none;
		padding: 14px 10px;
		border-right: 1px solid var(--line);
	}

	.tab {
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

	.panel {
		flex: 1;
		min-width: 0;
		padding: 18px 22px 24px;
		overflow-y: auto;
	}

	h3 {
		margin: 0;
		font-size: 14px;
		font-weight: 500;
	}

	.segments {
		display: inline-flex;
		gap: 2px;
		margin-top: 10px;
		padding: 3px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}

	.segment {
		padding: 5px 14px;
		border-radius: 6px;
		font-size: 13px;
		color: var(--text-muted);
	}

	.segment.active {
		background: var(--surface-raised);
		color: var(--text);
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
		color: var(--peacock);
	}

	.problem {
		color: var(--danger);
	}

	.decision[data-decision='allow'] {
		color: var(--peacock);
	}
	.decision[data-decision='deny'] {
		color: var(--danger);
	}
	.decision[data-decision='ask'] {
		color: var(--brass);
	}

	.empty {
		margin: 18px 0;
		max-width: 56ch;
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
