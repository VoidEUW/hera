<script lang="ts">
	/**
	 * Which servers are connected *now*, as a quick sheet beside the composer.
	 *
	 * A read-only mirror of `GET /servers`: the composer pill answers "what can she reach
	 * this turn", so it counts *connected* servers and nothing else — one that failed to
	 * start is configured but changes nothing for the next message. Adding or removing
	 * servers is deliberately not here: that is Settings → Servers, where the writing surface
	 * and its validation live, and this sheet hands off to it rather than duplicating it.
	 */
	import type { Server } from '$lib/api/client';
	import { t } from '$lib/i18n';
	import Modal from './Modal.svelte';

	interface Props {
		/** The servers reported connected, in the order the tool layer listed them. */
		servers: Server[];
		onclose: () => void;
		onsettings: () => void;
	}

	let { servers, onclose, onsettings }: Props = $props();
</script>

<Modal
	label={t.servers.title}
	title={t.servers.title}
	caption={t.servers.blurb}
	placement="docked"
	sheetclass="server-sheet"
	width="min(380px, 92vw)"
	{onclose}
>
	<ul class="list">
		{#each servers as server (server.name)}
			<li class="row">
				<span class="mark" aria-hidden="true">●</span>
				<span class="what">
					<span class="id">{server.name}</span>
					<span class="caption about">
						{server.tools}
						{server.tools === 1 ? t.servers.toolSingular : t.servers.toolPlural}
					</span>
				</span>
			</li>
		{:else}
			<li class="empty caption">{t.servers.none}</li>
		{/each}
	</ul>

	<button class="configure" type="button" onclick={onsettings}>{t.servers.configure}</button>
</Modal>

<style>
	/* The sheet's own padding: the header's is horizontal, the list's is vertical, and
	   this fills the rest. Scoped to this sheet alone — the skill picker pads its own. */
	:global(.sheet.server-sheet) {
		padding: 0 18px 16px;
	}
	.list {
		list-style: none;
		margin: 10px 0 0;
		padding: 0;
		overflow-y: auto;
	}

	.row {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		padding: 8px 0;
		border-bottom: 1px solid var(--line);
	}

	.row:last-child {
		border-bottom: 0;
	}

	.mark {
		flex: none;
		padding-top: 4px;
		font-size: 8px;
		color: var(--laurel);
	}

	.what {
		min-width: 0;
	}

	.id {
		display: block;
		font-size: 13.5px;
		color: var(--text-muted);
	}

	.about {
		display: block;
	}

	.empty {
		padding: 12px 8px;
		color: var(--text-muted);
	}

	.configure {
		align-self: flex-start;
		margin-top: 12px;
		color: var(--brass);
		font-size: 13px;
	}

	.configure:hover {
		text-decoration: underline;
	}
</style>
