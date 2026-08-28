<script lang="ts">
	/**
	 * One switch, currently set to this.
	 *
	 * Every selector in the application is this component, because before it there were two
	 * kinds: the composer's pills, which were a native `<select>` with `appearance: none` and a
	 * hand-drawn chevron, and the plain native controls everywhere else. They matched in the one
	 * place somebody had bothered and nowhere else — and even where they matched, *opening* one
	 * dropped the platform's own list into an interface that draws everything else itself.
	 *
	 * So the popup is ours too, and it is the **skill picker's** popup: raised surface, hairline,
	 * large radius, the same shadow, rows with a brass check on the chosen one. A person should
	 * not be able to tell from the way a list looks whether it came from a dialog or from a
	 * dropdown, because it is the same act either way.
	 *
	 * It is a popover rather than a sheet — no scrim, anchored to its trigger. The skill picker
	 * is a sheet because choosing skills is a task you go and do; picking one value from four is
	 * not, and darkening the application to ask it would be shouting.
	 */
	import { t } from '$lib/i18n';

	export interface Choice {
		value: string;
		label: string;
		/** A second line under the label. Used for what a value *is* rather than what it is
		 * called — an endpoint's URL, a profile's description — where the label alone is a name
		 * you have to already know. */
		hint?: string;
	}

	interface Props {
		choices: Choice[];
		value: string;
		/** The accessible name. Not drawn: the trigger shows the current value, and a visible
		 * label beside every pill would double the width of the composer bar. */
		label: string;
		/** Which way the list opens. The composer sits at the foot of the window, so `above` is
		 * not a preference there — a list opening downwards would be off the screen. */
		placement?: 'above' | 'below';
		/** Which edge the list is pinned to. A pill near the right edge opens leftwards. */
		align?: 'start' | 'end';
		disabled?: boolean;
		title?: string;
		/** Shown in place of the value when nothing is chosen and nothing can be. */
		placeholder?: string;
		onchange?: (value: string) => void;
	}

	let {
		choices,
		value,
		label,
		placement = 'below',
		align = 'start',
		disabled = false,
		title = '',
		placeholder = '',
		onchange
	}: Props = $props();

	let open = $state(false);
	let trigger = $state<HTMLButtonElement | null>(null);
	let list = $state<HTMLDivElement | null>(null);

	const current = $derived(choices.find((choice) => choice.value === value) ?? null);
	const shown = $derived(current?.label || placeholder || t.select.none);

	function choose(next: string) {
		open = false;
		trigger?.focus();
		if (next !== value) onchange?.(next);
	}

	function toggle() {
		if (disabled) return;
		open = !open;
	}

	/** Arrow keys walk the list, because the options are real buttons and focus is what moves.
	 * Home and End are cheap here and are what a listbox is expected to do. */
	function walk(event: KeyboardEvent) {
		const keys = ['ArrowDown', 'ArrowUp', 'Home', 'End'];
		if (!keys.includes(event.key)) return;
		const options = [...(list?.querySelectorAll<HTMLButtonElement>('[role="option"]') ?? [])];
		if (!options.length) return;
		event.preventDefault();

		const here = options.indexOf(document.activeElement as HTMLButtonElement);
		const next =
			event.key === 'Home'
				? 0
				: event.key === 'End'
					? options.length - 1
					: event.key === 'ArrowDown'
						? (here + 1) % options.length
						: (here - 1 + options.length) % options.length;
		options[next]?.focus();
	}

	/** Opening with a key should land on the list rather than leaving focus behind on the pill —
	 * otherwise the first ArrowDown is spent getting there. */
	function openFrom(event: KeyboardEvent) {
		if (disabled) return;
		if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
		event.preventDefault();
		open = true;
		queueMicrotask(() => list?.querySelector<HTMLButtonElement>('[role="option"]')?.focus());
	}

	function onkeydown(event: KeyboardEvent) {
		if (!open || event.key !== 'Escape') return;
		open = false;
		trigger?.focus();
	}
</script>

<svelte:window {onkeydown} />

{#if open}
	<!-- Catches the click that closes the list. Transparent, not dimmed: this is a dropdown, and
	     darkening the application behind one would say it is a decision worth stopping for. -->
	<div
		class="away"
		role="presentation"
		onclick={() => (open = false)}
		onkeydown={(event) => event.key === 'Enter' && (open = false)}
	></div>
{/if}

<div class="select" class:disabled>
	<button
		bind:this={trigger}
		class="pill"
		class:open
		type="button"
		{disabled}
		{title}
		aria-label={label}
		aria-haspopup="listbox"
		aria-expanded={open}
		onclick={toggle}
		onkeydown={openFrom}
	>
		<span class="shown">{shown}</span>
		<span class="chevron" aria-hidden="true"></span>
	</button>

	{#if open}
		<div
			bind:this={list}
			class="list {placement} {align}"
			role="listbox"
			aria-label={label}
			tabindex="-1"
			onkeydown={walk}
		>
			{#each choices as choice (choice.value)}
				{@const on = choice.value === value}
				<button
					class="entry"
					class:on
					type="button"
					role="option"
					aria-selected={on}
					onclick={() => choose(choice.value)}
				>
					<span class="mark" aria-hidden="true">{on ? '✓' : ''}</span>
					<span class="what">
						<span class="name">{choice.label}</span>
						{#if choice.hint}<span class="caption hint">{choice.hint}</span>{/if}
					</span>
				</button>
			{:else}
				<p class="empty caption">{t.select.empty}</p>
			{/each}
		</div>
	{/if}
</div>

<style>
	.select {
		position: relative;
		display: flex;
		align-items: center;
		min-width: 0;
	}

	/* The composer's pill, which is the one selector in v0.1 anybody had drawn by hand — the
	   same shape as the context chip beside it, because they sit in the same row and mean the
	   same kind of thing. */
	.pill {
		display: flex;
		align-items: center;
		gap: 6px;
		width: 100%;
		min-width: 0;
		padding: 3px 10px;
		background: none;
		border: 1px solid var(--line);
		border-radius: 999px;
		font-size: 12.5px;
		line-height: 1.45;
		color: var(--text-muted);
		cursor: pointer;
		transition:
			border-color var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	.pill:hover:not(:disabled),
	.pill.open {
		border-color: var(--text-faint);
		color: var(--text);
	}

	.pill:disabled {
		cursor: default;
		color: var(--text-faint);
		border-style: dashed;
	}

	.shown {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* Two borders on a rotated square: one shape, no asset, and it takes the colour of the row
	   like everything else here. `margin-left: auto` keeps it on the right of a pill that is
	   wider than its text. */
	.chevron {
		width: 5px;
		height: 5px;
		flex: none;
		margin-left: auto;
		border-right: 1.5px solid currentcolor;
		border-bottom: 1.5px solid currentcolor;
		transform: translateY(-2px) rotate(45deg);
		transition: transform var(--fade) var(--ease);
	}

	.pill.open .chevron {
		transform: translateY(1px) rotate(225deg);
	}

	.away {
		position: fixed;
		inset: 0;
		z-index: 20;
	}

	/* The skill picker's popup, anchored instead of centred. Same ground, same hairline, same
	   radius, same shadow, same fade — so a list looks like a list wherever it was opened from. */
	.list {
		position: absolute;
		z-index: 21;
		display: flex;
		flex-direction: column;
		min-width: max(100%, 180px);
		max-width: min(320px, 80vw);
		max-height: 44vh;
		overflow-y: auto;
		padding: 5px;
		background: var(--surface-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow);
		animation: fade var(--fade) var(--ease);
	}

	@keyframes fade {
		from {
			opacity: 0;
		}
	}

	.list.below {
		top: calc(100% + 5px);
	}

	.list.above {
		bottom: calc(100% + 5px);
	}

	.list.start {
		left: 0;
	}

	.list.end {
		right: 0;
	}

	.entry {
		display: flex;
		align-items: flex-start;
		gap: 8px;
		width: 100%;
		padding: 7px 8px;
		border-radius: var(--radius);
		text-align: left;
		transition: background var(--fade) var(--ease);
	}

	.entry:hover,
	.entry:focus-visible {
		background: var(--surface);
		outline: none;
	}

	.mark {
		width: 13px;
		flex: none;
		padding-top: 1px;
		color: var(--brass);
		font-size: 11px;
	}

	.what {
		min-width: 0;
	}

	.name {
		display: block;
		font-size: 13px;
		color: var(--text-muted);
	}

	.on .name {
		color: var(--brass);
	}

	.hint {
		display: block;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.empty {
		margin: 0;
		padding: 8px;
		color: var(--text-muted);
	}
</style>
