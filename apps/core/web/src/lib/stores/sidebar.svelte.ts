/**
 * How wide the chat sidebar is, and whether it is folded to an icon rail (the theme's
 * `hera/sidebar`, chat variant). Kept per browser in localStorage, like the appearance: it is
 * about this screen, not about the person.
 *
 * The width is clamped to the theme's range on every way in — a drag, a key, a stored value from
 * an older build — so the sidebar can never be dragged into uselessness or stored there.
 */

export const MIN = 200;
export const MAX = 420;
/** One arrow-key press, in pixels. */
export const STEP = 16;
/** `--rail` in `app.css`: what a double-click on the handle goes back to. */
export const DEFAULT = 264;

const WIDTH = 'hera:sidebar-width';
const FOLDED = 'hera:sidebar-collapsed';

export function clamp(width: number): number {
	if (!Number.isFinite(width)) return DEFAULT;
	return Math.round(Math.min(MAX, Math.max(MIN, width)));
}

export class Sidebar {
	width = $state(DEFAULT);
	collapsed = $state(false);

	load(storage: Pick<Storage, 'getItem'> = localStorage) {
		const stored = storage.getItem(WIDTH);
		this.width = stored === null ? DEFAULT : clamp(Number(stored));
		this.collapsed = storage.getItem(FOLDED) === '1';
	}

	resize(width: number, storage: Pick<Storage, 'setItem'> = localStorage) {
		this.width = clamp(width);
		storage.setItem(WIDTH, String(this.width));
	}

	/** The keyboard on the resize handle: arrows step, Home and End jump to the ends. Returns
	 * whether the key was one of these, so the handler knows to swallow it. */
	key(key: string, storage: Pick<Storage, 'setItem'> = localStorage): boolean {
		const next =
			key === 'ArrowLeft'
				? this.width - STEP
				: key === 'ArrowRight'
					? this.width + STEP
					: key === 'Home'
						? MIN
						: key === 'End'
							? MAX
							: null;
		if (next === null) return false;
		this.resize(next, storage);
		return true;
	}

	reset(storage: Pick<Storage, 'setItem'> = localStorage) {
		this.resize(DEFAULT, storage);
	}

	toggle(storage: Pick<Storage, 'setItem'> = localStorage) {
		this.collapsed = !this.collapsed;
		storage.setItem(FOLDED, this.collapsed ? '1' : '0');
	}
}

export const sidebar = new Sidebar();
