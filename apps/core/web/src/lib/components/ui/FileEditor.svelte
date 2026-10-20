<script lang="ts">
	/**
	 * One component for looking at and changing a file (the theme's `hera/file-editor`, open look):
	 * a header with the file's icon, name and what it is, its tools and download; the body on the
	 * ground; a footer for state and actions. No panel fill — header, body and footer sit on the
	 * ground with a hairline under the header — so it reads the same inline, in the side view and
	 * in a dialog.
	 *
	 * Kinds:
	 * - `image` — the picture on a checked ground, with zoom out / reset / in;
	 * - `source` — a `CodeView`;
	 * - `markdown` — Preview / Source, the preview typeset as her prose is;
	 * - `skill` — a SKILL.md: source with the Edit switch, and the caller's footer for trust state,
	 *   Revert and Save.
	 *
	 * PDF pages wait for a viewer library; nothing here pretends to draw one.
	 */
	import type { Snippet } from 'svelte';
	import type { IconName } from '$lib/icons';
	import { t } from '$lib/i18n';
	import Prose from '../Prose.svelte';
	import CloseButton from './CloseButton.svelte';
	import CodeView from './CodeView.svelte';
	import Icon from './Icon.svelte';
	import IconButton from './IconButton.svelte';
	import Segmented from './Segmented.svelte';

	interface Props {
		kind: 'image' | 'source' | 'markdown' | 'skill';
		name: string;
		/** What it is, under the name: "Python · 2.1 KB". */
		meta?: string;
		icon?: IconName;
		/** The text, for every kind but `image`. */
		text?: string;
		/** The grammar for `source`; `md` for the others. */
		extension?: string;
		/** The picture, for `image`. */
		src?: string;
		/** A download link, already resolved. */
		download?: string;
		editing?: boolean;
		onchange?: (text: string) => void;
		onediting?: (editing: boolean) => void;
		onclose?: () => void;
		/** Extra controls in the header, before download and close. */
		tools?: Snippet;
		footer?: Snippet;
	}

	let {
		kind,
		name,
		meta,
		icon,
		text = '',
		extension = 'md',
		src,
		download,
		editing = $bindable(false),
		onchange,
		onediting,
		onclose,
		tools,
		footer
	}: Props = $props();

	const ICON: Record<Props['kind'], IconName> = {
		image: 'image',
		source: 'code',
		markdown: 'book',
		skill: 'spark'
	};

	let zoom = $state(1);
	let tab = $state<'preview' | 'source'>('preview');

	function step(by: number) {
		zoom = by === 0 ? 1 : Math.min(4, Math.max(0.25, zoom + by));
	}
</script>

<div class="fe" data-kind={kind}>
	<header>
		<span class="icon"><Icon name={icon ?? ICON[kind]} /></span>
		<div class="title">
			<b>{name}</b>
			{#if meta}<small>{meta}</small>{/if}
		</div>
		<div class="tools">
			{#if kind === 'image'}
				<IconButton icon="minus" label={t.ui.zoomOut} onclick={() => step(-0.25)} />
				<button class="zoom" type="button" aria-label={t.ui.resetZoom} onclick={() => step(0)}>
					{Math.round(zoom * 100)}%
				</button>
				<IconButton icon="plus" label={t.ui.zoomIn} onclick={() => step(0.25)} />
			{:else if kind === 'markdown'}
				<Segmented
					size="sm"
					label={name}
					value={tab}
					options={[
						{ value: 'preview', label: t.ui.preview },
						{ value: 'source', label: t.ui.source }
					]}
					onchange={(next) => (tab = next)}
				/>
			{/if}
			{@render tools?.()}
			{#if download}
				<IconButton
					icon="download"
					label={t.ui.download}
					href={download}
					download={name}
					external
				/>
			{/if}
			{#if onclose}<CloseButton onclick={onclose} />{/if}
		</div>
	</header>

	<div class="body">
		{#if kind === 'image'}
			<div class="canvas">
				<img {src} alt={name} style:width="calc(min(100%, 560px) * {zoom})" />
			</div>
		{:else if kind === 'markdown' && tab === 'preview'}
			<div class="document"><Prose {text} /></div>
		{:else}
			<CodeView
				{text}
				extension={kind === 'skill' || kind === 'markdown' ? 'md' : extension}
				label={kind === 'skill' ? 'SKILL.md' : undefined}
				editable={kind === 'skill' && Boolean(onchange)}
				bind:editing
				{onchange}
				{onediting}
			/>
		{/if}
	</div>

	{#if footer}<footer>{@render footer()}</footer>{/if}
</div>

<style>
	.fe {
		display: flex;
		flex-direction: column;
		min-height: 0;
		height: 100%;
		overflow: hidden;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: transparent;
	}

	header {
		display: flex;
		flex: none;
		align-items: center;
		gap: 10px;
		min-height: 52px;
		padding: 8px 8px 8px 14px;
		border-bottom: var(--border-width) solid var(--line);
	}

	.icon {
		display: inline-grid;
		color: var(--text-muted);
	}

	.title {
		flex: 1;
		min-width: 0;
	}

	b,
	small {
		display: block;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	b {
		font-size: 13.5px;
		font-weight: 500;
	}

	small {
		color: var(--text-faint);
		font-size: 11.5px;
	}

	.tools {
		display: flex;
		flex: none;
		align-items: center;
		gap: 4px;
	}

	.zoom {
		min-width: 46px;
		padding: 4px;
		border-radius: 4px;
		color: var(--text-muted);
		font: 500 11.5px var(--font-mono);
		text-align: center;
	}

	.zoom:hover {
		background: var(--hover);
		color: var(--text);
	}

	.body {
		display: flex;
		flex: 1;
		flex-direction: column;
		min-height: 0;
		overflow: hidden;
		background: var(--ground);
	}

	.body > :global(.cv) {
		flex: 1;
	}

	.canvas {
		display: grid;
		flex: 1;
		place-items: center;
		padding: 24px;
		overflow: auto;
		background-color: var(--ground);
		background-image: conic-gradient(
			var(--hover) 25%,
			transparent 0 50%,
			var(--hover) 0 75%,
			transparent 0
		);
		background-size: 18px 18px;
	}

	.canvas img {
		max-width: none;
		transition: width var(--motion-modal-enter);
	}

	.document {
		flex: 1;
		padding: 18px 20px;
		overflow: auto;
	}

	.document :global(.prose) {
		max-width: var(--measure);
		font-size: 15px;
	}

	footer {
		display: flex;
		flex: none;
		align-items: center;
		gap: 8px;
		min-height: 40px;
		padding: 7px 10px 7px 14px;
		color: var(--text-faint);
		font: 10.5px var(--font-mono);
	}
</style>
