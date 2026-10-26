<script lang="ts">
	/**
	 * A filter (the theme's `hera/search`, soft look): a filled rounded field with a leading
	 * magnifier, and a keyboard hint at the end that becomes a clear button once there is text.
	 * Focus turns the border laurel at once (`search.focus: none` — no transition).
	 *
	 * `shortcut` is the key that focuses it from anywhere, drawn as the hint — the caller binds the
	 * key, because only it knows whether the shortcut is free on its screen.
	 */
	import { t } from '$lib/i18n';
	import { noAutofill } from '$lib/noAutofill';
	import CloseButton from './CloseButton.svelte';
	import Icon from './Icon.svelte';
	import Kbd from './Kbd.svelte';

	interface Props {
		value: string;
		placeholder: string;
		shortcut?: string;
		ref?: HTMLInputElement | null;
		onchange: (value: string) => void;
		onkeydown?: (event: KeyboardEvent) => void;
	}

	let { value, placeholder, shortcut, ref = $bindable(), onchange, onkeydown }: Props = $props();

	function clear() {
		onchange('');
		ref?.focus();
	}
</script>

<label class="search" class:filled={value !== ''}>
	<Icon name="search" />
	<input
		bind:this={ref}
		type="search"
		{value}
		{placeholder}
		aria-label={placeholder}
		{...noAutofill}
		oninput={(event) => onchange(event.currentTarget.value)}
		onkeydown={(event) => {
			if (event.key === 'Escape' && value) {
				event.preventDefault();
				event.stopPropagation();
				onchange('');
			}
			onkeydown?.(event);
		}}
	/>
	{#if value}
		<CloseButton size="sm" label={t.ui.clearSearch} onclick={clear} />
	{:else if shortcut}
		<Kbd>{shortcut}</Kbd>
	{/if}
</label>

<style>
	.search {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		min-width: 0;
		height: calc(var(--space) * 8.5);
		padding: 0 6px 0 10px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: var(--ground);
		color: var(--text-faint);
		transition:
			box-shadow var(--motion-search-focus),
			border-color var(--motion-search-focus);
	}

	.search:focus-within {
		border-color: var(--laurel);
	}

	input {
		flex: 1;
		min-width: 0;
		height: 100%;
		border: 0;
		outline: 0;
		background: none;
		color: var(--text);
		font-size: 13px;
	}

	input::placeholder {
		color: var(--text-faint);
	}

	input::-webkit-search-cancel-button {
		appearance: none;
	}

	input:focus-visible {
		outline: none;
	}

	/* iOS zooms the whole page into a field whose text is under 16px, and does not zoom back
	   out (#41). So on a phone a field's text is 16px. */
	@media (max-width: 780px) {
		input {
			font-size: 16px;
		}
	}
</style>
