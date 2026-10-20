<script lang="ts">
	/**
	 * A person, as a picture or an initial (the theme's `hera/chips`, the avatar part). The
	 * initial is the first letter of the name; a nameless account is the `user` icon rather than
	 * an empty disc, which reads as something that failed to load.
	 */
	import type { IconName } from '$lib/icons';
	import Icon from './Icon.svelte';

	interface Props {
		name?: string;
		/** A data or same-origin URL. */
		src?: string;
		size?: number;
		/** Drawn instead of an initial — a skill that failed to load. */
		icon?: IconName;
	}

	let { name = '', src, size = 28, icon }: Props = $props();

	/** By code point, not by UTF-16 unit, so a skill whose mark is an emoji shows the emoji. */
	const initial = $derived(([...name.trim()][0] ?? '').toUpperCase());
</script>

<span class="avatar" style:--diameter="{size}px" aria-hidden="true">
	{#if src}
		<img {src} alt="" />
	{:else if icon}
		<Icon name={icon} size="calc(var(--diameter) * 0.55)" />
	{:else if initial}
		{initial}
	{:else}
		<Icon name="user" size="calc(var(--diameter) * 0.6)" />
	{/if}
</span>

<style>
	.avatar {
		display: inline-grid;
		flex: none;
		place-items: center;
		width: var(--diameter);
		height: var(--diameter);
		overflow: hidden;
		border: var(--border-width) solid var(--line);
		border-radius: 50%;
		background: var(--surface-raised);
		color: var(--text-muted);
		font-family: var(--font-ui);
		font-size: calc(var(--diameter) * 0.43);
		font-weight: 600;
	}

	img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}
</style>
