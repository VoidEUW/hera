<script lang="ts">
	/**
	 * Hers: the send button (the theme's `hera/send-button`), pomegranate because sending is the
	 * one action that is her. While she works it becomes Stop — the arrow lifts and shrinks out,
	 * the stop square grows in, and a pomegranate ring spins around the button (`send.morph`) — so
	 * the same place in the composer always holds the one thing you can do next. `cancelling` is
	 * the beat between pressing Stop and the turn closing: square and ring go, nothing is offered.
	 *
	 * One element across every state rather than buttons swapped in and out, so focus stays where
	 * it was when a turn starts or ends under the keyboard.
	 */
	import { t } from '$lib/i18n';
	import Icon from './Icon.svelte';
	import { tooltip } from '$lib/tooltip';

	interface Props {
		busy: boolean;
		cancelling?: boolean;
		disabled?: boolean;
		onsend: () => void;
		onstop: () => void;
	}

	let { busy, cancelling = false, disabled = false, onsend, onstop }: Props = $props();
	const label = $derived(busy ? t.composer.stop : t.composer.send);
</script>

<button
	class="send"
	class:run={busy && !cancelling}
	class:cancel={cancelling}
	type="button"
	disabled={cancelling || (!busy && disabled)}
	aria-label={label}
	use:tooltip={label}
	onclick={() => (busy ? onstop() : onsend())}
>
	<span class="go"><Icon name="arrowUp" /></span>
	<span class="stop"><Icon name="stop" /></span>
	<svg class="ring" viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="20" r="18" /></svg>
</button>

<style>
	.send {
		position: relative;
		display: inline-grid;
		flex: none;
		place-items: center;
		width: 32px;
		height: 32px;
		border-radius: 50%;
		background: var(--pomegranate);
		color: var(--on-pomegranate);
		transition:
			background-color var(--motion-send-morph),
			opacity var(--motion-send-morph),
			transform var(--motion-button-press),
			box-shadow var(--motion-button-hover);
	}

	.send:hover:not(:disabled) {
		box-shadow: inset 0 0 0 100px var(--hover);
	}

	.send:active:not(:disabled) {
		transform: translateY(1px);
	}

	.send:disabled {
		opacity: 0.42;
		cursor: not-allowed;
	}

	.go,
	.stop {
		display: flex;
		grid-area: 1 / 1;
		--icon-stroke: 2.2;
		transition:
			transform var(--motion-send-morph),
			opacity var(--motion-send-morph);
	}

	.stop {
		opacity: 0;
		transform: scale(0.4);
	}

	.ring {
		position: absolute;
		inset: -4px;
		width: 40px;
		height: 40px;
		opacity: 0;
		pointer-events: none;
		transition: opacity var(--motion-send-morph);
	}

	/* `send.morph`'s ring turns once every five morphs — 1.1 s at Heaven's speed. */
	.ring circle {
		fill: none;
		stroke: var(--pomegranate);
		stroke-width: 2;
		stroke-linecap: round;
		stroke-dasharray: 22 120;
		transform-box: fill-box;
		transform-origin: center;
		animation: turn calc(var(--motion-send-morph-d) * 5) linear infinite;
	}

	.run .go {
		opacity: 0;
		transform: scale(0.4) translateY(-6px);
	}

	.run .stop {
		opacity: 1;
		transform: none;
	}

	.run .ring {
		opacity: 1;
	}

	.cancel .go,
	.cancel .stop {
		opacity: 0;
		transform: scale(0.2);
	}

	@keyframes turn {
		to {
			transform: rotate(360deg);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.ring circle {
			animation: none;
			stroke-dasharray: none;
		}
	}
</style>
