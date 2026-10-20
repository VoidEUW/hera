<script lang="ts">
	/**
	 * A person, as a picture or an initial (the theme's `hera/chips`, the avatar part). The
	 * initial is the first letter of the name; a nameless account is the `user` icon rather than
	 * an empty disc, which reads as something that failed to load.
	 */
	import Icon from './Icon.svelte';

	interface Props {
		name?: string;
		/** A data or same-origin URL. */
		src?: string;
		size?: number;
	}

	let { name = '', src, size = 28 }: Props = $props();

	const initial = $derived(name.trim().charAt(0).toUpperCase());
</script>

<span class="avatar" style:--diameter="{size}px" aria-hidden="true">
	{#if src}
		<img {src} alt="" />
	{:else if initial}
		{initial}
	{:else}
		<Icon name="user" size="calc(var(--diameter) * 0.6)" />
	{/if}
</span>

<style>
	.avatar {
		display: inline-grid;
		place-items: center;
		flex: none;
		width: var(--diameter);
		height: var(--diameter);
		overflow: hidden;
		border-radius: 50%;
		background: var(--brass-soft);
		color: var(--brass);
		font-family: var(--font-ui);
		font-size: calc(var(--diameter) * 0.45);
		font-weight: 600;
	}

	img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
</style>
