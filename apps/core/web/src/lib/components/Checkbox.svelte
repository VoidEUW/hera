<script lang="ts">
	/**
	 * One checkbox, drawn by us (#99).
	 *
	 * The native box inside the settings screens was small, did not react on hover, and did not
	 * follow the theme — the three things that made it look like the platform rather than like
	 * Hera. This replaces it: an ~18px box, `--brass` fill and check when on, hover / active /
	 * focus-visible states, and a `label` prop so the text and the box are one target.
	 *
	 * The native input stays underneath, visually hidden rather than removed, so keyboard and
	 * screen readers keep working — a checkbox that cannot be tabbed to or read out is a
	 * checkbox that has traded function for looks.
	 */

	interface Props {
		/** The checked state. One-way: the caller owns the value and gets `onchange` back, the
		 * same contract as every other control in the interface. */
		checked: boolean;
		/** The text beside the box, and the accessible name when `label` is not given. Clicking
		 * it clicks the box, because they are one `<label>` element. */
		label?: string;
		/** The accessible name, when the visible text is not it — a box labelled by a whole
		 * sentence elsewhere, say. */
		ariaLabel?: string;
		disabled?: boolean;
		onchange?: (checked: boolean) => void;
	}

	let { checked, label = '', ariaLabel = '', disabled = false, onchange }: Props = $props();

	function flip(event: Event) {
		// Read from the native input rather than flipping a local flag: the input is the source
		// of truth for what a click did, and this way the component works even when the caller
		// does not round-trip the new value back through the `checked` prop.
		const input = event.currentTarget as HTMLInputElement;
		onchange?.(input.checked);
	}
</script>

<label class="check" class:disabled>
	<input type="checkbox" {checked} {disabled} aria-label={ariaLabel || undefined} onchange={flip} />
	<span class="box" aria-hidden="true">
		<span class="mark"></span>
	</span>
	{#if label}<span class="word">{label}</span>{/if}
</label>

<style>
	.check {
		display: flex;
		align-items: center;
		gap: 6px;
		font-size: 12px;
		color: var(--text-muted);
		cursor: pointer;
	}

	.check:has(input:disabled) {
		cursor: default;
		color: var(--text-faint);
	}

	/* Visually hidden, functionally present: the input is what the keyboard and screen reader
	 * reach. Sized to the box rather than 1px so the focus ring lands somewhere sensible. */
	input {
		position: absolute;
		width: 18px;
		height: 18px;
		margin: 0;
		opacity: 0;
		cursor: inherit;
	}

	.box {
		position: relative;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 18px;
		height: 18px;
		flex: none;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: 5px;
		transition:
			border-color var(--fade) var(--ease),
			background-color var(--fade) var(--ease);
	}

	/* Hover, on the whole label — the text and the box are one target. */
	.check:hover:not(.disabled) .box {
		border-color: var(--text-faint);
	}

	.check:active:not(.disabled) .box {
		transform: scale(0.94);
	}

	/* Focus lands on the input, but the ring is drawn on the box it covers. */
	input:focus-visible + .box {
		border-color: var(--brass);
		box-shadow: 0 0 0 2px rgb(217 174 82 / 0.25);
	}

	/* The check itself: a rotated L rather than a \u2713, the same hairline mark the Select's
	 * rows and the SkillPicker's rows use, so *on* looks the same wherever it is switched on. */
	.mark {
		width: 9px;
		height: 5px;
		border-left: 1.5px solid transparent;
		border-bottom: 1.5px solid transparent;
		transform: rotate(-45deg) translate(0, -1px);
		transition: border-color var(--fade) var(--ease);
	}

	input:checked + .box .mark {
		border-color: var(--ground);
	}

	input:checked + .box {
		background: var(--brass);
		border-color: var(--brass);
	}

	.word {
		min-width: 0;
	}
</style>
