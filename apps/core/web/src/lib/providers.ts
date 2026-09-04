/**
 * Which small icon a provider shows beside its name.
 *
 * These are arbitrary self-hosted OpenAI-compatible endpoints, not a fixed catalogue of
 * vendors — `kind` is a person's own label, not something detected from `base_url`. Built-in
 * kinds get a monogram drawn here rather than a sourced vendor trademark image: bundling ten
 * brand logos as static assets is a licensing question this module doesn't need to take on, and
 * a monogram degrades the same way regardless of which kind it is. `'custom'` is the one kind
 * with a real uploaded image — see {@link api.logoUrl} — and only it needs the upload/serve
 * machinery on the API.
 */

import { api, type Provider, type ProviderKind } from '$lib/api/client';

export const PROVIDER_KINDS: ProviderKind[] = [
	'openai',
	'anthropic',
	'google',
	'mistral',
	'openrouter',
	'lmstudio',
	'ollama',
	'vllm',
	'llamacpp',
	'generic',
	'custom'
];

function monogram(letters: string, background: string): string {
	const svg =
		`<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 28 28">` +
		`<rect width="28" height="28" rx="7" fill="${background}"/>` +
		`<text x="14" y="19" font-family="system-ui, sans-serif" font-size="11" ` +
		`font-weight="600" fill="#fff" text-anchor="middle">${letters}</text></svg>`;
	return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

const BUILTIN_ICONS: Record<ProviderKind, string> = {
	openai: monogram('OA', '#10a37f'),
	anthropic: monogram('AN', '#d97757'),
	google: monogram('G', '#4285f4'),
	mistral: monogram('MI', '#fa520f'),
	openrouter: monogram('OR', '#6467f2'),
	lmstudio: monogram('LM', '#4c5cf0'),
	ollama: monogram('OL', '#1a1a1a'),
	vllm: monogram('VL', '#2f6f4f'),
	llamacpp: monogram('LC', '#8a5a2c'),
	generic: monogram('••', '#71717a'),
	custom: monogram('?', '#71717a')
};

/** The image to draw for one provider — its uploaded logo if it has one, otherwise the
 * built-in icon for its kind. */
export function providerIcon(provider: Provider): string {
	if (provider.kind === 'custom' && provider.logo_media_type) return api.logoUrl(provider.name);
	return BUILTIN_ICONS[provider.kind] ?? BUILTIN_ICONS.generic;
}

/** The built-in icon for a kind, regardless of any upload — used by the kind picker itself,
 * where every option needs to show what it *would* look like. */
export function kindIcon(kind: ProviderKind): string {
	return BUILTIN_ICONS[kind] ?? BUILTIN_ICONS.generic;
}
