/**
 * Passkeys in the browser (ADR 27, M4): asking the authenticator, and translating between the
 * server's JSON and the binary buffers WebAuthn speaks.
 *
 * The server sends options as `py_webauthn` writes them — every binary field base64url-encoded —
 * and wants the credential back the same way, which is what `PublicKeyCredential.toJSON()`
 * produces where it exists. It does not exist everywhere yet, so both directions are done here,
 * by hand, the same on every browser.
 *
 * Nothing about passkeys is drawn unless {@link available} says so: WebAuthn is missing outright
 * outside a secure context (a plain-http LAN address), and a button that can only fail is a door
 * painted on a wall.
 */

type Json = Record<string, unknown>;

/** Whether this browser, on this page, can use a passkey at all. */
export function available(): boolean {
	return window.isSecureContext && typeof window.PublicKeyCredential !== 'undefined';
}

/** Make a passkey: the options from `POST /auth/passkeys/options`, the answer for `/auth/passkeys`. */
export async function create(options: Json): Promise<Json> {
	const user = options.user as Json;
	const publicKey = {
		...options,
		challenge: decode(options.challenge as string),
		user: { ...user, id: decode(user.id as string) },
		excludeCredentials: descriptors(options.excludeCredentials)
	} as unknown as PublicKeyCredentialCreationOptions;
	const credential = (await navigator.credentials.create({ publicKey })) as PublicKeyCredential;
	const response = credential.response as AuthenticatorAttestationResponse;
	return {
		...common(credential),
		response: {
			clientDataJSON: encode(response.clientDataJSON),
			attestationObject: encode(response.attestationObject),
			transports: response.getTransports?.() ?? []
		}
	};
}

/** Sign in: the options from `POST /auth/passkey/options`, the answer for `/auth/passkey`. */
export async function get(options: Json): Promise<Json> {
	const publicKey = {
		...options,
		challenge: decode(options.challenge as string),
		allowCredentials: descriptors(options.allowCredentials)
	} as unknown as PublicKeyCredentialRequestOptions;
	const credential = (await navigator.credentials.get({ publicKey })) as PublicKeyCredential;
	const response = credential.response as AuthenticatorAssertionResponse;
	return {
		...common(credential),
		response: {
			clientDataJSON: encode(response.clientDataJSON),
			authenticatorData: encode(response.authenticatorData),
			signature: encode(response.signature),
			userHandle: response.userHandle ? encode(response.userHandle) : null
		}
	};
}

/** The person closed the browser's sheet, or it timed out: not an error worth a sentence. */
export function cancelled(cause: unknown): boolean {
	return cause instanceof DOMException && cause.name === 'NotAllowedError';
}

/** A first name for a new passkey — "Chrome on macOS" — so a list of them can be told apart
 * before anybody renames one. */
export function deviceName(agent = navigator.userAgent): string {
	const system = /iPhone|iPad/.test(agent)
		? 'iOS'
		: /Android/.test(agent)
			? 'Android'
			: /Mac OS X/.test(agent)
				? 'macOS'
				: /Windows/.test(agent)
					? 'Windows'
					: /Linux/.test(agent)
						? 'Linux'
						: '';
	const browser = /Edg\//.test(agent)
		? 'Edge'
		: /Firefox\//.test(agent)
			? 'Firefox'
			: /Chrome\//.test(agent)
				? 'Chrome'
				: /Safari\//.test(agent)
					? 'Safari'
					: '';
	return [browser, system].filter(Boolean).join(' on ');
}

function common(credential: PublicKeyCredential): Json {
	return {
		id: credential.id,
		rawId: encode(credential.rawId),
		type: credential.type,
		clientExtensionResults: credential.getClientExtensionResults(),
		authenticatorAttachment: credential.authenticatorAttachment ?? undefined
	};
}

function descriptors(value: unknown): PublicKeyCredentialDescriptor[] {
	return ((value as Json[] | undefined) ?? []).map((item) => ({
		...(item as unknown as PublicKeyCredentialDescriptor),
		id: decode(item.id as string)
	}));
}

export function encode(buffer: ArrayBuffer): string {
	let text = '';
	for (const byte of new Uint8Array(buffer)) text += String.fromCharCode(byte);
	return btoa(text).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

export function decode(value: string): ArrayBuffer {
	const base64 = value.replace(/-/g, '+').replace(/_/g, '/');
	const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
	const text = atob(padded);
	const bytes = new Uint8Array(text.length);
	for (let index = 0; index < text.length; index++) bytes[index] = text.charCodeAt(index);
	return bytes.buffer;
}
