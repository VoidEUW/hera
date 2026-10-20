<script lang="ts">
	/**
	 * A button that opens the file chooser: the composer's attach, Account's picture, a provider's
	 * logo. The native file input is kept here, hidden, so no screen draws the platform's own
	 * "Choose file · No file chosen" control beside a button that looks like Hera's.
	 *
	 * With children it is a `Button`; without, a round bordered `IconButton` — the composer's +.
	 */
	import type { Snippet } from 'svelte';
	import type { IconName } from '$lib/icons';
	import Button from './Button.svelte';
	import IconButton from './IconButton.svelte';

	interface Props {
		icon?: IconName;
		label: string;
		accept?: string;
		multiple?: boolean;
		size?: 'sm' | 'md';
		disabled?: boolean;
		onfiles: (files: FileList) => void;
		children?: Snippet;
	}

	let {
		icon = 'plus',
		label,
		accept,
		multiple = false,
		size = 'md',
		disabled = false,
		onfiles,
		children
	}: Props = $props();

	let input = $state<HTMLInputElement | null>(null);

	function picked(event: Event & { currentTarget: HTMLInputElement }) {
		const files = event.currentTarget.files;
		if (files?.length) onfiles(files);
		// Cleared so choosing the same file twice in a row still fires a change event.
		event.currentTarget.value = '';
	}
</script>

{#if children}
	<Button {icon} {size} {disabled} onclick={() => input?.click()}>{@render children()}</Button>
{:else}
	<IconButton {icon} {label} bordered {disabled} onclick={() => input?.click()} />
{/if}
<input
	bind:this={input}
	class="sr-only"
	type="file"
	{accept}
	{multiple}
	tabindex="-1"
	aria-hidden="true"
	onchange={picked}
/>
