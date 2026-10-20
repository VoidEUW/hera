<script lang="ts">
	/**
	 * What you do with the artifact that is open: look at its code, or take it with you.
	 *
	 * Lives in the header beside the selector rather than in the drawer, so everything that acts
	 * on *which file* is in one place. Ghost buttons — no frame — because they share a row with
	 * the selector's pill and the export tool, and a third kind of box there reads as clutter.
	 */
	import { downloadUrl, hasSource, kindOf } from '$lib/artifacts';
	import { t } from '$lib/i18n';
	import { saveDiagram } from '$lib/mermaid';
	import { artifacts } from '$lib/stores/artifacts.svelte';
	import Code from './Code.svelte';
	import Tray from './Tray.svelte';

	interface Props {
		chatId: string;
		name: string;
	}

	let { chatId, name }: Props = $props();
</script>

{#if hasSource(name)}
	<button
		class="tool"
		type="button"
		aria-pressed={artifacts.source}
		aria-label={artifacts.source ? t.artifact.showDrawnOf(name) : t.artifact.showSourceOf(name)}
		onclick={() => (artifacts.source = !artifacts.source)}
	>
		<Code size={14} />
		{artifacts.source ? t.artifact.showDrawn : t.artifact.showSource}
	</button>
{/if}

{#if kindOf(name) === 'mermaid'}
	<!-- A diagram is saved as the page that draws it rather than as its mermaid source, so this
	     one really is a fetch and a blob — the conversion needs a browser. `$lib/mermaid` is
	     where that is written down, and the card in the transcript calls the same function. -->
	<button
		class="tool"
		type="button"
		aria-label={t.artifact.downloadDrawnOne(name)}
		title={t.artifact.downloadDrawn}
		onclick={() => saveDiagram(chatId, name)}
	>
		<Tray size={14} />
		{t.artifact.download}
	</button>
{:else}
	<!-- A plain link, not a fetch and a blob: the browser knows how to save a file, and the
	     response says `attachment` with a neutral media type, so a page she wrote is never a
	     document rendered at Hera's own origin. -->
	<a
		class="tool"
		href={downloadUrl(chatId, name)}
		download={name}
		rel="external"
		aria-label={t.artifact.downloadOne(name)}
	>
		<Tray size={14} />
		{t.artifact.download}
	</a>
{/if}

<style>
	.tool {
		display: flex;
		align-items: center;
		gap: 6px;
		flex: none;
		padding: 4px 8px;
		border-radius: var(--radius);
		font-size: 12.5px;
		color: var(--text-muted);
		text-decoration: none;
		transition:
			color var(--fade) var(--ease),
			background var(--fade) var(--ease);
	}

	.tool:hover,
	.tool:focus-visible,
	.tool[aria-pressed='true'] {
		color: var(--brass);
		background: var(--surface);
		outline: none;
	}
</style>
