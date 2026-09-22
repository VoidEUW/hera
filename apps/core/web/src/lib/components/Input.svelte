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
	class="control {variant}"
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
	   the `<label>` wrapper around a `Checkbox`, and the two must never collide. */
	.control {
		width: 100%;
		padding: 7px 10px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-family: var(--font-ui);
		font-size: 13px;
		color: var(--text);
		transition: border-color var(--fade) var(--ease);
	}

	.control.mono {
		font-family: var(--font-mono);
	}

	.control:disabled {
		cursor: default;
		opacity: 0.5;
	}

	.control:focus-visible {
		outline: none;
		border-color: var(--brass);
		box-shadow: 0 0 0 2px rgb(217 174 82 / 0.25);
	}

	/* The rail's in-place rename: the brass border is the edit state itself, not a focus ring on
	   top of one, so there is nothing extra to draw on focus. */
	.control.inline {
		padding: 6px 8px;
		background: var(--ground);
		border-color: var(--brass);
		font-size: 13.5px;
	}

	.control.inline:focus-visible {
		box-shadow: none;
	}

	/* The memory editor's paragraph field — matches `.editor textarea` beside it, which this
	   component does not own, exactly: ground, brass only once focused, no ring. */
	.control.editor {
		padding: 6px 8px;
		background: var(--ground);
	}

	.control.editor:focus-visible {
		box-shadow: none;
	}
</style>
