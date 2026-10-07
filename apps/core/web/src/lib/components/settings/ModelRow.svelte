<script lang="ts">
	/**
	 * One registered model: a row that opens its own options when you click it.
	 *
	 * The toggle is a real `<button>` that takes all the width the row has to spare, so a click
	 * anywhere on the row's body opens or closes it, and Enter and Space do the same from the
	 * keyboard. **Remove** is a *sibling* of that button, not children: a
	 * control inside a control is invalid, and it would make the whole row announce twice.
	 *
	 * Whether the editor is open is the parent's to say. A provider has one open model at a
	 * time, so that is one value there rather than a flag in every row.
	 */
	import type { ModelEntry, ModelPreset, Provider } from '$lib/api/client';
	import { t } from '$lib/i18n';
	import ModelOptions from './ModelOptions.svelte';

	interface Props {
		provider: string;
		model: ModelEntry;
		/** Whether this is the model her turns run on. Switching it is the composer's job, where she is
		 * picked per message; there is no second switch here. */
		current: boolean;
		open: boolean;
		presets: ModelPreset[];
		ontoggle: () => void;
		onremove: () => void;
		onsaved: (body: { providers: Provider[]; active: string }) => void;
		onerror: (message: string) => void;
	}

	let { provider, model, current, open, presets, ontoggle, onremove, onsaved, onerror }: Props =
		$props();

	const count = $derived(Object.keys(model.options).length);
</script>

<li class:on={current}>
	<div class="row">
		<button class="toggle" type="button" aria-expanded={open} onclick={ontoggle}>
			<span class="start">
				<span class="chevron" class:open aria-hidden="true">▸</span>
				<span class="name">{model.name}</span>
				{#if count}<span class="badge quiet">{t.models.optionsSet(count)}</span>{/if}
			</span>
			<span class="id">{model.name !== model.id ? model.id : ''}</span>
			<span class="end"
				>{#if current}<span class="badge">{t.models.active}</span>{/if}</span
			>
		</button>
		<button class="small danger" type="button" onclick={onremove}>{t.models.removeModel}</button>
	</div>

	{#if open}
		<ModelOptions {provider} {model} {presets} {onsaved} {onerror} onclose={ontoggle} />
	{/if}
</li>

<style>
	li {
		padding: 6px 8px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}

	li.on {
		border-color: var(--brass);
	}

	.row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	/* No border and no padding of its own: the row is the box, and this is the part of it that
	   answers a click. Negative margins let the hit area reach the row's edge. */
	.toggle {
		flex: 1;
		min-width: 0;
		display: grid;
		grid-template-columns: 16rem minmax(0, 1fr) auto;
		align-items: center;
		gap: 12px;
		margin: -6px 0 -6px -8px;
		padding: 6px 0 6px 8px;
		border: 0;
		border-radius: var(--radius) 0 0 var(--radius);
		text-align: left;
		font-size: 13px;
		color: var(--text);
		cursor: pointer;
	}

	.toggle:hover .name {
		color: var(--brass);
	}

	.chevron {
		width: 12px;
		flex: none;
		font-size: 14px;
		line-height: 1;
		color: var(--text-faint);
		transition: transform var(--fade) var(--ease);
	}

	.chevron.open {
		transform: rotate(90deg);
	}

	.start,
	.end {
		display: flex;
		align-items: baseline;
		gap: 8px;
		min-width: 0;
	}

	.end {
		justify-content: flex-end;
	}

	.name {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 13px;
		color: var(--text);
		transition: color var(--fade) var(--ease);
	}

	/* The id starts at the same place on every row — the name column is a fixed width — in the
	   body face and italic: a model id is a name, not code, and monospace made it read like a field
	   somebody had forgotten to fill in. */
	.id {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 12.5px;
		font-style: italic;
		color: var(--text-faint);
	}

	.badge {
		flex: none;
		font-size: 11px;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--brass);
	}

	.badge.quiet {
		color: var(--text-faint);
	}

	.small {
		padding: 1px 8px;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 12px;
		color: var(--text-muted);
		transition:
			border-color var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	.small:hover {
		border-color: var(--text-faint);
		color: var(--text);
	}

	.danger:hover {
		border-color: var(--danger);
		color: var(--danger);
	}
</style>
