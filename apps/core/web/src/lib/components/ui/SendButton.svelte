<script lang="ts">
	/**
	 * Hers: the send button (the theme's `hera/send-button`), pomegranate because sending is the
	 * one action that is her. While she works it becomes Stop — the arrow lifts and shrinks out,
	 * the stop square grows in, and a ring turns around the button (`send.morph`) — so the same
	 * place in the composer always holds the one thing you can do next.
	 *
	 * One element across both states rather than two buttons swapped in and out, so focus stays
	 * where it was when a turn starts or ends under the keyboard.
	 */
	import { t } from '$lib/i18n';
	import Icon from './Icon.svelte';

	interface Props {
		busy: boolean;
		disabled?: boolean;
		onsend: () => void;
		onstop: () => void;
	}

	let { busy, disabled = false, onsend, onstop }: Props = $props();
</script>

<button
	class="send"
	class:busy
	type="button"
	disabled={!busy && disabled}
	aria-label={busy ? t.composer.stop : t.composer.send}
	title={busy ? t.composer.stop : t.composer.send}
	onclick={() => (busy ? onstop() : onsend())}
>
	<span class="arrow"><Icon name="arrowUp" /></span>
	<span class="square" aria-hidden="true"></span>
	{#if busy}<span class="ring" aria-hidden="true"></span>{/if}
</button>

<style>
	.send {
		--diameter: calc(var(--space) * 7.5);
		position: relative;
		display: grid;
		place-items: center;
		flex: none;
		width: var(--diameter);
		height: var(--diameter);
		border-radius: 50%;
		background: var(--pomegranate);
		color: var(--on-pomegranate);
		transition:
			transform var(--motion-button-hover),
			opacity var(--fade) var(--ease);
	}

	.send:hover:not(:disabled) {
		transform: translateY(-1px);
	}

	.send:active:not(:disabled) {
		transform: translateY(1px);
	}

	.send:disabled {
		opacity: 0.4;
		cursor: default;
	}

	.arrow,
	.square {
		grid-area: 1 / 1;
		transition:
			transform var(--motion-send-morph),
			opacity var(--motion-send-morph);
	}

	.arrow {
		display: flex;
	}

	.square {
		width: 9px;
		height: 9px;
		border-radius: 2px;
		background: currentColor;
		opacity: 0;
		transform: scale(0.2);
	}

	.busy .arrow {
		opacity: 0;
		transform: translateY(-6px) scale(0.5);
	}

	.busy .square {
		opacity: 1;
		transform: none;
	}

	/* A ring turning around the button while she works, in her own colour. */
	.ring {
		position: absolute;
		inset: -4px;
		border: 2px solid var(--pomegranate-soft);
		border-top-color: var(--pomegranate);
		border-radius: 50%;
		animation: turn var(--motion-spinner-loop) infinite;
	}

	@keyframes turn {
		to {
			transform: rotate(360deg);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.ring {
			border-color: var(--pomegranate);
		}
	}
</style>
