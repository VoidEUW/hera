/**
 * Every keyboard chord in Hera, in one place (#112).
 *
 * **One rule, from v0.2.1:** a shortcut is a control that also exists on screen. A feature only a
 * chord reaches is one nobody discovers, so every binding below names the `control` it mirrors,
 * the Hotkeys screen prints that beside the chord, and a test fails on an entry that names none.
 *
 * The map is data — `{ id, label, group, control, default }` — so rebinding later is a screen
 * over this list rather than a rewrite. A person's own choices would live in `overrides`, read
 * through `current()`; nothing writes them yet.
 *
 * A chord is written `Mod+Shift+O`. `Mod` is ⌘ on macOS and Ctrl everywhere else, which is the
 * one translation every cross-platform app makes. Matching is on `event.key`, and Shift is only
 * part of the chord for letters, arrows and named keys: on a German keyboard `/` is Shift+7, so
 * a chord of `Mod+/` that required "no Shift" would never fire there.
 *
 * **Components register handlers; nothing here knows a component.** A chat-only chord exists only
 * while the chat screen has registered it, which is what stops ⌘. toggling a drawer that is not
 * there. A handler returns `false` to decline — "not now" — and the browser keeps the chord.
 */

export type KeyId =
	| 'palette'
	| 'palette.chats'
	| 'settings'
	| 'newChat'
	| 'hotkeys'
	| 'escape'
	| 'composer'
	| 'chat.previous'
	| 'chat.next'
	| 'chat.find'
	| 'chat.sideView'
	| 'chat.save'
	| 'chat.export'
	| 'chat.share'
	| 'chat.delete';

export interface Binding {
	id: KeyId;
	/** What it does, as the Hotkeys screen says it. */
	label: string;
	group: 'global' | 'chat';
	/** The on-screen control it mirrors — the rule, written down. */
	control: string;
	default: string;
	/** Fires while a text field has focus. Off for the chords a text field already uses for
	 * editing (⌘⌫ deletes a line, ⌥↑ moves the cursor), so the composer never loses a keystroke
	 * to a shortcut. */
	inFields?: boolean;
	/** Drawn and listed, but the control it mirrors is not usable yet, so nothing is bound. */
	planned?: boolean;
}

export const BINDINGS: readonly Binding[] = [
	{
		id: 'palette',
		label: 'Search and jump',
		group: 'global',
		control: 'Search in the sidebar',
		default: 'Mod+K',
		inFields: true
	},
	{
		id: 'palette.chats',
		label: 'Search chats',
		group: 'global',
		control: 'Search in the sidebar',
		default: 'Mod+Shift+F',
		inFields: true
	},
	{
		id: 'settings',
		label: 'Open Settings',
		group: 'global',
		control: 'Account in the sidebar',
		default: 'Mod+,',
		inFields: true
	},
	{
		id: 'newChat',
		label: 'New chat',
		group: 'global',
		control: 'New chat in the sidebar',
		default: 'Mod+Shift+O',
		inFields: true
	},
	{
		id: 'hotkeys',
		label: 'Show the keyboard shortcuts',
		group: 'global',
		control: 'Settings, Hotkeys',
		default: 'Mod+/',
		inFields: true
	},
	{
		id: 'escape',
		label: 'Close the topmost thing',
		group: 'global',
		control: 'Each layer’s close button',
		default: 'Escape'
	},
	{
		id: 'composer',
		label: 'Focus the message field',
		group: 'global',
		control: 'The message field',
		default: 'Shift+Escape',
		inFields: true
	},
	{
		id: 'chat.previous',
		label: 'Previous chat',
		group: 'global',
		control: 'The chats in the sidebar',
		default: 'Alt+ArrowUp'
	},
	{
		id: 'chat.next',
		label: 'Next chat',
		group: 'global',
		control: 'The chats in the sidebar',
		default: 'Alt+ArrowDown'
	},
	{
		id: 'chat.find',
		label: 'Find in this chat',
		group: 'chat',
		control: 'Find, in the top bar',
		default: 'Mod+F',
		inFields: true
	},
	{
		id: 'chat.sideView',
		label: 'Show or hide the side view',
		group: 'chat',
		control: 'Side view toggle, in the top bar',
		default: 'Mod+.',
		inFields: true
	},
	{
		id: 'chat.save',
		label: 'Save the open file',
		group: 'chat',
		control: 'Save, in the side view',
		default: 'Mod+S',
		inFields: true
	},
	{
		id: 'chat.export',
		label: 'Export this chat',
		group: 'chat',
		control: 'Export, in the chat menu',
		default: 'Mod+E',
		inFields: true
	},
	{
		id: 'chat.share',
		label: 'Share this chat',
		group: 'chat',
		control: 'Share, in the chat menu',
		default: 'Mod+Shift+E',
		planned: true
	},
	{
		id: 'chat.delete',
		label: 'Delete this chat',
		group: 'chat',
		control: 'Delete, in the chat menu',
		default: 'Mod+Backspace'
	}
];

/** What the browser keeps for itself — a page cannot intercept `⌘N`, `⌘T` or `⌘W`, and `⌘C`,
 * `⌘V`, `⌘Z` are the editing every text field relies on. A guard test keeps the map off them. */
export const RESERVED = [
	'Mod+A',
	'Mod+C',
	'Mod+N',
	'Mod+Q',
	'Mod+R',
	'Mod+T',
	'Mod+V',
	'Mod+W',
	'Mod+X',
	'Mod+Z',
	'Mod+Shift+N',
	'Mod+Shift+T',
	'Mod+Shift+W'
];

export interface Chord {
	mod: boolean;
	alt: boolean;
	shift: boolean;
	/** `event.key`, lowercased for a letter: `o`, `,`, `arrowup`, `escape`. */
	key: string;
}

export function parse(chord: string): Chord {
	const parts = chord.split('+');
	// A `+` key is the one chord that ends in the separator.
	const key = chord.endsWith('++') ? '+' : (parts[parts.length - 1] ?? '');
	const held = new Set(parts.slice(0, -1));
	return {
		mod: held.has('Mod'),
		alt: held.has('Alt'),
		shift: held.has('Shift'),
		key: key.toLowerCase()
	};
}

/** Whether the shift key is part of what a key *is* — a letter, an arrow, a named key — or only
 * how a layout reaches a symbol. */
function shiftMatters(key: string): boolean {
	return key.length > 1 || /[a-z0-9]/.test(key);
}

export function isMac(): boolean {
	if (typeof navigator === 'undefined') return false;
	return /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
}

/** The part of a `KeyboardEvent` a chord is matched on, so a test needs no DOM to make one. */
export type Press = Pick<KeyboardEvent, 'key' | 'metaKey' | 'ctrlKey' | 'altKey' | 'shiftKey'>;

export function matches(event: Press, chord: Chord, mac = isMac()): boolean {
	if (event.key.toLowerCase() !== chord.key) return false;
	const mod = mac ? event.metaKey : event.ctrlKey;
	const stray = mac ? event.ctrlKey : event.metaKey;
	if (stray || mod !== chord.mod || event.altKey !== chord.alt) return false;
	return !shiftMatters(chord.key) || event.shiftKey === chord.shift;
}

const NAMES: Record<string, string> = {
	escape: 'Esc',
	backspace: '⌫',
	arrowup: '↑',
	arrowdown: '↓',
	arrowleft: '←',
	arrowright: '→',
	enter: '↵'
};

/** A chord as it is drawn: `⌘⇧O` on a Mac, `Ctrl+Shift+O` elsewhere. */
export function format(chord: string, mac = isMac()): string {
	const { mod, alt, shift, key } = parse(chord);
	const name = NAMES[key] ?? key.toUpperCase();
	if (mac) return `${mod ? '⌘' : ''}${alt ? '⌥' : ''}${shift ? '⇧' : ''}${name}`;
	const words = NAMES[key] === '⌫' ? 'Backspace' : name;
	return [mod ? 'Ctrl' : '', alt ? 'Alt' : '', shift ? 'Shift' : '', words]
		.filter(Boolean)
		.join('+');
}

/** Focus is in something a person types into. */
export function typing(target: EventTarget | null): boolean {
	if (!(target instanceof HTMLElement)) return false;
	return target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName);
}

/** What stands over the page and answers its own Escape. */
const LAYERS = '[role="dialog"], [role="menu"], [role="listbox"]:not([data-inline])';

type Handler = () => boolean | void;

class Keymap {
	#handlers = new Map<KeyId, Handler[]>();
	#escapes: Array<{ priority: number; run: Handler }> = [];
	/** A person's own chords by id. Read through `chord()`; nothing writes it yet. */
	overrides: Partial<Record<KeyId, string>> = {};

	binding(id: KeyId): Binding {
		const found = BINDINGS.find((item) => item.id === id);
		if (!found) throw new Error(`no such key: ${id}`);
		return found;
	}

	/** The chord in force: the person's, else the default. */
	chord(id: KeyId): string {
		return this.overrides[id] ?? this.binding(id).default;
	}

	/** The chord as drawn beside a control, for the platform in use. */
	label(id: KeyId): string {
		return format(this.chord(id));
	}

	/** The chord for `aria-keyshortcuts`, which spells modifiers out: `Meta+Shift+O`. */
	aria(id: KeyId, mac = isMac()): string {
		const { mod, alt, shift, key } = parse(this.chord(id));
		const name = key.length === 1 ? key.toUpperCase() : key.replace(/^./, (c) => c.toUpperCase());
		return [mod ? (mac ? 'Meta' : 'Control') : '', alt ? 'Alt' : '', shift ? 'Shift' : '', name]
			.filter(Boolean)
			.join('+');
	}

	/** Register what a chord does. Returns the way to take it back — an `$effect` returns it
	 * directly, so a handler lives exactly as long as the component that owns it. The newest
	 * registration is asked first. */
	on(id: KeyId, run: Handler): () => void {
		const list = this.#handlers.get(id) ?? [];
		list.push(run);
		this.#handlers.set(id, list);
		return () => {
			const at = list.indexOf(run);
			if (at >= 0) list.splice(at, 1);
		};
	}

	/** Something that closes on Escape and is not a dialog or a menu: the side view, the find
	 * bar. The highest `priority` goes first, so what is nearest the hand closes first. */
	onEscape(run: Handler, priority = 0): () => void {
		const entry = { priority, run };
		this.#escapes.push(entry);
		this.#escapes.sort((a, b) => b.priority - a.priority);
		return () => {
			const at = this.#escapes.indexOf(entry);
			if (at >= 0) this.#escapes.splice(at, 1);
		};
	}

	/** The one `keydown` listener. Returns whether the chord was handled. */
	dispatch(event: KeyboardEvent): boolean {
		if (event.defaultPrevented || event.isComposing) return false;
		if (event.key === 'Escape' && !event.shiftKey) return this.#escape(event);
		const fields = typing(event.target);
		for (const binding of BINDINGS) {
			if (binding.planned || binding.id === 'escape') continue;
			if (fields && !binding.inFields) continue;
			if (!matches(event, parse(this.chord(binding.id)))) continue;
			const list = this.#handlers.get(binding.id) ?? [];
			for (let at = list.length - 1; at >= 0; at -= 1) {
				if (list[at]?.() === false) continue;
				event.preventDefault();
				return true;
			}
		}
		return false;
	}

	/** Escape closes the topmost thing — a menu, then a dialog, which answer for themselves —
	 * and only then what is registered here. A text field keeps its own Escape (clear a search,
	 * cancel a rename), so it never closes a drawer behind a person's back. */
	#escape(event: KeyboardEvent): boolean {
		if (typing(event.target) || document.querySelector(LAYERS)) return false;
		for (const { run } of this.#escapes) {
			if (run() === false) continue;
			event.preventDefault();
			return true;
		}
		return false;
	}
}

export const keys = new Keymap();
