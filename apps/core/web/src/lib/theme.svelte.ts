/**
 * System, light or dark.
 *
 * System is the default, because a person who has already told their machine wants the same
 * answer here. The chosen mode is written to `data-theme` on `<html>`; `app.css` puts the dark
 * tokens on `:root` as well, so a dark-preferring visitor gets them before any of this runs —
 * a light flash on load is the one thing a warm interface cannot afford.
 */

import registry from '$lib/themes/registry.json';

export type Appearance = 'system' | 'light' | 'dark';

const KEY = 'hera:appearance';

/** Every imported theme (ADR 21), and the one a fresh browser gets. */
export const THEMES = registry;
const DEFAULT = THEMES.find((entry) => entry.default) ?? THEMES[0];

class Theme {
	appearance = $state<Appearance>('system');
	/** Which imported theme is on screen. Only the default exists today, so nothing sets it yet;
	 * it is written to `data-palette` all the same, so a second theme is a picker away. */
	palette = $state(DEFAULT.id);

	/** What is actually on screen, after `system` has been resolved. */
	resolved = $derived(this.appearance === 'system' ? systemPreference() : this.appearance);

	load() {
		const stored = localStorage.getItem(KEY);
		if (stored === 'light' || stored === 'dark' || stored === 'system') this.appearance = stored;
		this.apply();

		// Follow the machine while set to `system`, without a reload.
		matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
			if (this.appearance === 'system') this.apply();
		});
	}

	set(appearance: Appearance) {
		this.appearance = appearance;
		localStorage.setItem(KEY, appearance);
		this.apply();
	}

	apply() {
		const root = document.documentElement;
		root.dataset.theme = this.resolved;
		root.dataset.palette = this.palette;
		// The installed app's chrome follows the same resolution the page does, instead of
		// staying pinned to the dark value `app.html` ships as its pre-hydration default. The
		// ground comes from the registry rather than a stylesheet because a PWA's chrome wants
		// it before the page has necessarily painted anything to compute it from.
		const ground = (THEMES.find((entry) => entry.id === this.palette) ?? DEFAULT).ground;
		document
			.querySelector('meta[name="theme-color"]')
			?.setAttribute('content', ground[this.resolved]);
	}
}

function systemPreference(): 'light' | 'dark' {
	if (typeof matchMedia === 'undefined') return 'dark';
	return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export const theme = new Theme();
