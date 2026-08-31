<script lang="ts">
	/**
	 * What she published, where she published it (ADR 13).
	 *
	 * Two shapes, and the model chose which when it made the file — because it is the only thing
	 * that knows which of them it meant:
	 *
	 * - **`inline: false`** is a card: the stele, the filename humanised, the extension, and an
	 *   **Open**. Right for a page or a document — something you go and look at, beside the
	 *   conversation rather than inside it.
	 * - **`inline: true`** draws the thing itself, here, in the flow of the answer. Right for a
	 *   diagram that explains the paragraph above it, which is not something you go and open
	 *   later; by then the sentence it belonged to has scrolled away.
	 *
	 * Both open the drawer, because even a figure drawn in the flow is a file you may want full
	 * size or on disk. What the two decide is where the *thing* is, not whether it can be
	 * reached.
	 *
	 * The heading is the filename humanised and there is no title field to compete with it — the
	 * author chose those words, and a browser second-guessing them is how one screen disagrees
	 * with the next.
	 */
	import type { Artifact } from '$lib/api/events';
	import { downloadUrl, extensionOf, size, titleOf } from '$lib/artifacts';
	import { t } from '$lib/i18n';
	import { artifacts } from '$lib/stores/artifacts.svelte';
	import ArtifactView from './ArtifactView.svelte';
	import Stele from './Stele.svelte';
	import Tray from './Tray.svelte';

	interface Props {
		chatId: string | null;
		artifact: Artifact;
	}

	let { chatId, artifact }: Props = $props();

	const title = $derived(titleOf(artifact.name));
	const extension = $derived(extensionOf(artifact.name).toUpperCase());

	function open() {
		if (chatId) artifacts.show(chatId, artifact.name);
	}
</script>

<figure class="artifact" class:inline={artifact.inline}>
	{#if artifact.inline && chatId}
		<!-- The figure first and its caption under it, which is the order a figure is read in.
		     Drawn at a height that leaves the answer on screen; the drawer is where it gets the
		     room. -->
		<ArtifactView {chatId} name={artifact.name} height="360px" />
	{/if}

	<figcaption class="bar">
		<span class="mark" aria-hidden="true"><Stele size={14} muted={artifact.inline} /></span>
		<span class="named">
			<span class="title">{title}</span>
			<span class="about">
				{#if extension}<span class="kind">{extension}</span>{/if}
				<span class="bytes">{size(artifact.bytes)}</span>
			</span>
		</span>
		{#if chatId}
			<!-- Saving it is the other thing anybody does with a published file, and until now it
			     meant opening the drawer to find the link. A plain `<a download>` at the download
			     URL, the same one the drawer uses: the browser knows how to save a file, and the
			     response says `attachment` with a neutral media type, so a page she wrote is never
			     a document rendered at Hera's own origin.

			     A glyph and no word, because the row already carries three pieces of text and the
			     name is the one that has to stay legible when it is long. The name is in the label
			     rather than just *Download*, so a screen reader on the fourth card of a turn is
			     told which file it would be saving. -->
			<a
				class="save"
				href={downloadUrl(chatId, artifact.name)}
				download={artifact.name}
				title={t.artifact.download}
				aria-label={t.artifact.downloadOne(artifact.name)}
			>
				<Tray size={14} />
			</a>
		{/if}
		<button type="button" class="open" onclick={open} disabled={!chatId}>
			{artifact.inline ? t.artifact.openFull : t.artifact.open}
		</button>
	</figcaption>
</figure>

<style>
	.artifact {
		margin: 14px 0;
		padding: 0;
		max-width: var(--measure);
	}

	/* The card shape: a bordered strip you click. An inline artifact does not get the border,
	   because the thing above the caption is already the object and boxing it twice reads as a
	   frame around a frame. */
	.artifact:not(.inline) .bar {
		padding: 11px 12px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-left: 3px solid var(--brass);
		border-radius: var(--radius);
	}

	.bar {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.artifact.inline .bar {
		padding: 6px 2px 0;
	}

	.mark {
		display: flex;
		flex: none;
		align-items: center;
	}

	/* The gap between the name and the controls, rather than `margin-left: auto` on the last one
	   — there are two controls now and only one of them is always there. */
	.named {
		display: flex;
		align-items: baseline;
		gap: 8px;
		min-width: 0;
		margin-right: auto;
	}

	.title {
		font-family: var(--font-body);
		font-size: 15px;
		color: var(--text);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.artifact.inline .title {
		font-size: 13px;
		color: var(--text-muted);
	}

	.about {
		display: flex;
		gap: 8px;
		flex: none;
		font-size: 12px;
		color: var(--text-faint);
	}

	.kind {
		letter-spacing: 0.04em;
	}

	/* Square, so the glyph sits in the middle of a target the same height as the button beside
	   it. Faint until it is wanted: saving is the second thing you do with an artifact and it
	   should not compete with the first. */
	.save {
		display: flex;
		flex: none;
		align-items: center;
		justify-content: center;
		width: 27px;
		height: 27px;
		border: 1px solid transparent;
		border-radius: var(--radius);
		color: var(--text-faint);
		transition:
			color var(--fade) var(--ease),
			border-color var(--fade) var(--ease);
	}

	.save:hover {
		color: var(--text);
		border-color: var(--brass);
	}

	.open {
		flex: none;
		padding: 4px 10px;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 12.5px;
		color: var(--text-muted);
		transition:
			color var(--fade) var(--ease),
			border-color var(--fade) var(--ease);
	}

	.open:hover:not(:disabled) {
		color: var(--text);
		border-color: var(--brass);
	}

	.artifact.inline .open {
		border-color: transparent;
		padding: 2px 6px;
		font-size: 12px;
	}

	.artifact.inline .save {
		width: 22px;
		height: 22px;
	}
</style>
