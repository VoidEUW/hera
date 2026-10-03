<script lang="ts">
	/**
	 * One registered model: a row that opens its own options when you click it.
	 *
	 * The toggle is a real `<button>` that takes all the width the row has to spare, so a click
	 * anywhere on the row's body opens or closes it, and Enter and Space do the same from the
	 * keyboard. **Set active** and **Remove** are *siblings* of that button, not children: a
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
		/** Whether this is the model her turns run on. */
		current: boolean;
		/** Whether the provider is the active one — only then is *Set active* offered, since a
		 * model on an endpoint that is not in use cannot be switched to. */
		canActivate: boolean;
		open: boolean;
		presets: ModelPreset[];
		ontoggle: () => void;
		onactivate: () => void;
		onremove: () => void;
		onsaved: (body: { providers: Provider[]; active: string }) => void;
		onerror: (message: string) => void;
	}

	let {
		provider,
		model,
		current,
		canActivate,
		open,
		presets,
		ontoggle,
		onactivate,
		onremove,
		onsaved,
		onerror
	}: Props = $props();

	const count = $derived(Object.keys(model.options).length);
</script>

<li class:on={current}>
	<div class="row">
		<button class="toggle" type="button" aria-expanded={open} onclick={ontoggle}>
			<span class="chevron" class:open aria-hidden="true">▸</span>
			<span class="what">
				<span class="name">{model.name}</span>
				{#if model.name !== model.id}<code class="hint">{model.id}</code>{/if}
				{#if count}<span class="badge quiet">{t.models.optionsSet(count)}</span>{/if}
			</span>
			{#if current}<span class="badge">{t.models.active}</span>{/if}
		</button>
		{#if !current && canActivate}
			<button class="small" type="button" onclick={onactivate}>{t.models.setActiveModel}</button>
		{/if}
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
		display: flex;
		align-items: center;
		gap: 8px;
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

	.what {
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: baseline;
		gap: 8px;
	}

	.name {
		font-size: 13px;
		color: var(--text);
		transition: color var(--fade) var(--ease);
	}

	.hint {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-family: var(--font-mono);
		font-size: 11.5px;
		color: var(--text-faint);
	}

	.badge {
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
