<script lang="ts">
	/**
	 * A field that holds a number (a Hera addition to `hera/text-field`): the same open frame as
	 * `Input`, in the mono face with tabular figures, and an optional unit after the number —
	 * "tokens", "s". Its own component rather than a `kind` of `Input`, because its value is a
	 * number or nothing, and an empty field means "not set", never zero.
	 */
	import Field from './Field.svelte';

	interface Props {
		value: number | null;
		min?: number;
		max?: number;
		step?: number | 'any';
		placeholder?: string;
		unit?: string;
		label?: string;
		help?: string;
		error?: string;
		ariaLabel?: string;
		disabled?: boolean;
		/** Narrow, for a number inside a row or a menu rather than a form column. */
		compact?: boolean;
		onchange?: (value: number | null) => void;
		onkeydown?: (event: KeyboardEvent) => void;
	}

	let {
		value,
		min,
		max,
		step,
		placeholder = '',
		unit,
		label,
		help,
		error,
		ariaLabel = '',
		disabled = false,
		compact = false,
		onchange,
		onkeydown
	}: Props = $props();

	const id = $props.id();
	const framed = $derived(Boolean(label || help || error));

	function read(event: Event & { currentTarget: HTMLInputElement }) {
		const raw = event.currentTarget.value.trim();
		const parsed = raw === '' ? null : Number(raw);
		onchange?.(parsed === null || Number.isNaN(parsed) ? null : parsed);
	}
</script>

{#snippet control()}
	<span class="number" class:compact>
		<input
			{id}
			type="number"
			inputmode="decimal"
			value={value ?? ''}
			{min}
			{max}
			{step}
			{placeholder}
			{disabled}
			aria-label={ariaLabel || undefined}
			aria-invalid={error ? true : undefined}
			oninput={read}
			{onkeydown}
		/>
		{#if unit}<span class="unit">{unit}</span>{/if}
	</span>
{/snippet}

{#if framed}
	<Field {id} {label} {help} {error}>{@render control()}</Field>
{:else}
	{@render control()}
{/if}

<style>
	.number {
		display: flex;
		align-items: center;
		width: 100%;
		height: calc(var(--space) * 9);
		padding: 0 11px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: transparent;
		box-shadow: inset 0 0 0 transparent;
		transition:
			box-shadow var(--motion-field-focus),
			border-color var(--motion-field-focus);
	}

	.compact {
		width: 12ch;
		height: calc(var(--space) * 7);
		padding: 0 8px;
	}

	.number:focus-within {
		box-shadow: inset 0 -2px 0 var(--laurel);
	}

	input {
		flex: 1;
		min-width: 0;
		height: 100%;
		border: 0;
		outline: 0;
		background: none;
		color: var(--text);
		font-family: var(--font-mono);
		font-size: 12.5px;
		font-variant-numeric: tabular-nums;
		appearance: textfield;
	}

	input::-webkit-inner-spin-button,
	input::-webkit-outer-spin-button {
		margin: 0;
		appearance: none;
	}

	input::placeholder {
		color: var(--text-faint);
	}

	input:disabled {
		color: var(--text-faint);
		cursor: not-allowed;
	}

	.unit {
		flex: none;
		color: var(--text-faint);
		font-size: 11.5px;
	}
</style>
