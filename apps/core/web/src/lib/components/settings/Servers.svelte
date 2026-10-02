<script lang="ts">
	/**
	 * The MCP servers she can reach, and whether each one is running.
	 *
	 * The load is counted, not flagged, the same arrangement `ChatSession` uses: a load that has
	 * been overtaken has nothing to say about the screen somebody is looking at now, and a flag
	 * cannot tell two loads apart.
	 */
	import { api, type Server } from '$lib/api/client';
	import { t } from '$lib/i18n';
	import { Placeholder } from '$lib/loading.svelte';
	import Rows from './Rows.svelte';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	let servers = $state<Server[]>([]);
	let error = $state<string | null>(null);

	const visible = $derived(servers.filter((s) => !filter || s.name.toLowerCase().includes(filter)));

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
			const found = await api.servers();
			if (token !== generation) return;
			servers = found;
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
	{#each visible as server (server.name)}
		<section class="row">
			<div class="row-head">
				<h3>{server.name}</h3>
				<span class="caption" class:problem={!server.connected}>
					{server.connected ? t.settings.connected : t.settings.disconnected}
				</span>
			</div>
			<p class="caption">{t.settings.toolCount(server.tools)}</p>
			{#if server.failure}
				<p class="caption problem">{server.failure}</p>
			{/if}
		</section>
	{:else}
		<p class="empty">{filter ? t.settings.noMatch : t.settings.noServers}</p>
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

	.problem {
		color: var(--danger);
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
