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

import { downloadUrl, extensionOf, kindOf, newest, sanitiseSvg, size, titleOf } from './artifacts';

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

	it('takes a perfectly innocent label out with it, which is why mermaid may not use one', () => {
		// Not a security test — a constraint, pinned where somebody would look before changing
		// `$lib/mermaid`'s configuration. The profile cannot tell a smuggled frame from a label,
		// so it removes both, and mermaid's *default* label is exactly this: a `<foreignObject>`
		// full of XHTML. A diagram drawn that way arrives with every box intact and every word
		// gone, which is the shape of failure that reads as success. `htmlLabels: false` is the
		// answer; widening this profile to `html` is the one that hands every artifact a frame.
		const drawn = sanitiseSvg(
			'<svg><foreignObject><div><span>Client hello</span></div></foreignObject>' +
				'<text>Server hello</text></svg>'
		);
		expect(drawn).not.toContain('Client hello');
		expect(drawn).toContain('Server hello');
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

describe('newest', () => {
	const file = (name: string, modified_at: string) => ({ name, bytes: 10, modified_at });

	it('opens the one she made last, not the one that sorts last', () => {
		// The listing arrives in name order, so `aardvark.md` is first and `zebra.md` last --
		// and neither of those facts says anything about which one is the recent one.
		const found = [
			file('aardvark.md', '2026-09-16T12:00:00+00:00'),
			file('zebra.md', '2026-09-16T09:00:00+00:00')
		];

		expect(newest(found)?.name).toBe('aardvark.md');
	});

	it('breaks a tie towards the later entry in the bar', () => {
		const found = [
			file('one.md', '2026-09-16T12:00:00+00:00'),
			file('two.md', '2026-09-16T12:00:00+00:00')
		];

		expect(newest(found)?.name).toBe('two.md');
	});

	it('has nothing to open when there is nothing published', () => {
		expect(newest([])).toBeNull();
	});

	it('falls back to the last file when no stamp can be read', () => {
		const found = [file('one.md', 'not a date'), file('two.md', '')];

		expect(newest(found)?.name).toBe('two.md');
	});
});
