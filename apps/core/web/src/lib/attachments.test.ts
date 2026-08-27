// @vitest-environment jsdom
//
// The one test file that needs a DOM: reading a picture goes through `FileReader`, which is
// the platform's own base64 and not something worth reimplementing in JS to keep the suite on
// the node environment.

/**
 * Attachments: what is accepted, what is refused, and how it reaches the model.
 *
 * The refusals matter more than the acceptances. A PDF arriving as mojibake would be worse than
 * a message saying it cannot be sent — the model would politely describe binary noise, and the
 * person would blame the model.
 *
 * Composing a file into what the model reads is the *server's* job now
 * (`hera_chats.history.content_of`), so there is nothing to test for it here.
 */

import { describe, expect, it } from 'vitest';

import { MAX_IMAGE_BYTES, MAX_TEXT_BYTES, isImage, looksLikeText, read, size } from './attachments';

const NUL = String.fromCharCode(0);
const BAD = '�';

describe('what looks like text', () => {
	it('accepts source', () => {
		expect(looksLikeText('const x = 1;\nif (x < 2) {}\n')).toBe(true);
	});

	it('accepts prose with accents and emoji', () => {
		expect(looksLikeText('Grüße — naïve café 🎉')).toBe(true);
	});

	it('refuses anything with a NUL in it', () => {
		expect(looksLikeText(`PK${NUL}${NUL}binary`)).toBe(false);
	});

	it('refuses a decode that produced mostly replacement characters', () => {
		// File.text() decodes as UTF-8 and never throws -- it substitutes U+FFFD -- so what came
		// out is the only evidence of what went in.
		expect(looksLikeText(BAD.repeat(20))).toBe(false);
	});

	it('tolerates one stray replacement character in a long file', () => {
		expect(looksLikeText('a'.repeat(4000) + BAD)).toBe(true);
	});
});

/** A file of a given type and size, without holding the bytes: only `size` and `type` are read
 * on the paths that refuse one, so a megabyte of test fixture buys nothing. */
function fake(name: string, type: string, bytes: number, body = 'x'): File {
	const file = new File([body], name, { type });
	Object.defineProperty(file, 'size', { value: bytes });
	return file;
}

describe('pictures', () => {
	it('reads one as a data URL with its media type', async () => {
		const { attachments, rejected } = await read([fake('shot.png', 'image/png', 9, 'PNGDATA')]);

		expect(rejected).toEqual([]);
		expect(isImage(attachments[0])).toBe(true);
		expect(attachments[0].media_type).toBe('image/png');
		expect(attachments[0].data_url).toMatch(/^data:image\/png;base64,/);
		expect(attachments[0].text).toBe('');
	});

	it('refuses an image format no endpoint will accept, and says which', async () => {
		// HEIC off a phone is the case this exists for. The browser will not decode it either,
		// so bytes no model can read is the worse of the two outcomes.
		const { attachments, rejected } = await read([fake('IMG_0001.heic', 'image/heic', 900)]);

		expect(attachments).toEqual([]);
		expect(rejected[0].reason).toContain('image/heic');
		expect(rejected[0].reason).toContain('PNG');
	});

	it('has its own ceiling, well above the one for text', async () => {
		expect(MAX_IMAGE_BYTES).toBeGreaterThan(MAX_TEXT_BYTES);

		const { rejected } = await read([fake('huge.png', 'image/png', MAX_IMAGE_BYTES + 1)]);
		expect(rejected[0].reason).toContain('12 MB');
	});

	it('lets a photograph through at a size a phone actually produces', async () => {
		const { attachments } = await read([fake('photo.jpg', 'image/jpeg', 4 * 1024 * 1024)]);
		expect(attachments).toHaveLength(1);
	});
});

describe('text files', () => {
	it('still travel as text, with no data URL', async () => {
		const { attachments } = await read([fake('a.py', 'text/x-python', 5, 'x = 1')]);

		expect(isImage(attachments[0])).toBe(false);
		expect(attachments[0].text).toBe('x = 1');
		expect(attachments[0].data_url).toBeUndefined();
	});

	it('says PDFs are not readable yet rather than sending mojibake', async () => {
		const { rejected } = await read([fake('paper.pdf', 'application/pdf', 40, `%PDF-1.4\0\0\0`)]);
		expect(rejected[0].reason).toContain('PDF');
	});
});

describe('sizes read as sizes', () => {
	it('counts bytes, kilobytes and megabytes', () => {
		expect(size(512)).toBe('512 B');
		expect(size(2048)).toBe('2 KB');
		expect(size(1024 * 1024 * 1.5)).toBe('1.5 MB');
	});
});
