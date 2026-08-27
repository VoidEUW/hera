/**
 * Attachments: what is accepted, what is refused, and how it reaches the model.
 *
 * The refusals matter more than the acceptances. A PDF arriving as mojibake would be worse than
 * a message saying it cannot be sent — the model would politely describe binary noise, and the
 * person would blame the model.
 *
 * Composing a file into what the model reads is the *server's* job now
 * (`hera_chats.history.compose`), so there is nothing to test for it here.
 */

import { describe, expect, it } from 'vitest';

import { looksLikeText, size } from './attachments';

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

describe('sizes read as sizes', () => {
	it('counts bytes, kilobytes and megabytes', () => {
		expect(size(512)).toBe('512 B');
		expect(size(2048)).toBe('2 KB');
		expect(size(1024 * 1024 * 1.5)).toBe('1.5 MB');
	});
});
