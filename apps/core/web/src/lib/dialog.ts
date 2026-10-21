/**
 * What makes an element a dialog to a keyboard, in one place (#121, the first step of #112's
 * "one Escape").
 *
 *     <div role="dialog" aria-modal="true" use:dialog={{ onclose }}>…</div>
 *
 * - **focus in:** the first control takes focus when the dialog becomes active — a dialog that
 *   does not is one a keyboard user has to tab into;
 * - **focus held:** Tab and Shift+Tab wrap inside it. `aria-modal` promises that nothing outside
 *   is reachable, and Tab is where that promise is kept;
 * - **Escape:** closes it — but only the topmost dialog answers, and not while one of its own
 *   dropdowns is open, because one Escape does one thing;
 * - **focus back:** returned to whatever had it before, usually the control that opened it.
 *
 * `active` exists for the rail, which is a permanent element that only *becomes* a dialog when it
 * is opened as a sheet on a phone. Turning it on and off runs the same in and out as mounting and
 * unmounting would.
 */

const FIRST =
	'input, button:not(.close), select, textarea, [href], [tabindex]:not([tabindex="-1"])';
const FOCUSABLE =
	'input:not([disabled]), button:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])';

export interface DialogParams {
	onclose?: () => void;
	active?: boolean;
}

/** Whether `node` is the last open dialog in the document — the one on top. A sheet opened
 * from inside another (the skill editor over Settings) is later in the document. */
export function topmost(node: Element): boolean {
	const open = document.querySelectorAll('[role="dialog"]');
	return open[open.length - 1] === node;
}

export function dialog(node: HTMLElement, params: DialogParams = {}) {
	let onclose = params.onclose;
	let active = false;
	let opener: HTMLElement | null = null;

	function onkeydown(event: KeyboardEvent) {
		if (!topmost(node)) return;
		if (event.key === 'Escape') {
			// An open dropdown or menu inside the dialog is what this Escape is for; it closes
			// itself, and closing the dialog as well would be the double close they used to race.
			// An inline list — the command palette's results — is not a dropdown; it sits in the
			// dialog and Escape closes the dialog around it.
			if (node.querySelector('[role="listbox"]:not([data-inline]), [role="menu"]')) return;
			onclose?.();
			return;
		}
		if (event.key !== 'Tab') return;
		const focusable = [...node.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
			(element) => element.offsetParent !== null
		);
		if (!focusable.length) return;
		const first = focusable[0];
		const last = focusable[focusable.length - 1];
		const here = document.activeElement;
		if (event.shiftKey && (here === first || here === node)) {
			event.preventDefault();
			last.focus();
		} else if (!event.shiftKey && here === last) {
			event.preventDefault();
			first.focus();
		}
	}

	function enter() {
		if (active) return;
		active = true;
		opener = document.activeElement as HTMLElement | null;
		(node.querySelector<HTMLElement>(FIRST) ?? node).focus();
		window.addEventListener('keydown', onkeydown);
	}

	function leave() {
		if (!active) return;
		active = false;
		window.removeEventListener('keydown', onkeydown);
		opener?.focus?.();
		opener = null;
	}

	if (params.active ?? true) enter();

	return {
		update(next: DialogParams) {
			onclose = next.onclose;
			if (next.active ?? true) enter();
			else leave();
		},
		destroy: leave
	};
}
