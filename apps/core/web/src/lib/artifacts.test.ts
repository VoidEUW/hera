/**
 * @vitest-environment jsdom
 *
 * jsdom because `sanitiseSvg` needs a DOM to sanitise in — the same reason `markdown.test.ts`
 * asks for one.
 *
 * The extension is the kind, and that is the whole of the decision (ADR 13) — so these tests are
 * about a filename and nothing else. There is no `kind` field anywhere for them to disagree with.
 *
 * `sanitiseSvg` gets the sharper tests: a drawing she made is markup a *model* wrote, going into
 * the page through `{@html}`, and the profile it goes through is what makes a picture a picture
 * rather than a document.
 */

import { describe, expect, it } from 'vitest';

import { downloadUrl, extensionOf, kindOf, sanitiseSvg, size, titleOf } from './artifacts';

describe('kindOf', () => {
	it('reads the renderer off the extension', () => {
		expect(kindOf('page.html')).toBe('html');
		expect(kindOf('flow.svg')).toBe('svg');
		expect(kindOf('report.md')).toBe('markdown');
		expect(kindOf('flow.mmd')).toBe('mermaid');
		expect(kindOf('setup.py')).toBe('code');
	});

	it('falls back to a plain file rather than guessing', () => {
		// Treating an unknown extension as text and hoping is how somebody is shown a screen of
		// replacement characters. A file she made is still a file, and the download says so.
		expect(kindOf('archive.zip')).toBe('file');
		expect(kindOf('README')).toBe('file');
	});

	it('does not care how the extension was capitalised', () => {
		expect(kindOf('PAGE.HTML')).toBe('html');
	});

	it('reads a dotfile as a name rather than as an extension', () => {
		expect(extensionOf('.notes')).toBe('');
	});
});

describe('titleOf', () => {
	it('humanises the filename and nothing more', () => {
		// The author chose these words. A browser second-guessing them is how one screen
		// disagrees with the next, which is why there is no title field to compete with this.
		expect(titleOf('theme-workshop.html')).toBe('Theme workshop');
		expect(titleOf('quarterly_report.md')).toBe('Quarterly report');
	});

	it('leaves a name with no extension alone', () => {
		expect(titleOf('README')).toBe('README');
	});
});

describe('sanitiseSvg', () => {
	it('keeps the drawing', () => {
		const drawn = sanitiseSvg('<svg viewBox="0 0 8 8"><circle cx="4" cy="4" r="3"/></svg>');
		expect(drawn).toContain('<circle');
	});

	it('takes the script out', () => {
		const drawn = sanitiseSvg('<svg><script>alert(1)</script><circle r="2"/></svg>');
		expect(drawn).not.toContain('alert');
		expect(drawn).toContain('<circle');
	});

	it('refuses markup that would make it a document rather than a picture', () => {
		// The svg profile only: a frame smuggled into a drawing is removed rather than rendered,
		// which is what keeps the difference between the two renderers real — a page gets the
		// sandbox, a picture gets this.
		const drawn = sanitiseSvg(
			'<svg><foreignObject><iframe src="http://x"></iframe></foreignObject></svg>'
		);
		expect(drawn).not.toContain('<iframe');
	});
});

describe('the download link', () => {
	it('escapes the name rather than trusting it in a URL', () => {
		expect(downloadUrl('c-1', 'a b&c.md')).toBe(
			'/api/v1/chats/c-1/artifacts/a%20b%26c.md/download'
		);
	});
});

describe('size', () => {
	it('says bytes below a kilobyte, because 0.0 KB says less than 812 B', () => {
		expect(size(812)).toBe('812 B');
		expect(size(2048)).toBe('2.0 KB');
		expect(size(3 * 1024 * 1024)).toBe('3.0 MB');
	});
});
