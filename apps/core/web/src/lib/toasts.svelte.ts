/**
 * One-line confirmations that leave on their own (the theme's `hera/toast`): *Copied*, *Saved*,
 * *Could not save — the server did not answer*.
 *
 * The store is the behaviour and `Toaster.svelte` the picture, kept apart so the timing can be
 * tested without a DOM. A toast is for something that already happened and needs no decision;
 * anything that needs one is a card or a dialog, because a message that disappears while you are
 * reading it cannot ask you anything.
 */

/** How long a toast stays: the theme's `toast.enter` slot carries 3000 ms as its hold (`wo`). */
export const STAY = 3000;

export interface Toast {
	id: number;
	message: string;
	kind: 'success' | 'failure';
	/** One optional follow-up, like *Undo*. Running it dismisses the toast. */
	action?: { label: string; run: () => void };
}

export class Toasts {
	items = $state<Toast[]>([]);
	#next = 1;
	/** Bookkeeping, not state: nothing renders from it, so it is a plain record. */
	#timers: Record<number, ReturnType<typeof setTimeout>> = {};

	show(message: string, options: Pick<Partial<Toast>, 'kind' | 'action'> = {}): number {
		const id = this.#next++;
		this.items = [
			...this.items,
			{ id, message, kind: options.kind ?? 'success', action: options.action }
		];
		this.#timers[id] = setTimeout(() => this.dismiss(id), STAY);
		return id;
	}

	/** A failure toast. Same lifetime: a failure that needs the person to do something is not a
	 * toast. */
	fail(message: string): number {
		return this.show(message, { kind: 'failure' });
	}

	dismiss(id: number) {
		clearTimeout(this.#timers[id]);
		delete this.#timers[id];
		this.items = this.items.filter((toast) => toast.id !== id);
	}

	/** Holds a toast while the pointer or focus is on it, so its action can be reached. */
	hold(id: number) {
		clearTimeout(this.#timers[id]);
	}

	release(id: number) {
		if (!this.items.some((toast) => toast.id === id)) return;
		this.#timers[id] = setTimeout(() => this.dismiss(id), STAY);
	}
}

export const toasts = new Toasts();
