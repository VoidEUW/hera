<script lang="ts" module>
	import type { IconName } from '$lib/icons';
	import type { KeyId } from '$lib/keys';

	export interface PaletteItem {
		id: string;
		label: string;
		description?: string;
		icon?: IconName;
		/** The heading it sits under. Items of one group are shown together, in the order given. */
		group: string;
		/** The chord that does the same thing, drawn at the end of the row (#112). */
		keyId?: KeyId;
		run: () => void;
	}
</script>

<script lang="ts">
	/**
	 * The command palette (Hera's `hera/palette`): one field and one list that answers it, opened
	 * over the screen from a chord and closed by the thing it does. Chats by name, projects,
	 * Settings screens, and the actions that already have a button.
	 *
	 * The keyboard model is the combobox's: focus stays in the field, ↑ / ↓ move a highlight
	 * through the rows, Enter runs the highlighted one, Escape clears the field and then closes.
	 * A row is picked by the same words a person types — every word must appear in the label or
	 * its description, in any order — and the rows keep the caller's order, so the list reads
	 * "newest chat first" without this knowing what a chat is.
	 *
	 * A `Modal`, so it is a dialog to a keyboard like every other and the one Escape rule holds.
	 */
	import { tick } from 'svelte';
	import Icon from './Icon.svelte';
	import Kbd from './Kbd.svelte';
	import Modal from './Modal.svelte';
	import SearchBar from './SearchBar.svelte';
	import { keys } from '$lib/keys';

	interface Props {
		label: string;
		placeholder: string;
		/** Said when nothing matches. */
		empty: string;
		items: PaletteItem[];
		/** What is typed. Bound so a caller can open it already filled. */
		query?: string;
		onclose: () => void;
	}

	let { label, placeholder, empty, items, query = $bindable(''), onclose }: Props = $props();

	const id = $props.id();
	/** More than this and the list is a wall; a longer one wants a narrower question. */
	const LIMIT = 40;

	const shown = $derived.by(() => {
		const words = query.toLowerCase().split(/\s+/).filter(Boolean);
		const taken: Record<string, number> = {};
		return items.filter((item) => {
			const haystack = `${item.label} ${item.description ?? ''}`.toLowerCase();
			if (!words.every((word) => haystack.includes(word))) return false;
			taken[item.group] = (taken[item.group] ?? 0) + 1;
			return taken[item.group] <= LIMIT;
		});
	});

	/** The rows under their headings, headings in the order they first appear. */
	const groups = $derived.by(() => {
		const out: Array<{ name: string; rows: PaletteItem[] }> = [];
		for (const item of shown) {
			const group = out.find((entry) => entry.name === item.group);
			if (group) group.rows.push(item);
			else out.push({ name: item.group, rows: [item] });
		}
		return out;
	});

	let at = $state(0);
	let field = $state<HTMLInputElement | null>(null);
	let list = $state<HTMLElement | null>(null);

	// A new question starts at the top of its answer.
	$effect(() => {
		void query;
		at = 0;
	});

	const active = $derived(shown[Math.min(at, shown.length - 1)]);
	const rowId = (item: PaletteItem) => `${id}-${item.id}`;

	// The field is a combobox over the list: it names the highlighted row for a screen reader
	// without focus ever leaving the place a person is typing.
	$effect(() => {
		if (!field) return;
		field.setAttribute('role', 'combobox');
		field.setAttribute('aria-expanded', 'true');
		field.setAttribute('aria-controls', `${id}-list`);
		if (active) field.setAttribute('aria-activedescendant', rowId(active));
		else field.removeAttribute('aria-activedescendant');
	});

	async function reveal() {
		await tick();
		list?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' });
	}

	function run(item: PaletteItem | undefined) {
		if (!item) return;
		// Close first: what a row does is usually navigate or open another dialog, and the focus
		// it hands back should be the one that leaves, not this one.
		onclose();
		item.run();
	}

	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
			event.preventDefault();
			if (!shown.length) return;
			at = (at + (event.key === 'ArrowDown' ? 1 : -1) + shown.length) % shown.length;
			void reveal();
		} else if (event.key === 'Enter') {
			event.preventDefault();
			run(active);
		}
	}
</script>

<Modal {label} placement="top" width="min(620px, 92vw)" closeButton={false} {onclose}>
	<div class="bar">
		<SearchBar
			bind:ref={field}
			value={query}
			{placeholder}
			onchange={(value) => (query = value)}
			{onkeydown}
		/>
	</div>
	<div bind:this={list} id="{id}-list" class="list" role="listbox" data-inline aria-label={label}>
		{#each groups as group (group.name)}
			<div class="heading" role="presentation">{group.name}</div>
			{#each group.rows as item (item.id)}
				<!-- The field keeps focus and names this row through `aria-activedescendant`, so a row
				     takes the pointer and nothing else: it is not a tab stop, and a click is the same
				     as Enter on it. -->
				<!-- svelte-ignore a11y_click_events_have_key_events -->
				<div
					id={rowId(item)}
					class="row"
					role="option"
					tabindex="-1"
					aria-selected={item === active}
					aria-keyshortcuts={item.keyId ? keys.aria(item.keyId) : undefined}
					onpointermove={() => (at = shown.indexOf(item))}
					onclick={() => run(item)}
				>
					{#if item.icon}<span class="lead"><Icon name={item.icon} /></span>{/if}
					<span class="text">
						{item.label}
						{#if item.description}<small>{item.description}</small>{/if}
					</span>
					{#if item.keyId}<Kbd decorative>{keys.label(item.keyId)}</Kbd>{/if}
				</div>
			{/each}
		{:else}
			<p class="empty">{empty}</p>
		{/each}
	</div>
</Modal>

<style>
	.bar {
		flex: none;
		padding: 12px 12px 8px;
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 1px;
		min-height: 0;
		overflow-y: auto;
		padding: 0 8px 10px;
	}

	.heading {
		padding: 10px 10px 4px;
		color: var(--text-faint);
		font-size: 11px;
		font-weight: 600;
		letter-spacing: 0.09em;
		text-transform: uppercase;
	}

	.row {
		display: flex;
		align-items: center;
		gap: 10px;
		min-height: 36px;
		padding: 6px 10px;
		border-radius: var(--radius-sm);
		color: var(--text);
		font-size: 13.5px;
		cursor: pointer;
	}

	.row[aria-selected='true'] {
		background: var(--hover);
	}

	.lead {
		display: inline-grid;
		flex: none;
		color: var(--text-muted);
	}

	.text {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	small {
		margin-left: 8px;
		color: var(--text-faint);
		font-size: 11.5px;
	}

	.empty {
		margin: 0;
		padding: 18px 10px;
		color: var(--text-faint);
		font-size: 13px;
	}
</style>
