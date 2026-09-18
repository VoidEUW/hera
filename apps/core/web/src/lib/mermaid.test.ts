/**
 * What saving a diagram hands over.
 *
 * `draw` itself is not tested here and cannot usefully be: mermaid lays a diagram out by
 * measuring its own text, so it wants a real browser — `tests/e2e/test_a_diagram_is_drawn.py`
 * is where that lives. What is testable below the browser is the other half, the conversion: a
 * drawn diagram is wrapped in a page so that what lands in a downloads folder is something that
 * opens, rather than six lines of mermaid nobody has a renderer for.
 */

import { describe, expect, it } from 'vitest';

import { page } from './mermaid';

describe('a diagram saved as a page', () => {
	const drawing = '<svg id="mermaid-drawing-1"><text>Client hello</text></svg>';

	it('is a whole document with the picture in it', () => {
		const saved = page('Handshake', drawing);

		expect(saved.startsWith('<!doctype html>')).toBe(true);
		expect(saved).toContain('<meta charset="utf-8" />');
		expect(saved).toContain(drawing);
		expect(saved).toContain('<title>Handshake</title>');
	});

	it('carries the drawing itself rather than fetching a renderer', () => {
		// The picture is already drawn by the time it gets here. A saved page that pulled two
		// megabytes of mermaid from a CDN to redraw it would be a page that stops working when
		// the network does — which is the opposite of what saving a file is for.
		const saved = page('Handshake', drawing);

		expect(saved).not.toContain('<script');
		expect(saved).not.toContain('<link');
	});

	it('escapes the title, because it came from a filename', () => {
		// A filename is not markup and this is the one place it is written into some. The name
		// belongs to a file a model chose the name of, so it goes through the same care her
		// prose does.
		const saved = page('A <b>bold</b> & brass plan', drawing);

		expect(saved).toContain('<title>A &lt;b&gt;bold&lt;/b&gt; &amp; brass plan</title>');
		expect(saved).not.toContain('<b>bold</b>');
	});

	it('does not lay the drawing out with flex', () => {
		// `ArtifactView`'s `.drawing` writes this trap down at length: an `<svg>` with
		// `height: auto` is a flex item whose cross size is `auto`, so it gets stretched to the
		// box instead of keeping its aspect ratio, and a tall flow chart comes out as a
		// thumbnail in an acre of white.
		const saved = page('Handshake', drawing);

		expect(saved).not.toContain('flex');
		expect(saved).toContain('margin: 0 auto');
	});
});
