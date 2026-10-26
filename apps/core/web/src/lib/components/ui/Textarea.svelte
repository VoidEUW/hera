<script lang="ts">
	/**
	 * A text field for more than a line (the theme's `hera/textarea`): the same open frame as
	 * `Input` — transparent, outlined, a laurel underline on focus (`field.focus`) — taller, with a
	 * counter when there is a limit. With a `label`, `help` or `error` it is drawn inside a `Field`.
	 *
	 * `prose` sets it in the body face at reading size: the message editor, where what you type is
	 * the same text that will be read back as a bubble. `mono` is for a prompt or a SKILL.md.
	 *
	 * `bare` drops the frame entirely — the composer's field, where the composer is the frame — and
	 * grows with its content up to `grow` pixels, so a long message is visible without the field
	 * taking the whole screen.
	 */
	import { t } from '$lib/i18n';
	import { noAutofill } from '$lib/noAutofill';
	import Field from './Field.svelte';

	interface Props {
		value: string;
		placeholder?: string;
		rows?: number;
		/** Shows a counter and stops input at the limit. */
		maxlength?: number;
		mono?: boolean;
		prose?: boolean;
		resizable?: boolean;
		label?: string;
		help?: string;
		error?: string;
		ariaLabel?: string;
		disabled?: boolean;
		autofocus?: boolean;
		bare?: boolean;
		/** Grow with the content up to this many pixels. */
		grow?: number;
		ref?: HTMLTextAreaElement | null;
		onchange?: (value: string) => void;
		onkeydown?: (event: KeyboardEvent) => void;
	}

	let {
		value,
		placeholder = '',
		rows = 4,
		maxlength,
		mono = false,
		prose = false,
		resizable = true,
		label,
		help,
		error,
		ariaLabel = '',
		disabled = false,
		autofocus = false,
		bare = false,
		grow,
		ref = $bindable(),
		onchange,
		onkeydown
	}: Props = $props();

	$effect(() => {
		if (!ref || !grow) return;
		void value;
		ref.style.height = 'auto';
		ref.style.height = `${Math.min(ref.scrollHeight, grow)}px`;
	});

	const id = $props.id();

	function takeover(node: HTMLTextAreaElement) {
		if (autofocus) node.focus();
	}
</script>

{#snippet counter()}
	{#if maxlength}
		<span class="counter" aria-live="polite">
			{value.length} / {maxlength}<span class="sr-only"> {t.ui.characters}</span>
		</span>
	{/if}
{/snippet}

{#snippet control()}
	<textarea
		bind:this={ref}
		{id}
		class="control"
		class:mono
		class:prose
		class:bare
		class:resizable={resizable && !bare}
		{value}
		{placeholder}
		rows={bare ? 1 : rows}
		{maxlength}
		{disabled}
		aria-label={ariaLabel || undefined}
		aria-invalid={error ? true : undefined}
		use:takeover
		oninput={(event) => onchange?.(event.currentTarget.value)}
		{onkeydown}
		{...noAutofill}></textarea>
{/snippet}

{#if bare}
	{@render control()}
{:else}
	<Field {id} {label} {help} {error} aside={maxlength ? counter : undefined}>
		{@render control()}
	</Field>
{/if}

<style>
	.control {
		width: 100%;
		min-height: 92px;
		padding: 9px 11px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: transparent;
		color: var(--text);
		font-family: var(--font-ui);
		font-size: 13px;
		line-height: 1.5;
		resize: none;
		outline: none;
		box-shadow: inset 0 0 0 transparent;
		transition:
			box-shadow var(--motion-field-focus),
			border-color var(--motion-field-focus);
	}

	.resizable {
		resize: vertical;
	}

	.mono {
		font-family: var(--font-mono);
		font-size: 12.5px;
	}

	.prose {
		min-height: 84px;
		font-family: var(--font-body);
		font-size: calc(var(--prose-size) - 1px);
	}

	.control::placeholder {
		color: var(--text-faint);
	}

	.control:focus-visible {
		box-shadow: inset 0 -2px 0 var(--laurel);
	}

	.control:disabled {
		background: var(--ground);
		color: var(--text-faint);
		cursor: not-allowed;
	}

	.bare {
		flex: 1;
		min-width: 0;
		min-height: 26px;
		padding: 2px 0;
		overflow: auto;
		border: 0;
		background: none;
		font-family: var(--font-body);
		font-size: 16px;
		box-shadow: none;
	}

	.bare:focus-visible {
		box-shadow: none;
	}

	.bare:disabled {
		background: none;
	}

	.counter {
		font-variant-numeric: tabular-nums;
	}

	/* iOS zooms the whole page into a field whose text is under 16px, and does not zoom back
	   out (#41). So on a phone a field's text is 16px. */
	@media (max-width: 780px) {
		.control,
		.mono {
			font-size: 16px;
		}

		/* Already above the line, and set larger on purpose. */
		.prose {
			font-size: calc(var(--prose-size) - 1px);
		}
	}
</style>
