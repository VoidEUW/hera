<script lang="ts">
	/**
	 * What she may do without asking: the rules, and what happens to anything they do not match.
	 *
	 * Counted load, as in `Servers.svelte`.
	 */
	import { api, type Rule } from '$lib/api/client';
	import { t } from '$lib/i18n';
	import { Placeholder } from '$lib/loading.svelte';
	import Rows from './Rows.svelte';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	let rules = $state<Rule[]>([]);
	let fallback = $state('ask');
	let error = $state<string | null>(null);

	const visible = $derived(
		rules.filter((r) => !filter || `${r.pattern} ${r.reason}`.toLowerCase().includes(filter))
	);

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
			const found = await api.permissions();
			if (token !== generation) return;
			rules = found.rules;
			fallback = found.fallback;
		} catch (cause) {
			if (token !== generation) return;
			error = cause instanceof Error ? cause.message : String(cause);
		} finally {
			if (token === generation) settling.set(false);
		}
	}
</script>

{#if error}
	<p class="error">{error}</p>
{/if}

{#if settling.shown}
	<Rows label={t.settings.loading} />
{:else}
	<p class="caption">{t.settings.permissionsFallback} <strong>{fallback}</strong></p>
	{#each visible as rule (rule.pattern + (rule.profile ?? ''))}
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

<style>
	h3 {
		margin: 0;
		font-size: 14px;
		font-weight: 500;
	}

	.row {
		padding: 14px 0;
		border-bottom: 1px solid var(--line);
	}

	.row-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 12px;
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
</style>
