<script lang="ts">
	/**
	 * Where toasts appear: top centre, text on ink with no border (the theme's open toast with its
	 * `toast.place: top` part). Mounted once in the layout; anything shows one through
	 * `$lib/toasts`.
	 *
	 * A polite live region, so a screen reader hears *Copied* without being interrupted. Hovering
	 * or focusing a toast holds it, so its action can be reached before it leaves.
	 */
	import { flip } from 'svelte/animate';
	import { t } from '$lib/i18n';
	import { reveal, slot, still } from '$lib/motion';
	import { toasts } from '$lib/toasts.svelte';
	import CloseButton from './CloseButton.svelte';
	import Icon from './Icon.svelte';
</script>

<div class="toaster" role="status" aria-live="polite">
	{#each toasts.items as toast (toast.id)}
		<div
			class="toast {toast.kind}"
			role="group"
			animate:flip={{ duration: still() ? 0 : slot('toast-enter').duration }}
			in:reveal={{ y: -8, slot: 'toast-enter' }}
			out:reveal={{ y: -8, slot: 'toast-enter' }}
			onpointerenter={() => toasts.hold(toast.id)}
			onpointerleave={() => toasts.release(toast.id)}
			onfocusin={() => toasts.hold(toast.id)}
			onfocusout={() => toasts.release(toast.id)}
		>
			<Icon name={toast.kind === 'failure' ? 'alert' : 'check'} />
			<span class="message">{toast.message}</span>
			{#if toast.action}
				<button
					class="action"
					type="button"
					onclick={() => {
						toast.action?.run();
						toasts.dismiss(toast.id);
					}}>{toast.action.label}</button
				>
			{/if}
			<CloseButton
				size="sm"
				inverse
				label={t.ui.dismiss}
				onclick={() => toasts.dismiss(toast.id)}
			/>
		</div>
	{/each}
</div>

<style>
	.toaster {
		position: fixed;
		top: 16px;
		left: 50%;
		z-index: 100;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8px;
		transform: translateX(-50%);
		pointer-events: none;
	}

	/* The open look: an inverted text-on-ink bar, no border. The icon is the bar's own colour. */
	.toast {
		display: flex;
		align-items: center;
		gap: 9px;
		max-width: min(90vw, 480px);
		padding: 7px 6px 7px 12px;
		border-radius: var(--radius-sm);
		background: var(--text);
		color: var(--ground);
		box-shadow: var(--shadow-sm);
		font-size: 12.5px;
		pointer-events: auto;
	}

	.message {
		flex: 1;
	}

	.action {
		color: inherit;
		font-weight: 600;
		text-decoration: underline;
		text-underline-offset: 2px;
	}
</style>
