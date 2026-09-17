/**
 * Mermaid, fetched only when there is a diagram to draw ([issue #73](https://github.com/VoidEUW/hera/issues/73)).
 *
 * A model that can describe a flow chart in six lines of mermaid very often cannot write the
 * same picture as SVG path data, so this is less a renderer than a second way to *ask* for a
 * drawing — one that is within reach of the models ADR 19 targets. That is the whole reason it
 * exists; drawing `.mmd` files that were already publishable is the smaller half.
 *
 * `mermaid` is two to three megabytes of browser dependency, which is why v0.2.0 shipped `.mmd`
 * as a source view and deferred the renderer rather than putting that in everybody's first load.
 * The whole of that decision is the `import('mermaid')` below: a dynamic import, so the bundler
 * splits the library into chunks of its own and nothing fetches them until an artifact whose
 * extension says `mermaid` is opened. A conversation that never publishes one never pays for it.
 *
 * Two rules travel with it, and both are about what comes back out:
 *
 * - **The output is sanitised, by the same function an `.svg` artifact goes through.** What
 *   mermaid draws is derived from text a *model* wrote, and it lands in this document through
 *   `{@html}` — so `sanitiseSvg` applies for exactly the reason `$lib/artifacts` gives for the
 *   svg branch: what goes into the page is a picture, and it must not be able to be a document.
 * - **`htmlLabels` is off, and that is what makes the first rule survivable.** Mermaid's default
 *   puts every label in a `<foreignObject>` full of XHTML `<div>`s, which the svg-only profile
 *   strips — correctly, and catastrophically: the boxes and the arrows arrive with no text in
 *   them at all. Turning the option off makes a label a real `<text>` element, so the diagram
 *   and the sanitiser want the same thing instead of fighting over it. Widening the profile to
 *   `html` is the other way to make labels survive and it is the wrong one, because it hands
 *   every artifact a `<div>` and an `<iframe>` back. The setting is also *locked* — see `secure`
 *   below, without which one line of frontmatter in a file a model wrote undoes all of this.
 *
 * **Nothing here reads her prose.** A fenced ```` ```mermaid ```` block in an answer stays a code
 * block; only a published `.mmd` artifact is drawn. That is what keeps this on the right side of
 * ADR 11 — it is a renderer for one artifact kind, not a second parser in the browser.
 */

import { sanitiseSvg } from './artifacts';

/** The loaded library, kept as the *promise* rather than the module.
 *
 * Two diagrams opened in the same second must not start two downloads, and the second one must
 * not draw before `initialize` has run. Caching the in-flight promise gives both: everybody
 * after the first awaits the same load and the same configuration.
 */
let engine: Promise<typeof import('mermaid').default> | null = null;

function library(): Promise<typeof import('mermaid').default> {
	// The *failed* load is deliberately not cached. A chunk that did not arrive is usually a
	// network that was not there, and keeping the rejected promise would mean every diagram for
	// the rest of the session failing for a reason that stopped being true — on a self-hosted
	// thing with an offline banner in it, that is a state a person really does come back from.
	engine ??= import('mermaid')
		.then(({ default: mermaid }) => {
			mermaid.initialize({
				// Nothing is drawn by scanning the page for `.mermaid` elements — every diagram here
				// is rendered by name, from a file, on request.
				startOnLoad: false,
				// Mermaid's own guard, on top of the sanitiser: markup in a label is encoded rather
				// than emitted, and `click` directives do not become handlers. Neither of those
				// survives `sanitiseSvg` either, which is the point of having both.
				securityLevel: 'strict',
				// Why a diagram has readable labels at all — see the note above.
				htmlLabels: false,
				// And why that setting *holds*. A `.mmd` is written by a model, and mermaid lets
				// the source override configuration through frontmatter — `config: {htmlLabels:
				// true}` above the diagram is ordinary syntax, not an exotic payload. Without
				// this, that one line turns every label back into a `<foreignObject>`, the
				// sanitiser strips it, and the diagram arrives with its boxes intact and every
				// word gone. `secure` is the list of keys only `initialize` may set; supplying it
				// *replaces* mermaid's default rather than extending it, so its six defaults are
				// repeated here and `htmlLabels` is the one being added.
				secure: [
					'secure',
					'securityLevel',
					'startOnLoad',
					'maxTextSize',
					'suppressErrorRendering',
					'maxEdges',
					'htmlLabels'
				],
				// A failed parse throws and leaves nothing behind. Without this, mermaid draws its
				// own error graphic into the page, which would put *mermaid's* idea of a failure on
				// screen instead of the source view that lets a person see what went wrong.
				suppressErrorRendering: true,
				// The interface's own UI face (`--font-ui` in `app.css`), spelled out rather than
				// read from the custom property: mermaid measures label widths against this font
				// while laying the diagram out, and a `var()` that fails to resolve in the element
				// it measures in comes out as text overflowing its boxes.
				fontFamily: "'Figtree Variable', system-ui, sans-serif",
				// A drawing sits on white whatever the theme is (`ArtifactView`), so the renderer is
				// never told about dark mode and never has to be re-run when the theme changes.
				theme: 'default'
			});
			return mermaid;
		})
		.catch((cause) => {
			engine = null;
			throw cause;
		});
	return engine;
}

/** Never repeats, so two diagrams on screen cannot collide.
 *
 * Mermaid scopes the `<style>` it writes into the drawing with the id it was given, and the id
 * survives sanitising — two drawings sharing one would mean the first one's styles landing on
 * the second. A counter is enough because it only has to be unique within a page's lifetime.
 */
let serial = 0;

/**
 * One diagram, drawn and safe to put into the document.
 *
 * Rejects the way mermaid rejects — a syntax error in the source is an `Error` with the line in
 * it, and the caller shows that line over the source rather than swallowing it. A diagram that
 * did not come out is something a person can fix; a blank box is not.
 */
export async function draw(source: string): Promise<string> {
	const mermaid = await library();
	const { svg } = await mermaid.render(`mermaid-drawing-${++serial}`, source);
	return sanitiseSvg(svg);
}
