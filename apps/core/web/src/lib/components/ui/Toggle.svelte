<script lang="ts">
	/**
	 * The drawn half of a toggle (the theme's `hera/toggles`): a switch's round track and thumb,
	 * or a checkbox's square and check. Both turn brass when on — a setting is her authority being
	 * granted — and move on `switch.toggle`.
	 *
	 * Only the picture. `Checkbox` lays a native input over it; a `MenuItem` with a switch or a
	 * checkbox at its end draws it as a mark on a row that is itself the control. One drawing, so
	 * on looks the same wherever it is switched on.
	 */
	import Icon from './Icon.svelte';

	let { kind = 'box', on = false }: { kind?: 'box' | 'switch'; on?: boolean } = $props();
</script>

{#if kind === 'switch'}
	<span class="switch" class:on aria-hidden="true"></span>
{:else}
	<span class="box" class:on aria-hidden="true"><Icon name="check" size="12px" /></span>
{/if}

<style>
	.switch {
		position: relative;
		flex: none;
		width: 34px;
		height: 20px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--chip-radius);
		background: var(--surface-raised);
		transition:
			background-color var(--motion-switch-toggle),
			border-color var(--motion-switch-toggle);
	}

	.switch::after {
		content: '';
		position: absolute;
		top: 2px;
		left: 2px;
		width: 14px;
		height: 14px;
		border-radius: var(--chip-radius);
		background: var(--text-muted);
		transition:
			transform var(--motion-switch-toggle),
			background-color var(--motion-switch-toggle);
	}

	.switch.on {
		border-color: var(--brass);
		background: var(--brass);
	}

	.switch.on::after {
		background: var(--on-brass);
		transform: translateX(14px);
	}

	.box {
		display: inline-grid;
		flex: none;
		place-items: center;
		width: 17px;
		height: 17px;
		border: 1.5px solid var(--text-faint);
		border-radius: max(calc(var(--radius-sm) - 2px), 3px);
		color: var(--on-brass);
		--icon-stroke: 2.6;
		transition:
			background-color var(--motion-switch-toggle),
			border-color var(--motion-switch-toggle);
	}

	.box :global(.icon) {
		opacity: 0;
		transform: scale(0.6);
		transition:
			opacity var(--motion-switch-toggle),
			transform var(--motion-switch-toggle);
	}

	.box.on {
		border-color: var(--brass);
		background: var(--brass);
	}

	.box.on :global(.icon) {
		opacity: 1;
		transform: none;
	}
</style>
