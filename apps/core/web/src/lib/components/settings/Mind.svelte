<script lang="ts">
	/**
	 * Her mind regions: the text that governs how she behaves, one editable region at a time.
	 *
	 * Fetches for itself and holds its own placeholder, like Memory and Skills. The load is
	 * counted rather than flagged — see `Servers.svelte`, which carries the longer note — though
	 * here the screen is mounted once per visit, so the count only matters if `load` is ever
	 * called twice while mounted.
	 */
	import Button from '$lib/components/ui/Button.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';
	import Textarea from '$lib/components/ui/Textarea.svelte';
	import { api, type Region } from '$lib/api/client';
	import { t } from '$lib/i18n';
	import { Placeholder } from '$lib/loading.svelte';
	import Rows from './Rows.svelte';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	let regions = $state<Region[]>([]);
	let drafts = $state<Record<string, string>>({});
	let savedRegion = $state<string | null>(null);
	let error = $state<string | null>(null);

	const visible = $derived(
		regions.filter(
			(r) => !filter || `${r.id} ${r.title} ${r.purpose} ${r.text}`.toLowerCase().includes(filter)
		)
	);

	/** Driven from `load` rather than from an `$effect` over a flag: against a server on this
	 * machine the flag would be set and cleared before effects next flush, and the placeholder
	 * would never be drawn. */
	const settling = new Placeholder(true);
	$effect(() => () => settling.stop());

	let generation = 0;

	$effect(() => {
		void load();
	});

	async function load() {
		const token = ++generation;
		error = null;
		settling.set(true);
		try {
			const found = await api.regions();
			if (token !== generation) return;
			regions = found;
			drafts = Object.fromEntries(found.map((region) => [region.id, region.text]));
		} catch (cause) {
			if (token !== generation) return;
			error = cause instanceof Error ? cause.message : String(cause);
		} finally {
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

{#if error}
	<p class="error">{error}</p>
{/if}

{#if settling.shown}
	<Rows label={t.settings.loading} />
{:else}
	{#each visible as region (region.id)}
		<section class="region">
			<div class="region-head">
				<h3>{region.title}</h3>
				<Pill tone={region.tier === 'owner_fixed' ? 'authority' : 'neutral'} dot={false}>
					{region.tier === 'owner_fixed' ? t.settings.ownerFixed : t.settings.evolvable}
				</Pill>
				<span class="caption generation">{t.settings.generation(region.generation)}</span>
			</div>
			<p class="caption purpose">{region.purpose}</p>
			<Textarea
				prose
				rows={4}
				ariaLabel={region.title}
				value={drafts[region.id] ?? ''}
				onchange={(value) => (drafts[region.id] = value)}
			/>
			<div class="region-foot">
				<Button
					variant="highlighted"
					size="sm"
					disabled={drafts[region.id] === region.text}
					onclick={() => saveRegion(region)}
				>
					{t.settings.save}
				</Button>
				{#if savedRegion === region.id}
					<Pill tone="live">{t.settings.saved}</Pill>
				{/if}
			</div>
		</section>
	{:else}
		<p class="empty">{t.settings.noMatch}</p>
	{/each}
{/if}

<style>
	h3 {
		margin: 0;
		font-size: 14px;
		font-weight: 500;
	}

	.region {
		padding: 14px 0;
		border-bottom: 1px solid var(--line);
	}

	.region-head {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.generation {
		margin-left: auto;
	}

	.purpose {
		margin: 4px 0 8px;
	}

	.region-foot {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-top: 8px;
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
</style>
