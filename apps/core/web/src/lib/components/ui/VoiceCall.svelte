<script lang="ts">
	/**
	 * What the composer becomes during a voice call (the theme's `hera/voice`): a laurel waveform —
	 * twelve 3px bars rising and falling out of step (`voice.wave`) — "Listening" and the call's
	 * length, mute, and End in red. Muted, the bars go faint and stop where they are.
	 *
	 * Built and on `/design`; nothing in Hera places a call yet.
	 */
	import { t } from '$lib/i18n';
	import Button from './Button.svelte';
	import IconButton from './IconButton.svelte';

	interface Props {
		seconds: number;
		muted?: boolean;
		onmute?: () => void;
		onend?: () => void;
	}

	let { seconds, muted = false, onmute, onend }: Props = $props();

	const BARS = [0.5, 0.8, 0.35, 1, 0.6, 0.9, 0.4, 0.75, 0.55, 1, 0.45, 0.7];
	const clock = $derived(`${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`);
</script>

<div class="voice" class:muted>
	<span class="wave" aria-hidden="true">
		{#each BARS as height, index (index)}
			<i style:height="{height * 100}%" style:--k={index}></i>
		{/each}
	</span>
	<span class="time">
		<b>{muted ? t.voice.muted : t.voice.listening}</b> · <span class="clock">{clock}</span>
	</span>
	<span class="space"></span>
	<IconButton
		icon={muted ? 'micOff' : 'mic'}
		label={muted ? t.voice.unmute : t.voice.mute}
		onclick={onmute}
	/>
	<Button variant="danger" size="sm" icon="phone" onclick={onend}>{t.voice.end}</Button>
</div>

<style>
	.voice {
		display: flex;
		align-items: center;
		gap: 12px;
		min-height: 36px;
	}

	.wave {
		display: inline-flex;
		align-items: center;
		gap: 3px;
		height: 26px;
		color: var(--laurel);
	}

	.wave i {
		width: 3px;
		border-radius: 2px;
		background: currentColor;
		transform-origin: center;
		animation: wave var(--motion-voice-wave) infinite;
		animation-delay: calc(var(--motion-voice-wave-d) * var(--k) * -0.13);
	}

	.muted .wave {
		color: var(--text-faint);
	}

	.muted .wave i {
		animation-play-state: paused;
	}

	.time {
		color: var(--text-muted);
		font-size: 12.5px;
	}

	b {
		color: var(--laurel);
		font-weight: 500;
	}

	.muted b {
		color: var(--text-muted);
	}

	.clock {
		font-variant-numeric: tabular-nums;
	}

	.space {
		flex: 1;
	}

	@keyframes wave {
		0%,
		100% {
			transform: scaleY(0.25);
		}
		50% {
			transform: scaleY(1);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.wave i {
			animation: none;
		}
	}
</style>
