<script lang="ts">
	/**
	 * A text field for more than a line (the theme's `hera/textarea`): the same open frame as
	 * `Input` — transparent, outlined, a laurel underline on focus (`field.focus`) — taller, with
	 * an optional counter when there is a limit.
	 *
	 * Same contract as `Input`: the value comes in, changes go out through `onchange`, so the
	 * caller owns the state and a half-typed draft is never written behind its back.
	 */
	import { t } from '$lib/i18n';
	import { noAutofill } from '$lib/noAutofill';

	interface Props {
		value: string;
		placeholder?: string;
		rows?: number;
		/** Shows a counter and stops input at the limit. */
		maxlength?: number;
		/** The monospace face — a prompt or a SKILL.md, not a sentence. */
		mono?: boolean;
		resizable?: boolean;
		ariaLabel?: string;
		disabled?: boolean;
		onchange?: (value: string) => void;
		onkeydown?: (event: KeyboardEvent) => void;
	}

	let {
		value,
		placeholder = '',
		rows = 4,
		maxlength,
		mono = false,
		resizable = true,
		ariaLabel = '',
		disabled = false,
		onchange,
		onkeydown
	}: Props = $props();
</script>

<div class="field" class:resizable>
	<textarea
		class="control"
		class:mono
		{value}
		{placeholder}
		{rows}
		{maxlength}
		{disabled}
		aria-label={ariaLabel || undefined}
		oninput={(event) => onchange?.(event.currentTarget.value)}
		{onkeydown}
		{...noAutofill}></textarea>
	{#if maxlength}
		<span class="counter" aria-live="polite">
			{value.length} / {maxlength}
			<span class="sr-only">{t.ui.characters}</span>
		</span>
	{/if}
</div>

<style>
	.field {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: calc(var(--space) * 1);
	}

	.control {
		width: 100%;
		min-height: calc(var(--space) * 18);
		padding: calc(var(--space) * 2) calc(var(--space) * 3);
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: transparent;
		color: var(--text);
		font-family: var(--font-ui);
		font-size: var(--ui-size);
		line-height: 1.5;
		resize: none;
		outline: none;
		/* The underline is drawn inside the bottom edge, so focus changes no geometry. */
		box-shadow: inset 0 0 0 transparent;
		transition:
			box-shadow var(--motion-field-focus),
			border-color var(--fade) var(--ease);
	}

	.resizable .control {
		resize: vertical;
	}

	.mono {
		font-family: var(--font-mono);
		font-size: calc(var(--ui-size) - 0.5px);
	}

	.control::placeholder {
		color: var(--text-faint);
	}

	.control:focus-visible {
		box-shadow: inset 0 -2px 0 var(--laurel);
	}

	.control:disabled {
		color: var(--text-faint);
		cursor: not-allowed;
	}

	.counter {
		align-self: flex-end;
		color: var(--text-faint);
		font-size: calc(var(--ui-size) - 2px);
		font-variant-numeric: tabular-nums;
	}
</style>
