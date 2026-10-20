<script lang="ts">
	/**
	 * Her thinking indicator (the theme's `hera/thinking`): the one piece of choreography, shown
	 * while she is still without words. A still ocellus pulsing in scale (`thinking.loop`) and the
	 * word "Thinking" breathing beside it (`thinking.label`). `large` is the start screen's.
	 */
	import { t } from '$lib/i18n';
	import Ocellus from './Ocellus.svelte';

	let { large = false, label = true }: { large?: boolean; label?: boolean } = $props();
</script>

<div class="thinking" class:large role="status" aria-label={t.message.thinking}>
	<Ocellus size={large ? 40 : 22} pulse />
	{#if label}<span class="label" aria-hidden="true">{t.message.thinking}</span>{/if}
</div>

<style>
	.thinking {
		display: inline-flex;
		align-items: center;
		gap: 10px;
		min-height: 28px;
		color: var(--text-muted);
		font-size: 13px;
	}

	.label {
		animation: breathe var(--motion-thinking-label-d) ease-in-out infinite;
	}

	@keyframes breathe {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.45;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.label {
			animation: none;
		}
	}
</style>
