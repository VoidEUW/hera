<script lang="ts">
	/**
	 * A checkbox or a switch (the theme's `hera/toggles`), with an optional label and a second,
	 * quieter line under it.
	 *
	 * `switch` is for a setting that takes effect the moment it is flipped; `box` for a choice that
	 * is part of something you will save or send. Both are the same native input underneath, laid
	 * invisibly over the drawn `Toggle`, so keyboard, screen reader and pointer all reach the real
	 * control. Focus is the global laurel ring, drawn on the picture the input covers.
	 */
	import Toggle from './Toggle.svelte';

	interface Props {
		/** One-way: the caller owns the value and gets `onchange` back. */
		checked: boolean;
		/** The text beside the toggle, and its accessible name unless `ariaLabel` is given. */
		label?: string;
		/** A second line under the label: what the setting does. */
		description?: string;
		ariaLabel?: string;
		disabled?: boolean;
		variant?: 'box' | 'switch';
		onchange?: (checked: boolean) => void;
	}

	let {
		checked,
		label = '',
		description = '',
		ariaLabel = '',
		disabled = false,
		variant = 'box',
		onchange
	}: Props = $props();
</script>

<label class="control" class:disabled>
	<span class="hit">
		<input
			type="checkbox"
			role={variant === 'switch' ? 'switch' : undefined}
			{checked}
			{disabled}
			aria-label={ariaLabel || undefined}
			onchange={(event) => onchange?.(event.currentTarget.checked)}
		/>
		<Toggle kind={variant} on={checked} />
	</span>
	{#if label}
		<span class="text">
			{label}
			{#if description}<small>{description}</small>{/if}
		</span>
	{/if}
</label>

<style>
	.control {
		display: inline-flex;
		align-items: center;
		gap: 9px;
		color: var(--text);
		font-size: 13px;
		cursor: pointer;
	}

	.disabled {
		cursor: not-allowed;
		opacity: 0.45;
	}

	.hit {
		position: relative;
		display: inline-flex;
		flex: none;
	}

	/* Over the drawing, not under it: the input is what the pointer, the keyboard and the screen
	   reader reach, and the picture beneath only shows what it says. */
	input {
		position: absolute;
		z-index: 1;
		inset: 0;
		width: 100%;
		height: 100%;
		margin: 0;
		opacity: 0;
		cursor: inherit;
	}

	input:focus-visible + :global(*) {
		outline: var(--focus-width) solid var(--laurel);
		outline-offset: 2px;
	}

	small {
		display: block;
		color: var(--text-faint);
		font-size: 11.5px;
	}
</style>
