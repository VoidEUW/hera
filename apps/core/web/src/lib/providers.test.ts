/**
 * Which icon a provider shows: its own uploaded logo when it has one, the built-in monogram
 * otherwise — including while `'custom'` is selected but nothing has been uploaded yet, which
 * must not throw or point at a logo that doesn't exist.
 */

import { describe, expect, it } from 'vitest';

import type { Provider } from './api/client';
import { kindIcon, providerIcon } from './providers';

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
