<script lang="ts">
	/**
	 * One artifact, drawn the way its extension says (ADR 13).
	 *
	 * The only component that fetches an artifact's content, used by the card in the transcript
	 * and by the drawer beside it — so *what a `.svg` looks like* is decided once. Content comes
	 * by name rather than in the event: a page never bloats a stored message, and an artifact has
	 * **one current state everywhere it appears**, so an edit in a later turn changes what an
	 * earlier card draws. `artifacts.version` is what tells this to look again.
	 *
	 * Five renderers and a fallback, and the three interesting ones are these:
	 *
	 * **`html` is a sandboxed frame and is not sanitised.** `allow-scripts` without
	 * `allow-same-origin` gives the frame an opaque origin, so a page she wrote cannot reach
	 * Hera's storage, cookies or DOM. That is why it may be a *page* rather than markup stripped
	 * until it is not one — stripping the script out of a page whose whole point is the script
	 * would look like Hera breaking her own output. It can still reach the network, which ADR 13
	 * writes down rather than leaves to be discovered: `sandbox` does not stop a frame loading a
	 * font, and a page without one looks broken in a way that reads as Hera being broken.
	 *
	 * **`svg` is drawn into this document, so it is sanitised** — `$lib/artifacts.sanitiseSvg`,
	 * the svg profile only, so a `<div>` or a frame smuggled into the markup is removed rather
	 * than rendered. A drawing is a picture; a page is a page, and it gets the frame.
	 *
	 * **`mermaid` is drawn into this document too, through the same sanitiser as `svg`** — it is
	 * a picture by the time it gets here, so it shares that branch's box and its rules. What it
	 * does not share is being ready: `$lib/mermaid` fetches the renderer on demand (issue #73),
	 * so a diagram has a *drawing it* state that a drawing she wrote herself does not, and a
	 * source that does not parse falls back to the same code figure `.mmd` used to get — with the
	 * mermaid error over it, because one bad line is the thing a person can fix.
	 */
	import { api, type ArtifactContent } from '$lib/api/client';
	import { extensionOf, hasSource, kindOf, sanitiseSvg, svgProblem } from '$lib/artifacts';
	import { escape, highlight } from '$lib/highlight';
	import { t } from '$lib/i18n';
	import { draw } from '$lib/mermaid';
	import { artifacts } from '$lib/stores/artifacts.svelte';
	import Copy from './Copy.svelte';
	import Prose from './Prose.svelte';

	interface Props {
		chatId: string;
		name: string;
		/** How tall the frame is allowed to be. The drawer gives it the room it has; a card in
		 * the transcript keeps it to something that does not push the answer off the screen. */
		height?: string;
		/** Show the code instead of the drawn thing. Only means something for a kind that has
		 * both — `hasSource` — and is ignored for the rest. */
		source?: boolean;
	}

	let { chatId, name, height = '420px', source = false }: Props = $props();

	/** The height a drawing is shrunk to fit, when the box has a fixed one — a card in the
	 * transcript. The drawer's `100%` is not a height to fit to: it scrolls what it cannot show. */
	const fit = $derived(height.endsWith('px') ? height : undefined);

	/** The two things a fetch is keyed on, and they are `$derived` for a reason worth keeping.
	 *
	 * A prop is read through a getter, so reading `name` inside an effect subscribes to whatever
	 * the *parent* read to produce it — and the parent here is a transcript that rebuilds
	 * `turn.blocks` from nothing on every token that arrives. `item.artifact` is a fresh object
	 * each time with the same filename in it, so "she said another word" reached this component
	 * as "your artifact changed": the content was refetched and a diagram redrawn from zero,
	 * forty times over a short answer. A `$derived` propagates only when the value really
	 * changed, which turns that back into *the file I am showing is a different file*.
	 */
	const wanted = $derived(name);
	const chat = $derived(chatId);

	let content = $state<ArtifactContent | null>(null);
	let failure = $state('');

	/** The drawn diagram, sanitised — `''` while the renderer is still being fetched. */
	let diagram = $state('');
	/** Why mermaid would not draw this one. Set means: show the source, with this over it. */
	let undrawable = $state('');

	const kind = $derived(kindOf(wanted));
	const asCode = $derived(source && hasSource(wanted));

	/** The source as HTML — plain and escaped at once, coloured when the grammar has arrived. */
	let lit = $state('');

	/** Whether the last press worked — the icon says so for a moment, then goes back. */
	let copied = $state(false);
	let reset: ReturnType<typeof setTimeout> | undefined;

	async function copy() {
		try {
			await navigator.clipboard.writeText(content?.text ?? '');
		} catch {
			return;
		}
		copied = true;
		clearTimeout(reset);
		reset = setTimeout(() => (copied = false), 1500);
	}
	/** `1\n2\n3…`, one per line of the file; a final newline ends a line rather than starting one. */
	const numbers = $derived.by(() => {
		const count = (content?.text ?? '').replace(/\n$/, '').split('\n').length;
		return Array.from({ length: count }, (_, at) => at + 1).join('\n');
	});

	$effect(() => {
		const text = content?.text ?? '';
		const extension = extensionOf(wanted);
		lit = escape(text);
		let current = true;
		highlight(text, extension).then((html) => {
			if (current) lit = html;
		});
		return () => {
			current = false;
		};
	});

	$effect(() => {
		// Re-runs when the file changes and when something published changed. `wanted` and `chat`
		// are read by the call itself; `version` is the one nothing else here reads. All three
		// are reads of state this effect does not write, which is what keeps it out of the loop
		// `status.md` records — nothing here assigns to `artifacts.version`.
		void artifacts.version;
		let current = true;
		content = null;
		failure = '';
		api
			.artifact(chat, wanted)
			.then((body) => {
				if (current) content = body;
			})
			.catch((cause) => {
				if (current) failure = cause instanceof Error ? cause.message : String(cause);
			});
		return () => {
			current = false;
		};
	});

	/** Tell the server this one would not draw. The person can see it — the source is on screen
	 * with the reason over it — and she cannot, which is why a syntax she keeps getting wrong
	 * stays wrong. Best effort: a report that did not arrive costs one more redraw. */
	function report(message: string) {
		void api.reportArtifactProblem(chat, wanted, message).catch(() => {});
	}

	// An SVG she wrote by hand can be broken too, and sanitising it would only hide that.
	$effect(() => {
		if (kind !== 'svg' || !content) return;
		const problem = svgProblem(content.text);
		if (problem) report(problem);
	});

	// Drawing is its own effect because it is its own wait: the content arrives over the API and
	// then the renderer arrives over the network, and only the second one can fail in a way a
	// person is meant to read. It reads `content` and `kind` and writes neither, which is what
	// keeps it clear of the `effect_update_depth_exceeded` shape `status.md` records three times.
	$effect(() => {
		const source = kind === 'mermaid' ? (content?.text ?? null) : null;
		diagram = '';
		undrawable = '';
		if (source === null) return;
		let current = true;
		draw(source)
			.then((drawn) => {
				if (current) diagram = drawn;
			})
			.catch((cause) => {
				// A mermaid parse error names the line. Anything else — the chunk failing to
				// load, say — is still worth putting on screen over the source, because the
				// source is what a person came to look at either way.
				if (!current) return;
				undrawable = cause instanceof Error ? cause.message : String(cause);
				report(undrawable);
			});
		return () => {
			current = false;
		};
	});
</script>

{#snippet lines()}
	<!-- The numbers are their own column rather than a counter on each line: highlighting wraps
	     tokens in spans that may run across a newline, so the text cannot be cut into line
	     elements without cutting them too. The price is that a line must not wrap, or the two
	     columns stop agreeing about where a line is — so this one scrolls sideways. -->
	<!-- Zero tall and sticky, so the button rides in the corner of the box while the code
	     scrolls under it, instead of scrolling away with the first line. -->
	<div class="corner">
		<button
			type="button"
			class="copy"
			title={copied ? t.artifact.copiedCode : t.artifact.copyCode}
			aria-label={t.artifact.copyCode}
			onclick={copy}
		>
			<Copy size={14} done={copied} />
		</button>
	</div>
	<div class="lines">
		<pre class="numbers mono" aria-hidden="true">{numbers}</pre>
		<!-- eslint-disable-next-line svelte/no-at-html-tags -- escaped in $lib/highlight -->
		<pre class="mono"><code>{@html lit}</code></pre>
	</div>
{/snippet}

{#if failure}
	<p class="failed">{failure}</p>
{:else if !content}
	<p class="waiting">{t.artifact.loading}</p>
{:else if asCode}
	<div class="source" style:max-height={height}>
		{@render lines()}
	</div>
{:else if kind === 'html'}
	<iframe title={wanted} class="frame" style:height sandbox="allow-scripts" srcdoc={content.text}
	></iframe>
{:else if kind === 'svg'}
	<div class="drawing" style:max-height={height} style:--fit={fit}>
		<!-- eslint-disable-next-line svelte/no-at-html-tags -- sanitised in $lib/artifacts -->
		{@html sanitiseSvg(content.text)}
	</div>
{:else if kind === 'markdown'}
	<div class="document" style:max-height={height}><Prose text={content.text} /></div>
{:else if kind === 'mermaid' && !undrawable && !diagram}
	<!-- Outside the box rather than inside it. The drawing's box is white whatever the theme is,
	     and a faint caption written for the page surface is not written for that — so while the
	     renderer is on its way this reads exactly like the line above it, and there is no empty
	     white strip standing in for a diagram that has not been laid out yet. -->
	<p class="waiting">{t.artifact.drawing}</p>
{:else if kind === 'mermaid' && !undrawable}
	<div class="drawing" style:max-height={height} style:--fit={fit}>
		<!-- eslint-disable-next-line svelte/no-at-html-tags -- sanitised in $lib/mermaid -->
		{@html diagram}
	</div>
{:else}
	<div class="source" style:max-height={height}>
		{#if undrawable}
			<p class="caption">{t.artifact.notDrawn(undrawable)}</p>
		{/if}
		{@render lines()}
	</div>
{/if}

<style>
	.frame {
		display: block;
		width: 100%;
		background: #fff;
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}

	.drawing,
	.document,
	.source {
		overflow: auto;
		overscroll-behavior: contain;
		border-radius: var(--radius);
	}

	/* A drawing sits on white whatever the theme is. An SVG she wrote has its own idea about
	   colour and very often assumes a light page; painting it onto a dark surface is how a
	   perfectly good chart turns into black lines on black.

	   **Deliberately not a flex container**, and that is the whole of a bug worth writing down.
	   An `<svg>` with `height: auto` is a flex item whose cross size is `auto`, so the default
	   `align-items: stretch` sets its height *from the box* instead of from its own aspect
	   ratio. With a `max-height` above it, a tall chart was squashed to the panel's height and
	   `preserveAspectRatio` then shrank the drawing to fit the width it no longer had — a
	   400 × 1400 flow chart came out as a thumbnail in an acre of white, which reads as an
	   artifact that came out broken rather than as a layout that is wrong. Centring with `auto`
	   margins costs nothing and leaves the drawing its own height, which is what the scroll on
	   this box is for.

	   A grid rather than a flex container for the same reason it is not a flex one: an auto
	   margin on a grid item absorbs the free space on both axes, so a drawing smaller than its
	   box sits in the middle of it — and one taller than the box falls back to the start and
	   scrolls, instead of being cut off above. */
	.drawing {
		display: grid;
		/* One column as wide as the box. An `auto` track is sized from the drawing, and an svg
		   whose width is a percentage has no size to offer, so the track collapsed to the
		   svg's default 300px and sat at the left of a box it did not fill. */
		grid-template-columns: minmax(0, 1fr);
		padding: 12px;
		background: #fff;
		border: 1px solid var(--line);
	}

	.drawing :global(svg) {
		display: block;
		margin: auto;
		max-width: 100%;
		height: auto;
		/* Under a fixed height, the drawing is scaled down to fit the box instead of running
		   past it: mermaid's svg is as wide as the box and as tall as its aspect ratio makes it,
		   so a wide chart overflowed and the box scrolled, with the picture pinned to one side.
		   `meet` then centres it in the room it has. 26px is the padding and the border. */
		max-height: calc(var(--fit, 100000px) - 26px);
	}

	/* A column, so the lines can be told to take whatever height the caption leaves — the gutter
	   then runs to the bottom of the box however short the file is. */
	.source {
		display: flex;
		flex-direction: column;
		background: var(--surface);
		border: 1px solid var(--line);
	}

	.corner {
		position: sticky;
		top: 0;
		left: 0;
		z-index: 1;
		display: flex;
		flex: none;
		justify-content: flex-end;
		height: 0;
	}

	.copy {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 27px;
		height: 27px;
		margin: 6px 8px 0 0;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		background: var(--surface);
		color: var(--text-faint);
		transition:
			color var(--fade) var(--ease),
			border-color var(--fade) var(--ease);
	}

	.copy:hover {
		color: var(--text);
		border-color: var(--brass);
	}

	.lines {
		display: grid;
		grid-template-columns: auto 1fr;
		flex: 1 0 auto;
	}

	/* Token colours are mixed with the page's own text colour, so they keep their contrast on
	   whichever theme is up instead of needing a second palette. Every source view shares them,
	   which is what `$lib/highlight` being reusable is for. */
	.source :global(.hljs-comment),
	.source :global(.hljs-quote) {
		color: var(--text-faint);
		font-style: italic;
	}

	.source :global(.hljs-keyword),
	.source :global(.hljs-selector-tag),
	.source :global(.hljs-literal),
	.source :global(.hljs-doctag) {
		color: color-mix(in srgb, #c678dd 70%, var(--text));
	}

	.source :global(.hljs-string),
	.source :global(.hljs-regexp),
	.source :global(.hljs-addition) {
		color: color-mix(in srgb, #7cb35b 70%, var(--text));
	}

	.source :global(.hljs-number),
	.source :global(.hljs-symbol),
	.source :global(.hljs-bullet),
	.source :global(.hljs-meta) {
		color: color-mix(in srgb, #d19a66 70%, var(--text));
	}

	.source :global(.hljs-title),
	.source :global(.hljs-function),
	.source :global(.hljs-section),
	.source :global(.hljs-name),
	.source :global(.hljs-selector-class),
	.source :global(.hljs-selector-id) {
		color: color-mix(in srgb, #61afef 70%, var(--text));
	}

	.source :global(.hljs-attr),
	.source :global(.hljs-attribute),
	.source :global(.hljs-variable),
	.source :global(.hljs-built_in),
	.source :global(.hljs-type),
	.source :global(.hljs-property) {
		color: color-mix(in srgb, #e5c07b 65%, var(--text));
	}

	.source :global(.hljs-deletion) {
		color: color-mix(in srgb, #e06c75 70%, var(--text));
	}

	.source :global(.hljs-emphasis) {
		font-style: italic;
	}

	.source :global(.hljs-strong) {
		font-weight: 600;
	}

	.source pre {
		margin: 0;
		padding: 10px 12px;
		white-space: pre;
	}

	/* Stretched by the grid to the full height of the box. Sticky, so it stays put while a long
	   line is scrolled sideways. */
	.source .numbers {
		position: sticky;
		left: 0;
		text-align: right;
		user-select: none;
		color: var(--text-faint);
		background: var(--surface);
		border-right: 1px solid var(--line);
	}

	.source .caption {
		margin: 0;
		padding: 8px 12px 0;
		color: var(--text-faint);
	}

	.waiting,
	.failed {
		margin: 0;
		font-size: 13px;
		color: var(--text-faint);
	}

	.failed {
		color: var(--danger);
	}
</style>
