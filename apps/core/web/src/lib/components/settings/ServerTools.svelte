<script lang="ts">
	/**
	 * What one server offers, fetched when its box is opened (#108) — a list of twenty closed boxes
	 * asks nothing — and a box beside each tool.
	 *
	 * A toggle is a round trip, because the answer is not always the one asked for: checking a tool
	 * that a wider rule turns off writes an allow, and the row then shows what the server says, not
	 * what was clicked.
	 */
	import { api, ApiError, type ServerTool } from '$lib/api/client';
	import Skeleton from '$lib/components/ui/Skeleton.svelte';
	import { t } from '$lib/i18n';
	import ToolRow from './ToolRow.svelte';

	interface Props {
		server: string;
	}

	let { server }: Props = $props();

	let tools = $state<ServerTool[] | null>(null);
	let working = $state<string | null>(null);
	let error = $state<string | null>(null);

	const message = (cause: unknown) =>
		cause instanceof ApiError || cause instanceof Error ? cause.message : String(cause);

	$effect(() => {
		const name = server;
		let current = true;
		api
			.serverTools(name)
			.then((found) => {
				if (current) tools = found;
			})
			.catch((cause) => {
				if (current) error = message(cause);
			});
		return () => {
			current = false;
		};
	});

	async function set(tool: ServerTool, allowed: boolean) {
		working = tool.name;
		error = null;
		try {
			const now = await api.setToolAllowed(server, tool.local_name, allowed);
			tools = (tools ?? []).map((existing) => (existing.name === now.name ? now : existing));
		} catch (cause) {
			error = message(cause);
			tools = await api.serverTools(server).catch(() => tools);
		} finally {
			working = null;
		}
	}
</script>

{#if error}<p class="error" role="alert">{error}</p>{/if}

{#if tools === null && !error}
	<div role="status" aria-busy="true" aria-label={t.serverEditor.toolsLoading}>
		<Skeleton rows={2} />
	</div>
{:else if tools !== null}
	{#each tools as tool (tool.name)}
		<ToolRow {tool} busy={working === tool.name} onchange={(allowed) => set(tool, allowed)} />
	{:else}
		<p class="caption">{t.serverEditor.noTools}</p>
	{/each}
{/if}

<style>
	.error {
		margin: 0 0 8px;
		color: var(--danger);
		font-size: 13px;
	}
</style>
