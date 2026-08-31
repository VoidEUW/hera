<script lang="ts">
	/**
	 * Take it off her hands and onto yours.
	 *
	 * The download control on an artifact card and in the drawer. A **tray** with something
	 * dropping into it — the thing an artifact becomes when it stops being a panel on a screen and
	 * turns into a file in your downloads folder.
	 *
	 * Drawn in the same hand as the stele it sits beside, and in the same weight, so a row of two
	 * marks reads as one row rather than as a glyph next to an icon from somewhere else. It takes
	 * its colour from the control it is in rather than setting one, because it is a button's
	 * label and not a subject: it has to go faint with the button and warm with the hover.
	 */
	interface Props {
		size?: number;
	}

	let { size = 13 }: Props = $props();
</script>

<svg
	class="tray"
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
	<!-- The fall, then the tray it lands in. The stem stops short of the arrowhead's join so the
	     two do not thicken into a blob at 13 px. -->
	<path d="M8 2.6v6.6" />
	<path d="M5.2 6.8 8 9.6l2.8-2.8" />
	<path d="M2.8 11.2v1.4a.8.8 0 0 0 .8.8h8.8a.8.8 0 0 0 .8-.8v-1.4" />
</svg>

<style>
	.tray {
		display: block;
	}
</style>
