<script lang="ts">
	/**
	 * One icon from the set in `$lib/icons` — the only component that draws one (ADR 21).
	 *
	 * Size and stroke are the theme's (`--icon-size`, `--icon-stroke`), colour is the text it sits
	 * in, so an icon in a danger button is a danger icon without being told. `size` is for the few
	 * places that need a different one — a mark beside a display title — and takes a CSS length,
	 * so `calc()` against the token is still a token.
	 *
	 * Decorative by default: next to a word the word is the label, and an icon that is read out as
	 * well says it twice. Give it a `label` when it stands alone.
	 */
	import { ICONS, type IconName } from '$lib/icons';

	interface Props {
		name: IconName;
		size?: string;
		label?: string;
	}

	let { name, size, label }: Props = $props();
</script>

<svg
	class="icon"
	viewBox="0 0 24 24"
	style:--size={size}
	role={label ? 'img' : undefined}
	aria-label={label}
	aria-hidden={label ? undefined : 'true'}
>
	{#each ICONS[name] as [tag, attributes], index (index)}
		<svelte:element this={tag} xmlns="http://www.w3.org/2000/svg" {...attributes} />
	{/each}
</svg>

<style>
	.icon {
		width: var(--size, var(--icon-size));
		height: var(--size, var(--icon-size));
		flex: none;
		fill: none;
		stroke: currentColor;
		/* The stroke is specified on the 24-unit grid; `vector-effect` would keep it in screen
		   pixels instead, which thickens a small icon and thins a large one. */
		stroke-width: var(--icon-stroke);
		stroke-linecap: var(--icon-linecap);
		stroke-linejoin: var(--icon-linejoin);
	}
</style>
