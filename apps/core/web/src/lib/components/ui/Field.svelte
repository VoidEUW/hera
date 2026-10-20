<script lang="ts">
	/**
	 * The frame around a text field (the theme's `hera/text-field`, `.fld`): a label at text weight
	 * above, the control, and a help line under it that an error replaces — the reason, in
	 * `--danger`. `Input`, `NumberField` and `Textarea` draw it when they are given a label, help
	 * or an error; without any of those a field is just its control.
	 */
	import type { Snippet } from 'svelte';

	interface Props {
		id: string;
		label?: string;
		help?: string;
		error?: string;
		/** Right-aligned on the help line: a textarea's counter. */
		aside?: Snippet;
		children: Snippet;
	}

	let { id, label, help, error, aside, children }: Props = $props();
</script>

<div class="field" class:error={Boolean(error)}>
	{#if label}<label for={id}>{label}</label>{/if}
	{@render children()}
	{#if error || help || aside}
		<span class="help" id="{id}-help">
			<span>{error || help}</span>
			{#if aside}{@render aside()}{/if}
		</span>
	{/if}
</div>

<style>
	.field {
		display: flex;
		flex-direction: column;
		gap: 6px;
		min-width: 0;
	}

	label {
		color: var(--text);
		font-size: 12px;
		font-weight: 500;
	}

	.help {
		display: flex;
		justify-content: space-between;
		gap: 8px;
		color: var(--text-faint);
		font-size: 11.5px;
	}

	.error .help {
		color: var(--danger);
	}

	.error :global(:is(input, textarea)) {
		border-color: var(--danger);
	}
</style>
