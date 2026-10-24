<script lang="ts">
	/**
	 * The MCP servers she can reach (#108): each one a box with its tools inside, hers first, and
	 * a way to add one, change one and remove one — which writes `mcp.json` and reconnects just
	 * that server.
	 *
	 * The load is counted, not flagged, the same arrangement `ChatSession` uses: a load that has
	 * been overtaken has nothing to say about the screen somebody is looking at now, and a flag
	 * cannot tell two loads apart.
	 */
	import { api, ApiError, type Server } from '$lib/api/client';
	import Button from '$lib/components/ui/Button.svelte';
	import Confirm from '$lib/components/ui/Confirm.svelte';
	import { t } from '$lib/i18n';
	import { Placeholder } from '$lib/loading.svelte';
	import { workspace } from '$lib/stores/workspace.svelte';
	import Rows from './Rows.svelte';
	import ServerBox from './ServerBox.svelte';
	import ServerEditor from './ServerEditor.svelte';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	let servers = $state<Server[]>([]);
	let error = $state<string | null>(null);
	/** The editor: a server being changed, `'new'`, or closed. */
	let editing = $state<Server | 'new' | null>(null);
	let deleting = $state<Server | null>(null);

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

	/** The composer's count and menu read the workspace's copy, not this one. */
	function changed() {
		void workspace.loadServers();
		void load();
	}

	function saved() {
		editing = null;
		changed();
	}

	async function remove() {
		const server = deleting;
		deleting = null;
		if (!server) return;
		try {
			await api.deleteServer(server.name);
		} catch (cause) {
			error = cause instanceof ApiError || cause instanceof Error ? cause.message : String(cause);
		}
		changed();
	}
</script>

{#if error}
	<p class="error" role="alert">{error}</p>
{/if}

{#if settling.shown}
	<Rows label={t.settings.loading} />
{:else}
	<div class="bar">
		<Button variant="highlighted" size="sm" icon="plus" onclick={() => (editing = 'new')}>
			{t.serverEditor.newServer}
		</Button>
	</div>

	{#each visible as server (server.name)}
		<ServerBox {server} onedit={() => (editing = server)} ondelete={() => (deleting = server)} />
	{:else}
		<p class="empty">{filter ? t.settings.noMatch : t.settings.noServers}</p>
	{/each}
{/if}

{#if editing}
	<ServerEditor
		name={editing === 'new' ? undefined : editing.name}
		onsaved={saved}
		onclose={() => (editing = null)}
	/>
{/if}

{#if deleting}
	<Confirm
		title={t.serverEditor.deleteTitle}
		body={t.serverEditor.deleteBody(deleting.name)}
		confirm={t.serverEditor.deleteYes}
		cancel={t.serverEditor.deleteKeep}
		onconfirm={remove}
		oncancel={() => (deleting = null)}
	/>
{/if}

<style>
	.bar {
		display: flex;
		justify-content: flex-end;
		padding-top: 14px;
		margin-bottom: 20px;
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
