<script lang="ts">
	/**
	 * One server as a box (#108): its mark, its name and whether it is running on the header, a
	 * wrench with how many tools it has, and the tools themselves once it is opened.
	 *
	 * Hers is a box like any other — she is a server (ADR 4) — marked with the ocellus rather than
	 * a letter, and without the controls that would edit or remove it, because it is not in
	 * `mcp.json`. Which boxes are open is kept in `servers` (`disclosure`), because Settings
	 * remounts a screen each time it is left.
	 */
	import type { Server } from '$lib/api/client';
	import Avatar from '$lib/components/ui/Avatar.svelte';
	import Collapsible from '$lib/components/ui/Collapsible.svelte';
	import Icon from '$lib/components/ui/Icon.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import Ocellus from '$lib/components/ui/Ocellus.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';
	import { servers as disclosure } from '$lib/disclosure.svelte';
	import { t } from '$lib/i18n';
	import ServerTools from './ServerTools.svelte';

	interface Props {
		server: Server;
		onedit: () => void;
		ondelete: () => void;
	}

	let { server, onedit, ondelete }: Props = $props();

	const open = $derived(disclosure.isOpen(server.name, false));
</script>

<div class="server">
	<Collapsible {open} lazy ontoggle={(next) => disclosure.set(server.name, next)}>
		{#snippet title()}
			<span class="named">
				{#if server.builtin}
					<Ocellus size={22} />
				{:else}
					<Avatar name={server.name} size={26} />
				{/if}
				{server.name}
			</span>
		{/snippet}
		{#snippet subtitle()}
			{#if server.builtin}
				{t.serverEditor.hers}
			{:else}
				{t.serverEditor[server.kind === 'http' ? 'http' : 'stdio']}
			{/if}
		{/snippet}
		{#snippet actions()}
			{#if !server.enabled}
				<Pill dot={false}>{t.serverEditor.off}</Pill>
			{:else}
				<Pill tone={server.connected ? 'live' : 'danger'}>
					{server.connected ? t.settings.connected : t.settings.disconnected}
				</Pill>
			{/if}
			<span class="count" title={t.settings.toolCount(server.tools)}>
				<Icon name="wrench" />{server.tools}
				<span class="sr">{t.settings.toolCount(server.tools)}</span>
			</span>
			{#if !server.builtin}
				<IconButton icon="edit" size="sm" label={t.serverEditor.edit} onclick={onedit} />
				<IconButton icon="trash" size="sm" label={t.serverEditor.delete} onclick={ondelete} />
			{/if}
		{/snippet}

		<div class="inside">
			{#if server.failure}<p class="caption problem">{server.failure}</p>{/if}
			{#if !server.enabled}
				<p class="caption">{t.serverEditor.switchOff}</p>
			{:else if !server.connected && server.tools === 0 && !server.builtin}
				<p class="caption">{t.serverEditor.notConnected}</p>
			{:else}
				<ServerTools server={server.name} />
			{/if}
		</div>
	</Collapsible>
</div>

<style>
	.server {
		margin-bottom: 12px;
	}

	.named {
		display: inline-flex;
		align-items: center;
		gap: 10px;
	}

	.count {
		display: inline-flex;
		align-items: center;
		gap: 4px;
		color: var(--text-muted);
		font-size: 13px;
	}

	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
	}

	.inside {
		display: flex;
		flex-direction: column;
	}

	.caption {
		margin: 0 0 8px;
	}

	.problem {
		color: var(--danger);
	}
</style>
