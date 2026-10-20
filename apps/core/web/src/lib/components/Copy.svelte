<script lang="ts">
	/**
	 * Two sheets, one behind the other — or, once it has been done, a tick.
	 *
	 * The copy control on a code view. Same hand and weight as `Tray` and the stele, and it takes
	 * its colour from the button it is in for the same reason: it is a label, not a subject.
	 */
	interface Props {
		size?: number;
		/** Show the tick instead: what the button says for a moment after it has worked. */
		done?: boolean;
	}

	let { size = 13, done = false }: Props = $props();
</script>

<svg
	class="copy"
	width={size}
	height={size}
	viewBox="0 0 16 16"
	fill="none"
	stroke="currentColor"
	stroke-width="1.4"
	stroke-linecap="round"
	stroke-linejoin="round"
	aria-hidden="true"
>
	{#if done}
		<path d="M3.4 8.6 6.6 11.8 12.6 4.6" />
	{:else}
		<rect x="5.6" y="5.6" width="7.6" height="8" rx="1.2" />
		<path d="M10.4 3.4v-.2a.8.8 0 0 0-.8-.8H3.6a.8.8 0 0 0-.8.8v7.6a.8.8 0 0 0 .8.8h.2" />
	{/if}
</svg>

<style>
	.copy {
		display: block;
	}
</style>
