<script lang="ts">
	/**
	 * The panel beside the transcript: one artifact full size, a download, and everything else
	 * this conversation published.
	 *
	 * This is the drawer M3 planned to build once for three panels (`docs/versions/v0.2.0.md`),
	 * arriving a milestone early because artifacts is the panel that needed it. Memory and the
	 * dream log are meant to fit this frame rather than each bringing their own, so what is
	 * artifact-specific here is deliberately only the body and the file bar.
	 *
	 * **A drawer rather than a modal**, for the reason Settings is a modal and this is not: you
	 * keep working with this open — reading the page, asking for a change, watching it change.
	 * So it takes width from the conversation instead of covering it, and there is no scrim.
	 *
	 * The **file bar** is what makes an artifact reachable after the turn that made it has
	 * scrolled away. Without it, `artifact_edit` in turn nine leaves you scrolling back to turn
	 * four to find the card that opens the file it just changed.
	 */
	import { api, type ArtifactSummary } from '$lib/api/client';
	import { downloadUrl, size, titleOf } from '$lib/artifacts';
	import { t } from '$lib/i18n';
	import { artifacts } from '$lib/stores/artifacts.svelte';
	import ArtifactView from './ArtifactView.svelte';
	import Stele from './Stele.svelte';
	import Tray from './Tray.svelte';

	interface Props {
		chatId: string;
	}

	let { chatId }: Props = $props();

	let listed = $state<ArtifactSummary[]>([]);
	let failure = $state('');

	const chosen = $derived(artifacts.name);

	$effect(() => {
		// The listing is re-read when something published changes, so a file created in the turn
		// you are watching appears in the bar without a reload.
		void artifacts.version;
		const chat = chatId;
		let current = true;
		api
			.artifacts(chat)
			.then((found) => {
				if (current) listed = found;
			})
			.catch((cause) => {
				if (current) failure = cause instanceof Error ? cause.message : String(cause);
			});
		return () => {
			current = false;
		};
	});
</script>

<aside class="drawer" aria-label={t.artifact.panel}>
	<header class="top">
		<span class="mark" aria-hidden="true"><Stele size={14} /></span>
		<h2 class="title">{chosen ? titleOf(chosen) : t.artifact.panel}</h2>
		{#if chosen}
			<!-- A plain link, not a fetch and a blob: the browser knows how to save a file, and the
			     response says `attachment` with a neutral media type, so a page she wrote is never
			     a document rendered at Hera's own origin. -->
			<a class="action save" href={downloadUrl(chatId, chosen)} download={chosen} rel="external">
				<Tray size={13} />
				{t.artifact.download}
			</a>
		{/if}
		<button class="action" type="button" onclick={() => artifacts.close()}>
			{t.artifact.close}
		</button>
	</header>

	<div class="body">
		{#if chosen}
			{#key chosen}
				<ArtifactView {chatId} name={chosen} height="100%" />
			{/key}
		{:else if failure}
			<p class="failed">{failure}</p>
		{:else}
			<p class="empty">{t.artifact.none}</p>
		{/if}
	</div>

	{#if listed.length}
		<nav class="files" aria-label={t.artifact.files}>
			<ul>
				{#each listed as file (file.name)}
					<li>
						<button
							type="button"
							class:current={file.name === chosen}
							onclick={() => artifacts.show(chatId, file.name)}
						>
							<span class="name">{file.name}</span>
							<span class="bytes">{size(file.bytes)}</span>
						</button>
					</li>
				{/each}
			</ul>
		</nav>
	{/if}
</aside>

<style>
	.drawer {
		display: flex;
		flex-direction: column;
		width: min(46vw, 720px);
		flex: none;
		border-left: 1px solid var(--line);
		background: var(--ground);
	}

	.top {
		display: flex;
		align-items: center;
		gap: 8px;
		flex: none;
		padding: 12px 14px;
		border-bottom: 1px solid var(--line);
	}

	/* Beside the transcript at 46vw of a phone width is not a panel, it is the whole screen with
	   the conversation squeezed into a sliver beside it — so below the shared breakpoint this
	   goes full-bleed instead. Still no scrim: `artifacts.close()` above is already the way out,
	   and a full-bleed sheet leaves nothing peeking out from behind it for a scrim to dim. */
	@media (max-width: 780px) {
		.drawer {
			position: fixed;
			inset: 0;
			width: 100%;
			z-index: 12;
			border-left: 0;
		}

		.top {
			padding-top: max(12px, env(safe-area-inset-top));
		}
	}

	.mark {
		display: flex;
	}

	/* The gap belongs after the title, not before the first control. `:first-of-type` counts per
	   element, so an `<a>` and a `<button>` in this row were each the first of theirs and both
	   took the space — which put a hole between Download and Close. */
	.title {
		margin: 0 auto 0 0;
		font-family: var(--font-display);
		font-size: 15px;
		font-weight: 500;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.action {
		flex: none;
		padding: 4px 9px;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 12.5px;
		color: var(--text-muted);
		text-decoration: none;
		transition:
			color var(--fade) var(--ease),
			border-color var(--fade) var(--ease);
	}

	.action:hover {
		color: var(--text);
		border-color: var(--brass);
	}

	/* The same glyph the card carries, so *save this* is one mark wherever it appears. */
	.save {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	/* The body owns the height it is given, so an HTML artifact's frame fills the panel rather
	   than being a fixed box inside a taller one. */
	.body {
		flex: 1;
		min-height: 0;
		padding: 14px;
		display: flex;
		flex-direction: column;
	}

	.body :global(.frame) {
		flex: 1;
		min-height: 0;
	}

	.files {
		flex: none;
		max-height: 24vh;
		overflow: auto;
		border-top: 1px solid var(--line);
	}

	.files ul {
		margin: 0;
		padding: 6px;
		list-style: none;
	}

	.files button {
		display: flex;
		align-items: baseline;
		gap: 10px;
		width: 100%;
		padding: 5px 8px;
		border-radius: var(--radius);
		font-size: 12.5px;
		color: var(--text-muted);
		text-align: left;
	}

	.files button:hover {
		background: var(--surface);
		color: var(--text);
	}

	.files button.current {
		color: var(--text);
		background: var(--surface-raised);
	}

	.name {
		font-family: var(--font-mono);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.bytes {
		margin-left: auto;
		flex: none;
		color: var(--text-faint);
	}

	.empty,
	.failed {
		margin: 0;
		font-size: 13px;
		color: var(--text-faint);
	}

	.failed {
		color: var(--danger);
	}
</style>
