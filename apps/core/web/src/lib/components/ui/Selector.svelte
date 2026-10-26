<script lang="ts" module>
	import type { IconName } from '$lib/icons';

	export interface Choice {
		value: string;
		label: string;
		/** A second, quieter line under the label: what a value *is* — a model's id and host, a
		 * profile's description — where the name alone is one you would have to already know. */
		description?: string;
		/** Choices with the same group sit under one heading, in the order they first appear. */
		group?: string;
		icon?: IconName;
		/** A small picture instead of an icon — a provider's logo. */
		image?: string;
	}
</script>

<script lang="ts">
	/**
	 * A button that opens a menu of choices (the theme's `hera/selector`). The menu is the same
	 * `Menu` every other menu in Hera uses: headings, a description under each row, the brass check
	 * on the chosen one, nothing else coloured.
	 *
	 * Two triggers, one menu:
	 *
	 * - `field` — the soft look: a filled rounded box with an optional leading icon, the label and
	 *   a chevron that turns while the menu is open. For a form, beside other fields.
	 * - `chip` — a fully rounded chip, for a toolbar: the composer's model, the top bar's artifacts.
	 */
	import { t } from '$lib/i18n';
	import Chip from './Chip.svelte';
	import Field from './Field.svelte';
	import Icon from './Icon.svelte';
	import Menu from './Menu.svelte';
	import MenuHeading from './MenuHeading.svelte';
	import MenuItem from './MenuItem.svelte';
	import MenuSeparator from './MenuSeparator.svelte';
	import MenuNote from './MenuNote.svelte';

	interface Props {
		choices: Choice[];
		value: string;
		/** The accessible name. Not drawn on a chip: the trigger shows the current value. */
		label: string;
		look?: 'field' | 'chip';
		/** The trigger's leading icon. Defaults to the chosen row's. */
		icon?: IconName;
		placement?: 'below' | 'above';
		align?: 'start' | 'end';
		disabled?: boolean;
		/** Shown in place of the value when nothing is chosen. */
		placeholder?: string;
		/** A tooltip on the trigger. */
		hint?: string;
		/** A `chip` trigger's text below the phone breakpoint (`Chip`'s `short`); `''` is the
		 * icon alone. */
		short?: string;
		/** A visible label above a `field` trigger, and a help line under it — the same frame a
		 * text field beside it has. */
		caption?: string;
		help?: string;
		onchange?: (value: string) => void;
	}

	let {
		choices,
		value,
		label,
		look = 'field',
		icon,
		placement = 'below',
		align = 'start',
		disabled = false,
		placeholder = '',
		hint,
		short,
		caption,
		help,
		onchange
	}: Props = $props();

	const id = $props.id();

	let open = $state(false);
	let trigger = $state<HTMLButtonElement | null>(null);

	/** When the catcher behind the menu last closed it. One physical click that arrives as two —
	 * a worn switch, some trackpad drivers — would otherwise close the menu and land a moment later
	 * on the trigger underneath, reopening it. */
	let closedAt = 0;
	const REOPEN_GUARD_MS = 300;

	const current = $derived(choices.find((choice) => choice.value === value) ?? null);
	const shown = $derived(current?.label || placeholder || t.select.none);
	const lead = $derived(icon ?? current?.icon);

	const groups = $derived.by(() => {
		const out: { name: string | undefined; choices: Choice[] }[] = [];
		for (const choice of choices) {
			const last = out.at(-1);
			if (last && last.name === choice.group) last.choices.push(choice);
			else out.push({ name: choice.group, choices: [choice] });
		}
		return out;
	});

	function toggle() {
		if (disabled) return;
		if (!open && Date.now() - closedAt < REOPEN_GUARD_MS) return;
		open = !open;
	}

	function close() {
		open = false;
		closedAt = Date.now();
	}

	function choose(next: string) {
		open = false;
		trigger?.focus();
		if (next !== value) onchange?.(next);
	}

	function openFrom(event: KeyboardEvent) {
		if (disabled || (event.key !== 'ArrowDown' && event.key !== 'ArrowUp')) return;
		event.preventDefault();
		open = true;
	}
</script>

{#if look === 'chip'}
	<Chip
		bind:ref={trigger}
		icon={current?.image ? undefined : lead}
		image={current?.image}
		chevron
		expanded={open}
		haspopup="menu"
		{label}
		{hint}
		{short}
		{disabled}
		onclick={toggle}
		onkeydown={openFrom}>{shown}</Chip
	>
{:else}
	{#snippet fieldTrigger()}
		<button
			bind:this={trigger}
			{id}
			class="field"
			class:open
			type="button"
			{disabled}
			aria-label={caption ? undefined : label}
			aria-haspopup="menu"
			aria-expanded={open}
			onclick={toggle}
			onkeydown={openFrom}
		>
			{#if current?.image}
				<img class="image" src={current.image} alt="" />
			{:else if lead}
				<span class="lead"><Icon name={lead} /></span>
			{/if}
			<span class="shown">{shown}</span>
			<span class="chevron"><Icon name="chevD" /></span>
		</button>
	{/snippet}
	{#if caption || help}
		<Field {id} label={caption} {help}>{@render fieldTrigger()}</Field>
	{:else}
		{@render fieldTrigger()}
	{/if}
{/if}

<Menu {open} anchor={trigger} {label} {placement} {align} onclose={close}>
	{#each groups as group, index (index)}
		{#if index > 0 && group.name}<MenuSeparator />{/if}
		{#if group.name}<MenuHeading>{group.name}</MenuHeading>{/if}
		{#each group.choices as choice (choice.value)}
			<MenuItem
				icon={choice.icon}
				image={choice.image}
				description={choice.description}
				trail="check"
				on={choice.value === value}
				onclick={() => choose(choice.value)}>{choice.label}</MenuItem
			>
		{/each}
	{:else}
		<MenuNote quiet>{t.select.empty}</MenuNote>
	{/each}
</Menu>

<style>
	.field {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		min-width: 0;
		max-width: 100%;
		height: calc(var(--space) * 8.5);
		padding: 0 8px 0 10px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: var(--surface);
		color: var(--text);
		font-size: 13px;
		text-align: left;
		transition:
			box-shadow var(--motion-button-hover),
			border-color var(--motion-button-hover),
			background-color var(--motion-button-hover);
	}

	.field:hover:not(:disabled),
	.field.open {
		border-color: var(--text-faint);
	}

	.field:disabled {
		color: var(--text-faint);
		cursor: not-allowed;
	}

	.lead {
		display: inline-grid;
		color: var(--text-muted);
	}

	.image {
		width: var(--icon-size);
		height: var(--icon-size);
		object-fit: contain;
	}

	.shown {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.chevron {
		display: inline-grid;
		color: var(--text-faint);
		transition: transform var(--motion-menu-enter);
	}

	.open .chevron {
		transform: rotate(180deg);
	}
</style>
