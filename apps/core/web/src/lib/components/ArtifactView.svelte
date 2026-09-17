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
	import { kindOf, sanitiseSvg } from '$lib/artifacts';
	import { t } from '$lib/i18n';
	import { draw } from '$lib/mermaid';
	import { artifacts } from '$lib/stores/artifacts.svelte';
	import Prose from './Prose.svelte';

	interface Props {
		chatId: string;
		name: string;
		/** How tall the frame is allowed to be. The drawer gives it the room it has; a card in
		 * the transcript keeps it to something that does not push the answer off the screen. */
		height?: string;
	}

	let { chatId, name, height = '420px' }: Props = $props();

	let content = $state<ArtifactContent | null>(null);
	let failure = $state('');

	/** The drawn diagram, sanitised — `''` while the renderer is still being fetched. */
	let diagram = $state('');
	/** Why mermaid would not draw this one. Set means: show the source, with this over it. */
	let undrawable = $state('');

	const kind = $derived(kindOf(name));

	$effect(() => {
		// Re-runs when the name changes and when something published changed. Both are reads of
		// state this effect does not write, which is what keeps it out of the loop `status.md`
		// records — nothing here assigns to `artifacts.version`.
		const wanted = name;
		const chat = chatId;
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
				if (current) undrawable = cause instanceof Error ? cause.message : String(cause);
			});
		return () => {
			current = false;
		};
	});
</script>

{#if failure}
	<p class="failed">{failure}</p>
{:else if !content}
	<p class="waiting">{t.artifact.loading}</p>
{:else if kind === 'html'}
	<iframe title={name} class="frame" style:height sandbox="allow-scripts" srcdoc={content.text}
	></iframe>
{:else if kind === 'svg'}
	<div class="drawing" style:max-height={height}>
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
	<div class="drawing" style:max-height={height}>
		<!-- eslint-disable-next-line svelte/no-at-html-tags -- sanitised in $lib/mermaid -->
		{@html diagram}
	</div>
{:else}
	<div class="source" style:max-height={height}>
		{#if undrawable}
			<p class="caption">{t.artifact.notDrawn(undrawable)}</p>
		{/if}
		<pre class="mono">{content.text}</pre>
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
	   this box is for. */
	.drawing {
		padding: 12px;
		background: #fff;
		border: 1px solid var(--line);
	}

	.drawing :global(svg) {
		display: block;
		margin: 0 auto;
		max-width: 100%;
		height: auto;
	}

	.source {
		background: var(--surface);
		border: 1px solid var(--line);
	}

	.source pre {
		margin: 0;
		padding: 10px 12px;
		white-space: pre-wrap;
		overflow-wrap: anywhere;
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
