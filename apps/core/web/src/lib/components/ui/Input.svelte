<script lang="ts">
	/**
	 * One text field, typed by what it holds (the theme's `hera/text-field`, open look):
	 * transparent, outlined, and on focus a 2px laurel underline drawn inside the bottom edge
	 * (`field.focus`) — focus is her attention, so it is laurel, and drawn inside so it moves
	 * nothing. With a `label`, `help` or `error` it is drawn inside a `Field`.
	 *
	 * `kind` is a closed set, so a URL field cannot become a password field through a typo, and the
	 * flags that keep a password manager from treating a settings screen as a login live in one
	 * place (`$lib/noAutofill`). A filter is a `SearchBar`, a number a `NumberField`.
	 *
	 * `inline` is the sidebar's in-place rename: shorter, on the ground, its border already laurel,
	 * because the field replacing a title *is* the edit rather than a control that starts one.
	 */
	import { noAutofill } from '$lib/noAutofill';
	import Field from './Field.svelte';

	interface Props {
		kind?: 'text' | 'url' | 'password' | 'email';
		value: string;
		placeholder?: string;
		variant?: 'field' | 'inline';
		/** The monospace face — an id or a URL, not a sentence. */
		mono?: boolean;
		label?: string;
		help?: string;
		error?: string;
		/** A name for the field — a handle for a test, never a style. */
		class?: string;
		ariaLabel?: string;
		disabled?: boolean;
		/** Takes focus and selects its contents the instant it mounts. */
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
		label,
		help,
		error,
		class: extra = '',
		ariaLabel = '',
		disabled = false,
		autofocus = false,
		onchange,
		onblur,
		onkeydown
	}: Props = $props();

	const id = $props.id();
	const framed = $derived(Boolean(label || help || error));

	function takeover(node: HTMLInputElement) {
		if (!autofocus) return;
		node.focus();
		node.select();
	}
</script>

{#snippet control()}
	<input
		{id}
		class="control {variant} {extra}"
		class:mono
		type={kind}
		{value}
		{placeholder}
		{disabled}
		aria-label={ariaLabel || undefined}
		aria-invalid={error ? true : undefined}
		aria-describedby={help || error ? `${id}-help` : undefined}
		{...noAutofill}
		use:takeover
		oninput={(event) => onchange?.(event.currentTarget.value)}
		{onblur}
		{onkeydown}
	/>
{/snippet}

{#if framed}
	<Field {id} {label} {help} {error}>{@render control()}</Field>
{:else}
	{@render control()}
{/if}

<style>
	.control {
		width: 100%;
		height: calc(var(--space) * 9);
		padding: 0 11px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: transparent;
		color: var(--text);
		font-family: var(--font-ui);
		font-size: 13px;
		outline: 0;
		box-shadow: inset 0 0 0 transparent;
		transition:
			box-shadow var(--motion-field-focus),
			border-color var(--motion-field-focus);
	}

	.control::placeholder {
		color: var(--text-faint);
	}

	.mono {
		font-family: var(--font-mono);
		font-size: 12.5px;
	}

	.control:disabled {
		background: var(--ground);
		color: var(--text-faint);
		cursor: not-allowed;
	}

	.control:focus-visible {
		outline: none;
		box-shadow: inset 0 -2px 0 var(--laurel);
	}

	.control[aria-invalid='true']:focus-visible {
		box-shadow: inset 0 -2px 0 var(--danger);
	}

	.inline {
		height: calc(var(--space) * 7.5);
		padding: 0 8px;
		border-color: var(--laurel);
		background: var(--ground);
	}

	.inline:focus-visible {
		box-shadow: none;
	}

	/* iOS zooms the whole page into a field whose text is under 16px, and does not zoom back
	   out (#41). So on a phone a field's text is 16px. */
	@media (max-width: 780px) {
		.control,
		.mono {
			font-size: 16px;
		}
	}
</style>
