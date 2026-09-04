<script lang="ts">
	/**
	 * The backdrop — her silhouette behind the work (issue #43). The drawing lives at
	 * static/background.svg and is intentionally a placeholder: it is applied as a mask
	 * and tinted by --backdrop-tint, so dropping the real artwork onto that same path
	 * changes nothing else in the interface.
	 *
	 * The element is pinned to the bottom of its parent and kept beneath the content with
	 * a negative z-index; the parent isolates itself so the figure lands between the room's
	 * own ground colour and everything drawn on top of it.
	 */
	interface Props {
		/** How far the figure rises up the room, as a height of the parent. */
		height?: string;
	}

	let { height = '82%' }: Props = $props();
</script>

<div class="backdrop" aria-hidden="true" style="--backdrop-height: {height}"></div>

<style>
	.backdrop {
		position: absolute;
		inset: 0;
		z-index: -1;
		pointer-events: none;
		user-select: none;
		/* A whisper of the reading colour rather than a drawing of her: present, never busy. */
		background-color: var(--backdrop-tint, var(--text-muted));
		opacity: var(--backdrop-opacity, 0.055);
		-webkit-mask-image: url('/background.svg');
		mask-image: url('/background.svg');
		-webkit-mask-repeat: no-repeat;
		mask-repeat: no-repeat;
		-webkit-mask-position: center bottom;
		mask-position: center bottom;
		-webkit-mask-size: auto var(--backdrop-height);
		mask-size: auto var(--backdrop-height);
	}
</style>
