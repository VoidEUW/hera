<script lang="ts">
	/**
	 * One text field, typed by what it holds (#99).
	 *
	 * Every text-like `<input>` in a settings screen used to spread its own copy of `noAutofill`
	 * and guess its own native `type` by hand — a base URL sat in a plain `type="text"` beside an
	 * API key, which is exactly the pair a password manager reads as a login form. `kind` is a
	 * closed set rather than a string here, so a URL field cannot become a password field through
	 * a typo, and the flags that keep a password manager from treating any of them as a login live
	 * in one place (`$lib/noAutofill`) instead of at every call site.
	 *
	 * `variant` is the look, not the meaning: the settings-screen `'field'` (surface, a hairline
	 * border, a brass ring on focus) is the default. `'inline'` is the rail's in-place rename —
	 * dark ground, a brass border that does not wait for focus, because the field replacing a
	 * title *is* the edit rather than a control that starts one. `'editor'` is the memory editor's
	 * paragraph field, which sits beside a `<textarea>` this component does not own and has to
	 * match it exactly: ground, brass only once focused. Three existing looks, kept apart rather
	 * than flattened into one, because the difference was intentional in each place it was drawn.
	 */
	import { noAutofill } from '$lib/noAutofill';

	interface Props {
		/** What the field holds. Decides the native `type` and, through it, the keyboard a phone
		 * offers and the validation the browser does on its own — `'url'` for an endpoint,
		 * `'password'` for a secret, `'search'` for a filter, `'text'` for everything else. */
		kind?: 'text' | 'url' | 'password' | 'search';
		value: string;
		placeholder?: string;
		variant?: 'field' | 'inline' | 'editor';
		/** The monospace face — an id or a URL, not a sentence. */
		mono?: boolean;
		/** Appended to the component's own class list, so a caller can put a name on the field.
		 *  A name rather than a style: the look is this component's job, and the note on `.control`
		 *  below is about exactly the collisions an open class list invites. What this is for is a
		 *  handle — the rail's three in-place fields were `input.rename` before they came here, and
		 *  an end-to-end test needs one selector that says which field it means. */
		class?: string;
		ariaLabel?: string;
		disabled?: boolean;
		/** Takes focus and selects its contents the instant it mounts — the rail's rename field
		 * replacing a title in place, where leaving focus behind would leave it nowhere to be. */
		autofocus?: boolean;
		onchange?: (value: string) => void;
		onblur?: () => void;
		onkeydown?: (event: KeyboardEvent) => void;
	}

	let {
		kind = 'text',
		value,
		placeholder = '',
		variant = 'field',
		mono = false,
		class: extra = '',
		ariaLabel = '',
		disabled = false,
		autofocus = false,
		onchange,
		onblur,
		onkeydown
	}: Props = $props();

	function handle(event: Event) {
		onchange?.((event.currentTarget as HTMLInputElement).value);
	}

	function takeover(node: HTMLInputElement) {
		if (!autofocus) return;
		node.focus();
		node.select();
	}
</script>

<input
	class="control {variant} {extra}"
	class:mono
	type={kind}
	{value}
	{placeholder}
	{disabled}
	aria-label={ariaLabel || undefined}
	{...noAutofill}
	use:takeover
	oninput={handle}
	{onblur}
	{onkeydown}
/>

<style>
	/* Named `.control` rather than `.field` — a settings screen that reaches in with `:global()`
	   (`Models.svelte`'s `.add-model`, `.search`) already has its own unrelated `.field` class on
	   the `<label>` wrapper around a `Checkbox`, and the two must never collide.

	   The theme's open look: transparent, outlined, and on focus a laurel underline drawn inside
	   the bottom edge (`field.focus`) — focus is her attention, so it is laurel, and drawn inside
	   so it moves nothing. Nine density units tall. */
	.control {
		width: 100%;
		height: calc(var(--space) * 9);
		padding: 0 calc(var(--space) * 3);
		background: transparent;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		font-family: var(--font-ui);
		font-size: var(--ui-size);
		color: var(--text);
		box-shadow: inset 0 0 0 transparent;
		transition:
			box-shadow var(--motion-field-focus),
			border-color var(--fade) var(--ease);
	}

	.control::placeholder {
		color: var(--text-faint);
	}

	.control.mono {
		font-family: var(--font-mono);
		font-size: calc(var(--ui-size) - 0.5px);
	}

	.control:disabled {
		cursor: default;
		color: var(--text-faint);
	}

	.control:focus-visible {
		outline: none;
		box-shadow: inset 0 -2px 0 var(--laurel);
	}

	/* The rail's in-place rename: the brass border is the edit state itself, not a focus ring on
	   top of one, so there is nothing extra to draw on focus. */
	.control.inline {
		height: calc(var(--space) * 7.5);
		padding: 0 calc(var(--space) * 2);
		background: var(--ground);
		border-color: var(--brass);
	}

	.control.inline:focus-visible {
		box-shadow: none;
	}

	/* The memory editor's paragraph field — matches the editor textarea beside it: ground, the
	   underline only once focused. */
	.control.editor {
		background: var(--ground);
	}
</style>
