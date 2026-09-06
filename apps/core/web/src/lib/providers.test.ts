/**
 * Which icon a provider shows: its own uploaded logo when it has one, the built-in monogram
 * otherwise — including while `'custom'` is selected but nothing has been uploaded yet, which
 * must not throw or point at a logo that doesn't exist.
 */

import { describe, expect, it } from 'vitest';

import type { Provider } from './api/client';
import { kindFallbackIcon, kindIcon, providerFallbackIcon, providerIcon } from './providers';

function provider(overrides: Partial<Provider> = {}): Provider {
	return {
		name: 'local',
		kind: 'generic',
		base_url: 'http://localhost:1234/v1',
		models: [],
		active_model: '',
		embedding_model: '',
		timeout_s: 600,
		connect_timeout_s: 5,
		api_key_set: false,
		logo_media_type: '',
		...overrides
	};
}

describe('providerIcon', () => {
	it('points at the uploaded logo for a custom provider that has one', () => {
		const icon = providerIcon(
			provider({ name: 'mine', kind: 'custom', logo_media_type: 'image/png' })
		);
		expect(icon).toBe('/api/v1/providers/mine/logo');
	});

	it('falls back to the built-in icon for a custom provider with nothing uploaded yet', () => {
		const icon = providerIcon(provider({ kind: 'custom', logo_media_type: '' }));
		expect(icon).toBe(kindIcon('custom'));
	});

	it('uses the built-in icon for every other kind', () => {
		for (const kind of ['openai', 'anthropic', 'ollama', 'generic'] as const) {
			expect(providerIcon(provider({ kind }))).toBe(kindIcon(kind));
		}
	});
});

describe('kindIcon', () => {
	it('points at a bundled logo file for a kind that has one', () => {
		expect(kindIcon('openai')).toBe('/providers/openai.svg');
		expect(kindIcon('anthropic')).toBe('/providers/claude.svg');
		expect(kindIcon('google')).toBe('/providers/google.svg');
		expect(kindIcon('mistral')).toBe('/providers/mistral.svg');
		expect(kindIcon('lmstudio')).toBe('/providers/lmstudio.svg');
		expect(kindIcon('ollama')).toBe('/providers/ollama.svg');
		expect(kindIcon('openrouter')).toBe('/providers/openrouter.svg');
		expect(kindIcon('vllm')).toBe('/providers/vllm.svg');
	});

	it('falls back to a monogram for a kind with no bundled file yet', () => {
		for (const kind of ['llamacpp', 'generic'] as const) {
			expect(kindIcon(kind)).toBe(kindFallbackIcon(kind));
			expect(kindIcon(kind)).toMatch(/^data:image\/svg\+xml,/);
		}
	});
});

describe('kindFallbackIcon / providerFallbackIcon', () => {
	it('is always a generated monogram, even for a kind with a bundled file', () => {
		expect(kindIcon('anthropic')).not.toMatch(/^data:/);
		expect(kindFallbackIcon('anthropic')).toMatch(/^data:image\/svg\+xml,/);
	});

	it('matches the kind fallback for a given provider', () => {
		expect(providerFallbackIcon(provider({ kind: 'anthropic' }))).toBe(
			kindFallbackIcon('anthropic')
		);
	});
});
