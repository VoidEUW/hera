/**
 * System, light or dark.
 *
 * System is the default, because a person who has already told their machine wants the same
 * answer here. The chosen mode is written to `data-theme` on `<html>`; `app.css` puts the dark
 * tokens on `:root` as well, so a dark-preferring visitor gets them before any of this runs —
 * a light flash on load is the one thing a warm interface cannot afford.
 */

export type Appearance = 'system' | 'light' | 'dark';

const KEY = 'hera:appearance';

/** The ground colour of each resolved appearance, in one place with `app.css`'s `--ground`
 * rather than read back out of a stylesheet — a PWA's chrome (status bar, task switcher) wants
 * this before the page has necessarily painted anything to compute it from. */
const GROUND: Record<'light' | 'dark', string> = {
	light: '#F6EEDB',
	dark: '#17130A'
};

class Theme {
	appearance = $state<Appearance>('system');

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
		document.documentElement.dataset.theme = this.resolved;
		// The installed app's chrome follows the same resolution the page does, instead of
		// staying pinned to the dark value `app.html` ships as its pre-hydration default.
		document
			.querySelector('meta[name="theme-color"]')
			?.setAttribute('content', GROUND[this.resolved]);
	}
}

function systemPreference(): 'light' | 'dark' {
	if (typeof matchMedia === 'undefined') return 'dark';
	return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export const theme = new Theme();
