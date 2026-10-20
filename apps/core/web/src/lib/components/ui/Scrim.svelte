<script lang="ts">
	/**
	 * The dimmed ground behind a sheet (`--scrim`): a dialog, the phone's sidebar. Presentation,
	 * not a control — clicking it closes what is over it, and Escape and the close button are the
	 * ways out a keyboard has. `clear` is a transparent catcher: it closes on a click without
	 * saying the screen behind is unavailable.
	 */
	import { expoIn } from 'svelte/easing';
	import { fade } from 'svelte/transition';
	import { LEAVING, slot, still } from '$lib/motion';

	interface Props {
		clear?: boolean;
		/** The motion slot of the sheet it sits under, so the two arrive and leave together. */
		motion?: string;
		onclick?: () => void;
	}

	let { clear = false, motion = 'modal-enter', onclick }: Props = $props();

	const timing = $derived(slot(motion));
	const arrive = $derived({ duration: still() ? 0 : timing.duration, easing: timing.easing });
	const leave = $derived({ duration: still() ? 0 : timing.duration * LEAVING, easing: expoIn });
</script>

<div
	class="scrim"
	class:clear
	role="presentation"
	{onclick}
	in:fade={arrive}
	out:fade={leave}
></div>

<style>
	.scrim {
		position: fixed;
		inset: 0;
		z-index: 10;
		background: var(--scrim);
	}

	.clear {
		background: none;
	}
</style>
