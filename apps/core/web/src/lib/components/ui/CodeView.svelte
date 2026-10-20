<script lang="ts">
	/**
	 * Source, shown the way an editor shows it (the theme's code view, `.cv`, shared by the side
	 * view, the file editor and error details): a bar with the language in mono, an optional file
	 * name, an Edit switch when the source may be changed, and a copy button; then a sticky gutter of
	 * line numbers beside the code, coloured with the editor's own palette (`--vs-*`).
	 *
	 * The numbers are their own column rather than a counter on each line: highlighting wraps
	 * tokens in spans that may run across a newline, so the text cannot be cut into line elements
	 * without cutting them too. Both columns share one font and one line height, stated here, and a
	 * line never wraps — otherwise the two stop agreeing about where a line is (#171).
	 *
	 * Editing lays a transparent textarea exactly over the highlighted text, so what you type is
	 * drawn in the same colours as what was there; the frame takes a laurel hairline while it is.
	 */
	import { escape, highlight } from '$lib/highlight';
	import { t } from '$lib/i18n';
	import { toasts } from '$lib/toasts.svelte';
	import Checkbox from './Checkbox.svelte';
	import IconButton from './IconButton.svelte';

	interface Props {
		text: string;
		/** The file extension, without a dot: decides the grammar. */
		extension: string;
		/** What the bar says — "python", "Traceback". Defaults to the extension. */
		label?: string;
		name?: string;
		/** Offer the Edit switch. Changes come back through `onchange`. */
		editable?: boolean;
		editing?: boolean;
		/** A line over the code — why a diagram would not draw. */
		notice?: string;
		maxHeight?: string;
		/** Drop the bar: for a view whose own header already carries copy and the name. */
		bare?: boolean;
		onchange?: (text: string) => void;
		onediting?: (editing: boolean) => void;
	}

	let {
		text,
		extension,
		label,
		name,
		editable = false,
		editing = $bindable(false),
		notice,
		maxHeight,
		bare = false,
		onchange,
		onediting
	}: Props = $props();

	let lit = $state('');
	let copied = $state(false);
	let reset: ReturnType<typeof setTimeout> | undefined;

	$effect(() => {
		const source = text;
		lit = escape(source);
		let current = true;
		highlight(source, extension).then((html) => {
			if (current) lit = html;
		});
		return () => {
			current = false;
		};
	});

	/** `1\n2\n3…`, one per line; a final newline ends a line rather than starting one. */
	const numbers = $derived.by(() => {
		const count = text.replace(/\n$/, '').split('\n').length;
		return Array.from({ length: count }, (_, at) => at + 1).join('\n');
	});

	async function copy() {
		try {
			await navigator.clipboard.writeText(text);
		} catch {
			return;
		}
		copied = true;
		toasts.show(t.ui.copied);
		clearTimeout(reset);
		reset = setTimeout(() => (copied = false), 1400);
	}

	function tab(event: KeyboardEvent) {
		if (event.key !== 'Tab' || event.shiftKey) return;
		event.preventDefault();
		const area = event.currentTarget as HTMLTextAreaElement;
		const { selectionStart: start, selectionEnd: end } = area;
		area.setRangeText('    ', start, end, 'end');
		onchange?.(area.value);
	}
</script>

<div class="cv" class:editing style:max-height={maxHeight}>
	{#if !bare}
		<div class="bar">
			<span class="lang">{label ?? extension}</span>
			{#if name}<span class="name">{name}</span>{/if}
			<span class="space"></span>
			{#if editable}
				<Checkbox
					variant="switch"
					label={t.ui.edit}
					checked={editing}
					onchange={(on) => {
						editing = on;
						onediting?.(on);
					}}
				/>
			{/if}
			<IconButton
				icon={copied ? 'check' : 'copy'}
				on={copied}
				label={t.artifact.copyCode}
				onclick={copy}
			/>
		</div>
	{/if}
	{#if notice}<p class="notice">{notice}</p>{/if}
	<div class="body">
		<pre class="gutter" aria-hidden="true">{numbers}</pre>
		<div class="area">
			<!-- eslint-disable-next-line svelte/no-at-html-tags -- escaped in $lib/highlight -->
			<pre class="code"><code>{@html lit}</code></pre>
			{#if editable}
				<textarea
					class="input"
					class:live={editing}
					wrap="off"
					spellcheck="false"
					readonly={!editing}
					tabindex={editing ? 0 : -1}
					aria-label="{label ?? extension} source"
					value={text}
					oninput={(event) => onchange?.(event.currentTarget.value)}
					onkeydown={tab}></textarea>
			{/if}
		</div>
	</div>
</div>

<style>
	.cv {
		--cv-bg: var(--ground);
		display: flex;
		flex-direction: column;
		min-width: 0;
		min-height: 0;
		background: var(--cv-bg);
	}

	.editing {
		box-shadow: inset 0 0 0 var(--border-width) var(--laurel);
	}

	.bar {
		display: flex;
		flex: none;
		align-items: center;
		gap: 8px;
		min-height: 36px;
		padding: 4px 6px 4px 12px;
		border-bottom: var(--border-width) solid var(--line);
		color: var(--text-faint);
		font-size: 11.5px;
	}

	.lang {
		color: var(--text-muted);
		font: 500 11px var(--font-mono);
		letter-spacing: 0.03em;
	}

	.space {
		flex: 1;
	}

	.bar :global(.control) {
		color: var(--text-muted);
		font-size: 12px;
	}

	.notice {
		margin: 0;
		padding: 8px 12px 0;
		color: var(--danger);
		font-size: 12px;
	}

	.body {
		display: grid;
		flex: 1;
		grid-template-columns: auto minmax(0, 1fr);
		align-items: start;
		min-height: 0;
		overflow: auto;
		overscroll-behavior: contain;
	}

	pre {
		margin: 0;
		font: 12.5px/1.65 var(--font-mono);
		letter-spacing: 0;
		white-space: pre;
		tab-size: 4;
	}

	.gutter {
		position: sticky;
		left: 0;
		z-index: 1;
		align-self: stretch;
		min-width: 3.2em;
		padding: 12px 10px 12px 12px;
		border-right: var(--border-width) solid var(--line);
		background: var(--cv-bg);
		color: var(--vs-gutter);
		text-align: right;
		user-select: none;
	}

	.area {
		display: grid;
		min-width: 0;
	}

	.code,
	.input {
		grid-area: 1 / 1;
		padding: 12px 16px 12px 14px;
	}

	.code {
		color: var(--vs-fg);
		pointer-events: none;
	}

	.code code {
		font: inherit;
	}

	.input {
		width: 100%;
		min-height: 100%;
		margin: 0;
		overflow: hidden;
		border: 0;
		border-radius: 0;
		outline: 0;
		background: transparent;
		color: transparent;
		caret-color: transparent;
		font: 12.5px/1.65 var(--font-mono);
		white-space: pre;
		tab-size: 4;
		resize: none;
		pointer-events: none;
	}

	.input.live {
		caret-color: var(--text);
		pointer-events: auto;
	}

	.input::selection {
		background: var(--vs-selection);
		color: transparent;
	}
</style>
