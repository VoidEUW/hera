import { describe, expect, it } from 'vitest';
import { decode, deviceName, encode } from './passkeys';

describe('base64url, the form WebAuthn bytes travel in', () => {
	it('round-trips every byte, with no padding and no + or /', () => {
		const bytes = new Uint8Array(256).map((_, index) => index);
		const text = encode(bytes.buffer);
		expect(text).not.toMatch(/[+/=]/);
		expect(new Uint8Array(decode(text))).toEqual(bytes);
	});

	it('reads what py_webauthn writes', () => {
		expect(new Uint8Array(decode('AQID'))).toEqual(new Uint8Array([1, 2, 3]));
		expect(new Uint8Array(decode('_-8'))).toEqual(new Uint8Array([255, 239]));
	});
});

describe('a first name for a passkey', () => {
	it('says browser and system', () => {
		const mac =
			'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36';
		expect(deviceName(mac)).toBe('Chrome on macOS');
		const iphone =
			'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1';
		expect(deviceName(iphone)).toBe('Safari on iOS');
		expect(deviceName('something else')).toBe('');
	});
});
