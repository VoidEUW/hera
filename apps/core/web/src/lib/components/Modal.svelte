<script lang="ts">
	/**
	 * One modal shell for every sheet in the application (#99).
	 *
	 * The four sheets this replaces — Settings, ServerSheet, SkillPicker, ProfileMenu — each
	 * carried their own copy of the scrim / sheet / Escape pattern, and the comments in each said
	 * so. This is that copy, once.
	 *
	 * What it owns:
	 *
	 * - the scrim and the click-on-it that closes,
	 * - `role="dialog"` + `aria-modal`, and an accessible name,
	 * - Escape, which is the first step of #112's "one Escape" — it moves in here so every
	 *   sheet gets it without carrying its own `svelte:window`,
	 * - focus: saved on open, returned to the opener on close,
	 * - the close button — a real control rather than a 12px `\u2715` glyph in a plain button:
	 *   a hairline circle with a 32px hit area, hover and focus states.
	 *
	 * What it does not own: the body. A sheet is its content; the shell only frames it.
	 */
	import { t } from '$lib/i18n';

	interface Props {
		/** The accessible name of the dialog. Not drawn — the header carries a visible title. */
		label: string;
		/** The visible title, drawn in the header beside the close button. An empty string hides
		 * the header entirely — a sheet with no title (the profile menu) does not want a bar of
		 * chrome above it. */
		title?: string;
		/** A caption under the title. Settings and the sheets have one; the menu does not. */
		caption?: string;
		/** Called on Escape, on the scrim, and on the close button. The parent decides what
		 * closing means; this shell only reports the intent. Optional, because a sheet whose
		 * only exit is its own controls (the profile menu before #102) still wants the shell. */
		onclose?: () => void;
		/** Draw the close control when there is no title to hang it beside. A titled sheet
		 * always has one; a bare sheet (the profile menu) draws a small floating one, because
		 * #99's rule is that every sheet closes with a real control, not a 12px glyph. */
		closeButton?: boolean;
		/** Where the sheet sits. `centre` is Settings; `docked` is the composer-adjacent sheets
		 * (ServerSheet, SkillPicker), which hang 96px from the bottom so the composer stays
		 * visible under them; `anchored` is the profile menu, which pins to the bottom-left
		 * above the profile card. */
		placement?: 'centre' | 'docked' | 'anchored';
		/** The scrim's own dimming. `true` (default) is the ordinary darkened scrim; `false` is
		 * the profile menu's transparent catcher, which closes on click without claiming the
		 * conversation behind it is unavailable. */
		dim?: boolean;
		/** The width of the sheet. Pass a CSS min() expression; the shell does not guess what
		 * fits. */
		width?: string;
		/** Class passed through to the sheet element, so a caller can size it from its own
		 * scoped styles without :global(). */
		sheetclass?: string;
		children?: import('svelte').Snippet;
	}

	let {
		label,
		title = '',
		caption = '',
		onclose,
		closeButton = true,
		placement = 'centre',
		dim = true,
		width = 'min(520px, 92vw)',
		sheetclass = '',
		children
	}: Props = $props();

	/** Where focus was when the sheet opened — the trigger that opened it, usually. Returned
	 * on close, because a control that takes focus away and keeps it is a control that has
	 * stranded a keyboard user. Captured on mount rather than trusted to the caller: the caller
	 * knows *whether* to open a sheet, not where focus happens to be when it does. */
	let opener = $state<HTMLElement | null>(null);
	let sheet = $state<HTMLDivElement | null>(null);

	$effect(() => {
		opener = document.activeElement as HTMLElement | null;
		// The sheet exists to be interacted with, so it takes focus on open — a dialog that
		// does not is a dialog a keyboard user has to tab into.
		const first =
			sheet?.querySelector<HTMLElement>(
				'input, button:not(.close), select, textarea, [href], [tabindex]:not([tabindex="-1"])'
			) ?? sheet;
		first?.focus();
		return () => opener?.focus?.();
	});

	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			// One Escape does one thing (#112's rule, arriving early). If a Select dropdown is open
			// inside the sheet, closing it is what this Escape is for — the modal is the layer
			// underneath it, and closing both at once is the double-close the dropdown's own
			// handler used to race. Select owns its Escape through `svelte:window` too, so the
			// check is on the DOM: an open dropdown is a `role="listbox"` that Select rendered.
			const dropdown = sheet?.querySelector('[role="listbox"]');
			if (dropdown) return;
			close();
			return;
		}
		if (event.key === 'Tab') {
			// `aria-modal` is a promise that nothing outside the sheet is reachable, and Tab is
			// where that promise is kept: forward from the last focusable wraps to the first,
			// reverse from the first wraps to the last. Without this the browser happily tabs
			// into the conversation behind the scrim, which is exactly what `aria-modal` said
			// could not happen. (#121 is the same bug in the rail's sheet.)
			const focusable = [
				...(sheet?.querySelectorAll<HTMLElement>(
					'input:not([disabled]), button:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
				) ?? [])
			].filter((el) => el.offsetParent !== null);
			if (!focusable.length) return;
			const first = focusable[0];
			const last = focusable[focusable.length - 1];
			const here = document.activeElement;
			if (event.shiftKey) {
				if (here === first || here === sheet) {
					event.preventDefault();
					last.focus();
				}
			} else if (here === last) {
				event.preventDefault();
				first.focus();
			}
		}
	}

	/** Every exit from the shell is this one function, so a caller overriding one behaviour
	 * (the profile menu closing on an outside click, say) can watch a single seam. */
	function close() {
		onclose?.();
	}

	/** A click outside the sheet closes it — including the click that lands on a Select's
	 * away-overlay, which sits above the scrim and swallows the event before the scrim's own
	 * handler can see it. When a dropdown is open, the click *is* the dropdown's to consume —
	 * the first click closes the dropdown, the second closes the sheet, which is the same
	 * one-gesture-one-effect rule Escape follows above.
	 *
	 * Attached with `addEventListener` in an `$effect` rather than through `<svelte:window
	 * onclick>`: Svelte 5 routes element events through delegation at the document root, and
	 * a window-level `onclick` compiled into the same dispatch interferes with it — observed
	 * as the sheet that never mounts, because the click that opened it was swallowed on the
	 * way to the delegated handlers that flip the state. A listener added after mount, in the
	 * bubble phase, sees only clicks that happen while the sheet is on screen.
	 *
	 * The opener's own click is excluded by the arm frame below, not by attach order. */
	$effect(() => {
		// The listener is armed one frame late: Svelte 5 flushes the mount effects for an
		// event-driven render synchronously inside that event's dispatch, so a listener attached
		// here would already see the opener's click still bubbling and close the sheet it just
		// opened. One animation frame is past the whole dispatch, and no human click lands in it.
		let armed = false;
		const arm = requestAnimationFrame(() => (armed = true));
		const away = (event: MouseEvent) => {
			if (!armed) return;
			// The propagation path rather than a captured `sheet` reference: the sheet that is
			// live at event time is the only one that can answer `contains`, and a listener that
			// outlived its own instance (a tab switch can unmount and remount Settings within one
			// synchronous flush) would otherwise hold a detached node and close the modal on a
			// click that landed squarely inside the new one. Any dialog on the path means the
			// click was consumed by a sheet — this one or a nested one.
			const path = event.composedPath();
			if (
				path.some((node) => node instanceof HTMLElement && node.getAttribute('role') === 'dialog')
			)
				return;
			if (sheet?.querySelector('[role="listbox"]')) return;
			close();
		};
		window.addEventListener('click', away);
		return () => {
			cancelAnimationFrame(arm);
			window.removeEventListener('click', away);
		};
	});
</script>

<svelte:window {onkeydown} />

<div class="scrim" class:clear={!dim} role="presentation"></div>

<div
	bind:this={sheet}
	class="sheet {placement} {sheetclass}"
	style="--modal-width: {width}"
	role="dialog"
	aria-modal="true"
	aria-label={label}
	tabindex="-1"
>
	{#if title || caption}
		<header>
			<div>
				{#if title}<h2 class="display">{title}</h2>{/if}
				{#if caption}<p class="caption">{caption}</p>{/if}
			</div>
			<button class="close" type="button" onclick={close}>
				<span class="sr-only">{t.settings.close}</span>
				<span class="glyph" aria-hidden="true"></span>
			</button>
		</header>
	{:else if closeButton}
		<!-- A sheet with no title still closes with a real control (#99): the profile menu
	         hides its chrome but not its way out. -->
		<button class="close floating" type="button" onclick={close}>
			<span class="sr-only">{t.settings.close}</span>
			<span class="glyph" aria-hidden="true"></span>
		</button>
	{/if}
	{#if children}
		{@render children()}
	{/if}
</div>

<style>
	/* The scrim. `role="presentation"` rather than the `role="button"` the four copies used:
	 * a scrim is not a control, it is the absence of one, and the close button and Escape are
	 * the two ways out that a keyboard user has. */
	.scrim {
		position: fixed;
		inset: 0;
		background: rgb(0 0 0 / 0.45);
		animation: fade var(--fade) var(--ease);
		z-index: 10;
	}

	.scrim.clear {
		background: none;
	}

	.sheet {
		position: fixed;
		display: flex;
		flex-direction: column;
		background: var(--surface-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow);
		overflow: hidden;
		z-index: 11;
		animation: fade var(--fade) var(--ease);
		width: var(--modal-width);
	}

	/* Centred by insets and auto margins rather than by `transform: translate(...)`, because
	 * a transform makes the sheet the containing block for its descendants' `position: fixed`
	 * elements — and `Select.svelte`'s away-overlay is exactly that. Under a transformed sheet
	 * the overlay covered only the sheet itself, so a click beside it fell through to the
	 * scrim and closed the whole modal instead of the dropdown, and Escape closed both at
	 * once. Insets and margins centre the same way and leave containing blocks where the spec
	 * puts them.
	 *
	 * `centre` needs a definite height from the caller (`sheetclass`), which Settings already
	 * gives it; without one the over-constrained insets stretch the sheet to the viewport. */
	.sheet.centre {
		inset: 0;
		margin: auto;
	}

	.sheet.docked {
		left: 0;
		right: 0;
		bottom: 96px;
		margin-inline: auto;
		max-height: 60vh;
	}

	.sheet.anchored {
		left: 12px;
		bottom: 76px;
		max-height: 70vh;
		overflow-y: auto;
		animation: rise var(--fade) var(--ease);
	}

	@keyframes fade {
		from {
			opacity: 0;
		}
	}

	@keyframes rise {
		from {
			opacity: 0;
			transform: translateY(4px);
		}
	}

	header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 16px;
		padding: 16px 20px;
		border-bottom: 1px solid var(--line);
		flex: none;
	}

	h2 {
		margin: 0;
		font-size: 18px;
	}

	header .caption {
		margin: 2px 0 0;
		max-width: 46ch;
	}

	/* The close button — the reason this component exists. A 32px hit area (the minimum for a
	 * comfortable touch target), a hairline circle that colours on hover and focus, and the
	 * glyph drawn as two crossing hairlines rather than a text \u2715, which is a font's own idea of
	 * the shape and differs between the fonts. */
	.close {
		display: flex;
		align-items: center;
		justify-content: center;
		flex: none;
		width: 32px;
		height: 32px;
		padding: 0;
		background: none;
		border: 1px solid var(--line);
		border-radius: 50%;
		color: var(--text-muted);
		transition:
			border-color var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	.close:hover,
	.close:focus-visible {
		border-color: var(--brass);
		color: var(--brass);
	}

	.close:active {
		transform: scale(0.95);
	}

	/* A bare sheet's close control: same circle, smaller and pinned to the sheet's own
	   top-right corner rather than sitting in a header bar that does not exist. */
	.close.floating {
		position: absolute;
		top: 6px;
		right: 6px;
		width: 26px;
		height: 26px;
		z-index: 1;
		background: var(--surface-raised);
	}

	/* Two hairlines crossing at the centre: one shape, no font, and it takes the colour of the
	 * button like everything else here. */
	.glyph {
		position: relative;
		width: 10px;
		height: 10px;
	}

	.glyph::before,
	.glyph::after {
		content: '';
		position: absolute;
		top: 50%;
		left: 50%;
		width: 12px;
		height: 1.5px;
		background: currentcolor;
		border-radius: 1px;
	}

	.glyph::before {
		transform: translate(-50%, -50%) rotate(45deg);
	}

	.glyph::after {
		transform: translate(-50%, -50%) rotate(-45deg);
	}

	/* The sr-only utility, here rather than imported, because it is three lines and every
	 * import chain should not be able to reach it. */
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
		border: 0;
	}
</style>
