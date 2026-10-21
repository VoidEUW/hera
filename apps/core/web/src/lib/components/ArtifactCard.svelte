<script lang="ts">
	/**
	 * What she published, where she published it (ADR 13).
	 *
	 * Two shapes, settled when the file was made. `artifact_create` asks the model which, because
	 * a page and a figure are the same call there and only the model knows which it meant;
	 * `diagram_create` does not ask — a diagram is drawn in the flow unless it explicitly said
	 * *beside*, which is the whole reason that is a separate tool.
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
	import Button from './ui/Button.svelte';
	import IconButton from './ui/IconButton.svelte';
	import Segmented from './ui/Segmented.svelte';
	import type { Artifact } from '$lib/api/events';
	import { downloadUrl, extensionOf, hasSource, kindOf, size, headingOf } from '$lib/artifacts';
	import { t } from '$lib/i18n';
	import { saveDiagram } from '$lib/mermaid';
	import { artifacts } from '$lib/stores/artifacts.svelte';
	import ArtifactView from './ArtifactView.svelte';
	import Icon from './ui/Icon.svelte';

	interface Props {
		chatId: string | null;
		artifact: Artifact;
	}

	let { chatId, artifact }: Props = $props();

	const title = $derived(headingOf(artifact.name));
	const extension = $derived(extensionOf(artifact.name).toUpperCase());
	const drawn = $derived(kindOf(artifact.name) === 'mermaid');
	/** Showing the code instead of the drawing, for this card only. */
	let source = $state(false);

	function open() {
		if (!chatId) return;
		// The same file again is not a way to lose an edit to it.
		if (artifacts.open && artifacts.name === artifact.name) artifacts.show(chatId, artifact.name);
		else artifacts.ask(() => artifacts.show(chatId, artifact.name));
	}
</script>

<figure class="artifact" class:inline={artifact.inline}>
	{#if artifact.inline && chatId}
		<!-- The figure first and its caption under it, which is the order a figure is read in.
		     Drawn at a height that leaves the answer on screen; the drawer is where it gets the
		     room. -->
		<ArtifactView {chatId} name={artifact.name} height="360px" {source} />
	{/if}

	<figcaption class="bar">
		<span class="mark" class:muted={artifact.inline}><Icon name="file" /></span>
		<span class="named">
			<span class="title">{title}</span>
			<span class="about">
				{#if extension}<span class="kind">{extension}</span><span aria-hidden="true">·</span>{/if}
				<span class="bytes">{size(artifact.bytes)}</span>
			</span>
		</span>
		{#if artifact.inline && chatId && hasSource(artifact.name)}
			<!-- Only where the thing itself is drawn here: a card that is just a strip has no
			     picture to swap for its code. -->
			<Segmented
				size="sm"
				label={t.artifact.view}
				value={source ? 'source' : 'preview'}
				options={[
					{ value: 'preview', label: t.ui.preview },
					{ value: 'source', label: t.ui.source }
				]}
				onchange={(next) => (source = next === 'source')}
			/>
		{/if}
		{#if chatId && drawn}
			<!-- A diagram is converted to the page that draws it on the way out (`$lib/mermaid`), so
			     this is a button, not the link the other files get. -->
			<IconButton
				icon="download"
				label={t.artifact.downloadDrawnOne(artifact.name)}
				onclick={() => saveDiagram(chatId, artifact.name)}
			/>
		{:else if chatId}
			<!-- A plain link at the download URL: the browser knows how to save a file, and the
			     response says `attachment` with a neutral media type, so a page she wrote is never a
			     document rendered at Hera's own origin. The name is in the label, so a screen reader
			     on the fourth card of a turn is told which file it would be saving. -->
			<IconButton
				icon="download"
				label={t.artifact.downloadOne(artifact.name)}
				href={downloadUrl(chatId, artifact.name)}
				download={artifact.name}
				external
			/>
		{/if}
		<Button
			size="sm"
			variant={artifact.inline ? 'ghost' : 'neutral'}
			onclick={open}
			disabled={!chatId}
		>
			{artifact.inline ? t.artifact.openFull : t.artifact.open}
		</Button>
	</figcaption>
</figure>

<style>
	.artifact {
		margin: calc(var(--space) * 3.5) 0;
		padding: 0;
		max-width: var(--measure);
		animation: arrive var(--motion-artifact-enter);
	}

	@keyframes arrive {
		from {
			opacity: 0;
		}
	}

	/* The card (the theme's `art.frame: card`, `art.rail: none`): a bordered surface you click.
	   An inline artifact does not get the border, because the thing above the caption is already
	   the object and boxing it twice reads as a frame around a frame. */
	.artifact:not(.inline) .bar {
		padding: 9px 10px 9px 14px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius);
		background: var(--surface);
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
		color: var(--text-muted);
	}

	.mark.muted {
		color: var(--text-faint);
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
		flex: none;
		gap: 5px;
		color: var(--text-faint);
		font-size: 11.5px;
		letter-spacing: 0.02em;
	}

	.kind {
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}
</style>
