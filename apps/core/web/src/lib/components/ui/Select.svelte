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
	import Icon from '$lib/components/ui/Icon.svelte';
	import { t } from '$lib/i18n';
	import { reveal } from '$lib/motion';

	export interface Choice {
		value: string;
		label: string;
		/** A second line under the label. Used for what a value *is* rather than what it is
		 * called — an endpoint's URL, a profile's description — where the label alone is a name
		 * you have to already know. */
		hint?: string;
		/** A small image drawn before the label, in both the trigger and the row — a provider's
		 * logo beside its model, say. Omitted entirely means no icon column, not a blank one. */
		icon?: string;
		/** Swapped in if `icon` fails to load — a bundled logo file that turned out to be
		 * missing on disk, say. Should itself never be able to fail (a generated placeholder,
		 * not another network fetch), since there is nothing after it to fall back to. */
		iconFallback?: string;
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
		/** The settings-screen look: the same rectangle, surface, mono face and padding as the
		 * `input` beside it, rather than the composer's pill. A selector in a form should look
		 * like the form's fields; a pill in the composer's row should look like its chips. */
		field?: boolean;
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
		field = false,
		onchange
	}: Props = $props();

	let open = $state(false);
	let trigger = $state<HTMLButtonElement | null>(null);
	let list = $state<HTMLDivElement | null>(null);

	/** The instant `.away` last closed the dropdown, or `0` if it never has. A doubled native
	 * `click` for one physical click — a worn mouse switch, some trackpad drivers — hits `.away`
	 * first (closing it and removing it from the DOM), then lands a few ms later on the
	 * now-exposed `.pill` underneath, whose `toggle()` would otherwise reopen what the first
	 * event just closed. `toggle()` refuses to reopen within a short grace window of this
	 * timestamp. */
	let closedAt = 0;
	const REOPEN_GUARD_MS = 300;

	const current = $derived(choices.find((choice) => choice.value === value) ?? null);
	const shown = $derived(current?.label || placeholder || t.select.none);

	/* The list grows out of the trigger's corner (the theme's `menu.enter`: from scale .95 on the
	   spring slot) through the shared `reveal` gesture — the same one every sheet uses, so a popup
	   and a sheet read as the same kind of arrival at two scales. The origin is set in CSS by
	   placement. */

	function choose(next: string) {
		open = false;
		trigger?.focus();
		if (next !== value) onchange?.(next);
	}

	function closeAway() {
		open = false;
		closedAt = Date.now();
	}

	function toggle() {
		if (disabled) return;
		if (!open && Date.now() - closedAt < REOPEN_GUARD_MS) return;
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

	/** A bundled logo file can be listed and still be missing on disk — swap to the fallback
	 * rather than showing a broken image. `onerror` is removed first so a fallback that somehow
	 * also fails does not loop. */
	function onIconError(fallback: string | undefined) {
		return (event: Event) => {
			const img = event.currentTarget as HTMLImageElement;
			img.onerror = null;
			if (fallback) img.src = fallback;
		};
	}
</script>

<svelte:window {onkeydown} />

{#if open}
	<!-- Catches the click that closes the list. Transparent, not dimmed: this is a dropdown, and
	     darkening the application behind one would say it is a decision worth stopping for. -->
	<div
		class="away"
		role="presentation"
		onclick={closeAway}
		onkeydown={(event) => event.key === 'Enter' && closeAway()}
	></div>
{/if}

<div class="select" class:disabled class:field>
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
		{#if current?.icon}
			<img
				class="icon"
				src={current.icon}
				alt=""
				aria-hidden="true"
				onerror={onIconError(current.iconFallback)}
			/>
		{/if}
		<span class="shown">{shown}</span>
		<span class="chevron"><Icon name="chevD" /></span>
	</button>

	{#if open}
		<div
			bind:this={list}
			class="list {placement} {align}"
			role="listbox"
			aria-label={label}
			tabindex="-1"
			onkeydown={walk}
			in:reveal={{ scale: 0.95 }}
			out:reveal={{ scale: 0.95 }}
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
					<span class="mark"
						>{#if on}<Icon name="check" />{/if}</span
					>
					{#if choice.icon}
						<img
							class="icon"
							src={choice.icon}
							alt=""
							aria-hidden="true"
							onerror={onIconError(choice.iconFallback)}
						/>
					{/if}
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

	/* The settings-screen look: the same rectangle, surface, mono face and padding the
	   `input` elements beside it wear, so a form reads as one set of fields rather than a mix
	   of pills and boxes. Only the trigger changes — the popup is the same list everywhere. */
	.select.field .pill {
		height: calc(var(--space) * 9);
		padding: 0 calc(var(--space) * 3);
		background: var(--surface);
		border-radius: var(--radius-sm);
		font-family: var(--font-ui);
		font-size: var(--ui-size);
	}

	.select.field .pill:hover:not(:disabled),
	.select.field .pill.open {
		border-color: var(--text-faint);
		color: var(--text);
		background: var(--surface);
	}

	.shown {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.icon {
		width: 14px;
		height: 14px;
		flex: none;
		border-radius: 3px;
		object-fit: cover;
	}

	/* `margin-left: auto` keeps it on the right of a pill that is wider than its text. */
	.chevron {
		display: flex;
		flex: none;
		margin-left: auto;
		color: var(--text-faint);
		transition: transform var(--fade) var(--ease);
	}

	.pill.open .chevron {
		transform: rotate(180deg);
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
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius);
		box-shadow: var(--shadow);
	}

	/* `menu.enter` grows the list out of the trigger's corner, so the origin is the edge it is
	   attached by. */
	.list.below {
		top: calc(100% + 5px);
		transform-origin: top;
	}

	.list.above {
		bottom: calc(100% + 5px);
		transform-origin: bottom;
	}

	.list.below.start {
		transform-origin: top left;
	}

	.list.below.end {
		transform-origin: top right;
	}

	.list.above.start {
		transform-origin: bottom left;
	}

	.list.above.end {
		transform-origin: bottom right;
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
