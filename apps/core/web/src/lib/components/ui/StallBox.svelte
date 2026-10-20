<script lang="ts">
	/**
	 * Waiting, said out loud (the theme's `hera/spinner-stalled`): a spinner, what is being waited
	 * on and for how long, and — once nothing has arrived for a while — the spinner turned red and
	 * breathing with the two things a person can do about it: wait, or retry.
	 *
	 * The caller decides when it is stalled, because only it knows how long is too long.
	 */
	import { t } from '$lib/i18n';
	import Button from './Button.svelte';
	import Spinner from './Spinner.svelte';

	interface Props {
		title: string;
		/** Seconds since it started (waiting) or since anything last arrived (stalled). */
		seconds: number;
		stalled?: boolean;
		onwait?: () => void;
		onretry?: () => void;
	}

	let { title, seconds, stalled = false, onwait, onretry }: Props = $props();
</script>

<div class="stall" class:stalled role="status">
	<Spinner size={22} {stalled} />
	<div class="text">
		{stalled ? t.ui.notResponding : title}
		<small>{stalled ? t.ui.stalledFor(seconds) : t.ui.startedAgo(seconds)}</small>
	</div>
	{#if stalled}
		{#if onwait}<Button variant="ghost" size="sm" onclick={onwait}>{t.ui.wait}</Button>{/if}
		{#if onretry}<Button size="sm" icon="refresh" onclick={onretry}>{t.ui.retry}</Button>{/if}
	{/if}
</div>

<style>
	.stall {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 12px 14px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius);
		background: var(--surface);
		transition: border-color var(--motion-spinner-label);
	}

	.stalled {
		border-color: var(--danger-soft);
	}

	.text {
		flex: 1;
		min-width: 0;
		font-size: 13px;
	}

	small {
		display: block;
		color: var(--text-faint);
		font-size: 12px;
	}
</style>
