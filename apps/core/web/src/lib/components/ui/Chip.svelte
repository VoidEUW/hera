<script lang="ts">
	/**
	 * A toggle that sits in a row of others — the composer's skills and servers (the theme's
	 * `hera/chips`). On is brass, because what is switched on for the next message is authority
	 * she has been given; the leading dot says on or off before the label is read.
	 *
	 * It is a button with `aria-pressed` when it toggles, and a plain button when it opens
	 * something (`pressed` left undefined) — the two are different questions to a screen reader.
	 */
	import type { Snippet } from 'svelte';

	interface Props {
		on?: boolean;
		/** Set when the chip is itself the switch; leave undefined when it opens a picker. */
		pressed?: boolean;
		disabled?: boolean;
		title?: string;
		onclick?: (event: MouseEvent) => void;
		children: Snippet;
	}

	let { on = false, pressed, disabled = false, title, onclick, children }: Props = $props();
</script>

<button class="chip" class:on type="button" aria-pressed={pressed} {disabled} {title} {onclick}>
	<span class="dot" aria-hidden="true"></span>
	{@render children()}
</button>

<style>
	.chip {
		display: inline-flex;
		align-items: center;
		gap: calc(var(--space) * 1.5);
		height: calc(var(--space) * 7);
		padding: 0 calc(var(--space) * 3);
		border: var(--border-width) solid var(--line);
		border-radius: var(--chip-radius);
		color: var(--text-muted);
		font-size: calc(var(--ui-size) - 1px);
		white-space: nowrap;
		transition:
			transform var(--motion-button-hover),
			border-color var(--fade) var(--ease),
			color var(--fade) var(--ease),
			background var(--fade) var(--ease);
	}

	.chip:hover:not(:disabled) {
		transform: translateY(-1px);
		color: var(--text);
		background: var(--hover);
	}

	.chip:active:not(:disabled) {
		transform: translateY(1px);
	}

	.dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: var(--text-faint);
	}

	.on {
		border-color: var(--brass-line);
		color: var(--text);
	}

	.on .dot {
		background: var(--brass);
	}

	.chip:disabled {
		color: var(--text-faint);
		cursor: not-allowed;
	}
</style>
