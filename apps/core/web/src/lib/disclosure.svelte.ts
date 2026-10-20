/**
 * Which disclosures somebody has opened, for as long as the page lives.
 *
 * Keyed by a name rather than held inside the component that draws the disclosure, because
 * Settings remounts a screen every time it is left and re-entered, and a provider you had opened
 * should still be open when you come back. Held in memory rather than in storage on purpose: a
 * reload goes back to each screen's own first-paint rule (for Models, only the active provider
 * open), which is a better start than whatever was left open last week.
 *
 * `fallback` is that rule. Until somebody has toggled a key, the answer is the fallback, so the
 * very first frame is right without an effect having to seed anything.
 */
export class Disclosure {
	#open = $state<Record<string, boolean>>({});

	isOpen(key: string, fallback: boolean): boolean {
		return this.#open[key] ?? fallback;
	}

	set(key: string, open: boolean) {
		this.#open = { ...this.#open, [key]: open };
	}

	toggle(key: string, fallback: boolean) {
		this.set(key, !this.isOpen(key, fallback));
	}
}

/** The Models screen's providers, by name. */
export const providers = new Disclosure();
