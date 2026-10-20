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
			<button
				class="dismiss"
				type="button"
				aria-label={t.ui.dismiss}
				onclick={() => toasts.dismiss(toast.id)}
			>
				<Icon name="x" size="calc(var(--icon-size) - 2px)" />
			</button>
		</div>
	{/each}
</div>

<style>
	.toaster {
		position: fixed;
		top: calc(var(--space) * 4);
		left: 50%;
		z-index: 100;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: calc(var(--space) * 2);
		transform: translateX(-50%);
		pointer-events: none;
	}

	.toast {
		display: flex;
		align-items: center;
		gap: calc(var(--space) * 2.5);
		max-width: min(90vw, 480px);
		padding: calc(var(--space) * 2.5) calc(var(--space) * 2.5) calc(var(--space) * 2.5)
			calc(var(--space) * 3.5);
		border-radius: var(--radius);
		background: var(--text);
		color: var(--ground);
		box-shadow: var(--shadow);
		font-size: var(--ui-size);
		pointer-events: auto;
	}

	.success :global(.icon) {
		color: var(--laurel);
	}

	.failure :global(.icon:first-child) {
		color: var(--danger);
	}

	.message {
		flex: 1;
	}

	.action {
		color: var(--ground);
		font-weight: 600;
		text-decoration: underline;
		text-underline-offset: 2px;
	}

	.dismiss {
		display: grid;
		place-items: center;
		width: calc(var(--space) * 6);
		height: calc(var(--space) * 6);
		border-radius: 50%;
		color: var(--ground);
		opacity: 0.6;
		transition: opacity var(--fade) var(--ease);
	}

	.dismiss:hover {
		opacity: 1;
	}
</style>
