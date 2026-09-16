/**
 * How long a placeholder stays up.
 *
 * The rule that is *not* here is a delay before drawing one. The usual advice — wait 150 ms so a
 * fast fetch shows no grey at all — assumes the fetch is usually slow. Hers is not: this is a
 * self-hosted application talking to a server on the same machine, so the rail's three requests
 * land in well under that on every ordinary load. A delay therefore means the placeholder never
 * appears at all, and what a person sees is the thing it was meant to prevent: an empty rail for
 * a frame, then the whole list arriving at once and shoving the headings down the screen.
 *
 * So it is drawn at once, and the only rule is a floor. The floor is honestly an artificial
 * delay — the data is usually already there when it expires — and it is worth it, because half a
 * second of the shape of the list is how the list gets to *arrive* rather than to appear.
 *
 * No `$effect` in this file: the consumer owns the effect, which keeps `set` callable with plain
 * fake timers and keeps this away from the read-and-write-the-same-state shape that ends in
 * `effect_update_depth_exceeded`.
 */

/** How long a placeholder stays once it is up, measured from when it appeared. */
export const FLOOR = 500;

export class Placeholder {
	#shown = $state(false);
	#timer: ReturnType<typeof setTimeout> | null = null;
	/** When `#shown` last became true, so the floor is measured from the moment somebody could
	 * see it rather than from whenever the component happened to mount. */
	#since = 0;
	/** What the last `set` said, so repeating it does not restart the floor — an effect re-runs
	 * for reasons that have nothing to do with this flag. */
	#loading: boolean;

	/** @param loading whether it is already loading at the moment this is constructed. Passed
	 * rather than assumed false because the first render happens before the first effect, and a
	 * placeholder that misses that frame has let the empty state through in it. */
	constructor(loading = false) {
		this.#loading = loading;
		this.#shown = loading;
		this.#since = Date.now();
	}

	/** Whether to draw the placeholder. */
	get shown(): boolean {
		return this.#shown;
	}

	/** Drive this from an `$effect` that reads the loading flag. */
	set(loading: boolean): void {
		if (loading === this.#loading) return;
		this.#loading = loading;
		this.#clear();
		if (loading) {
			this.#since = Date.now();
			this.#shown = true;
			return;
		}
		if (!this.#shown) return;
		const left = FLOOR - (Date.now() - this.#since);
		if (left <= 0) {
			this.#shown = false;
			return;
		}
		this.#timer = setTimeout(() => {
			this.#timer = null;
			this.#shown = false;
		}, left);
	}

	/** Drop any pending timer. Call from a component's teardown; a timer that fires into an
	 * unmounted component is a write to state nobody is reading. */
	stop(): void {
		this.#clear();
	}

	#clear(): void {
		if (this.#timer === null) return;
		clearTimeout(this.#timer);
		this.#timer = null;
	}
}
