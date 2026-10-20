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
	import { t } from '$lib/i18n';
	import { draw } from '$lib/mermaid';
	import { artifacts } from '$lib/stores/artifacts.svelte';
	import CodeView from './ui/CodeView.svelte';
	import Spinner from './ui/Spinner.svelte';
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
		/** Inside the side view, whose header already carries the name, copy and download: the
		 * code view drops its own bar. */
		bare?: boolean;
	}

	let { chatId, name, height = '420px', source = false, bare = false }: Props = $props();

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
	<div class="code" class:bare style:max-height={height}>
		<CodeView
			text={content?.text ?? ''}
			extension={extensionOf(wanted)}
			name={bare ? undefined : wanted}
			notice={undrawable ? t.artifact.notDrawn(undrawable) : undefined}
			{bare}
		/>
	</div>
{/snippet}

{#if failure}
	<p class="failed">{failure}</p>
{:else if !content}
	<p class="waiting"><Spinner size={16} label={t.artifact.loading} /></p>
{:else if asCode}
	{@render lines()}
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
	<p class="waiting"><Spinner size={16} label={t.artifact.drawing} /></p>
{:else if kind === 'mermaid' && !undrawable}
	<div class="drawing" style:max-height={height} style:--fit={fit}>
		<!-- eslint-disable-next-line svelte/no-at-html-tags -- sanitised in $lib/mermaid -->
		{@html diagram}
	</div>
{:else}
	{@render lines()}
{/if}

<style>
	.frame {
		display: block;
		width: 100%;
		background: var(--canvas);
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius);
	}

	.drawing,
	.document {
		overflow: auto;
		overscroll-behavior: contain;
		border-radius: var(--radius);
	}

	/* A published document is read, so it gets the room a page has: padding off the frame and
	   the reading measure, instead of prose flush against the drawer's edge (#158). */
	.document {
		padding: calc(var(--space) * 5) calc(var(--space) * 6);
	}

	.document :global(.prose) {
		max-width: var(--measure);
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
		background: var(--canvas);
		border: var(--border-width) solid var(--line);
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

	/* Source in a card gets the card's frame; in the side view it runs to the panel's edges. */
	.code {
		display: flex;
		flex-direction: column;
		overflow: hidden;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
	}

	.code > :global(.cv) {
		flex: 1;
		min-height: 0;
	}

	.code.bare {
		border: 0;
		border-radius: 0;
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
