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

	interface Props {
		/** The servers reported connected, in the order the tool layer listed them. */
		servers: Server[];
		onclose: () => void;
		onsettings: () => void;
	}

	let { servers, onclose, onsettings }: Props = $props();

	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') onclose();
	}
</script>

<svelte:window {onkeydown} />

<div
	class="scrim"
	role="button"
	tabindex="-1"
	aria-label={t.servers.close}
	onclick={onclose}
	onkeydown={(event) => event.key === 'Enter' && onclose()}
></div>

<div class="sheet" role="dialog" aria-modal="true" aria-label={t.servers.title}>
	<header>
		<div>
			<h2 class="display">{t.servers.title}</h2>
			<p class="caption">{t.servers.blurb}</p>
		</div>
		<button class="close" type="button" onclick={onclose}>
			<span class="sr-only">{t.servers.close}</span>
			<span aria-hidden="true">✕</span>
		</button>
	</header>

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
		inset: auto 50% 96px auto;
		transform: translateX(50%);
		width: min(380px, 92vw);
		max-height: 50vh;
		display: flex;
		flex-direction: column;
		padding: 16px 18px;
		background: var(--surface-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow);
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
		align-items: flex-start;
		justify-content: space-between;
		gap: 16px;
	}

	h2 {
		margin: 0;
		font-size: 18px;
	}

	header .caption {
		margin: 2px 0 0;
		max-width: 46ch;
	}

	.close {
		color: var(--text-muted);
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
