/**
 * A short label for an icon-only control (the theme's `hera/tooltip`): inverted text on ink,
 * rounded, above the control, below it when there is no room above.
 *
 *     <button use:tooltip={t.composer.attach}>…</button>
 *
 * An action rather than a component, because the label belongs to the element it describes and
 * wrapping every icon button in a positioning box would change the layout it sits in. The label
 * is appended to `<body>` so no `overflow: hidden` ancestor can clip it.
 *
 * Timing is the spec's: shown after the pointer has rested `SHOW_AFTER`, gone the moment it
 * leaves, fading in on `tooltip.enter`. Keyboard focus shows it at once — a person tabbing is
 * already asking what the control is. It is a visual aid, not the accessible name: the control
 * still needs its own `aria-label`.
 */
import { still } from './motion';

/** The spec's tooltip delay (`tooltip.enter`, its `w`). */
export const SHOW_AFTER = 1200;

export function tooltip(node: HTMLElement, label: string | undefined) {
	let text = label;
	let tip: HTMLDivElement | null = null;
	let timer: ReturnType<typeof setTimeout> | undefined;

	function place() {
		if (!tip) return;
		const box = node.getBoundingClientRect();
		const own = tip.getBoundingClientRect();
		const gap = 6;
		const above = box.top - own.height - gap;
		const top = above < 4 ? box.bottom + gap : above;
		const left = Math.min(
			Math.max(4, box.left + box.width / 2 - own.width / 2),
			window.innerWidth - own.width - 4
		);
		tip.style.top = `${top + window.scrollY}px`;
		tip.style.left = `${left + window.scrollX}px`;
	}

	function show() {
		if (!text || tip) return;
		tip = document.createElement('div');
		tip.className = 'hera-tooltip';
		tip.setAttribute('role', 'tooltip');
		tip.textContent = text;
		if (still()) tip.style.animation = 'none';
		document.body.append(tip);
		place();
	}

	function hide() {
		clearTimeout(timer);
		tip?.remove();
		tip = null;
	}

	function rest() {
		clearTimeout(timer);
		timer = setTimeout(show, SHOW_AFTER);
	}

	function focus() {
		if (node.matches(':focus-visible')) show();
	}

	node.addEventListener('pointerenter', rest);
	node.addEventListener('pointerleave', hide);
	node.addEventListener('pointerdown', hide);
	node.addEventListener('focusin', focus);
	node.addEventListener('focusout', hide);
	window.addEventListener('scroll', hide, true);

	return {
		update(next: string | undefined) {
			text = next;
			if (tip && text) tip.textContent = text;
			if (!text) hide();
		},
		destroy() {
			hide();
			node.removeEventListener('pointerenter', rest);
			node.removeEventListener('pointerleave', hide);
			node.removeEventListener('pointerdown', hide);
			node.removeEventListener('focusin', focus);
			node.removeEventListener('focusout', hide);
			window.removeEventListener('scroll', hide, true);
		}
	};
}
