<script lang="ts">
	/**
	 * One registered model (the theme's `hera/collapsible`, "model rows"): its name and id on the
	 * header, how many options it carries and whether it is the one in use as pills, Remove beside
	 * the header rather than inside it, and its options inside once opened.
	 *
	 * `lazy`, because the options editor reads presets and holds a draft — twenty closed rows should
	 * cost nothing. Whether a row is open is the parent's to say: a provider has one open model at a
	 * time, so that is one value there rather than a flag in every row.
	 */
	import Button from '$lib/components/ui/Button.svelte';
	import Collapsible from '$lib/components/ui/Collapsible.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';
	import type { ModelEntry, ModelPreset, Provider } from '$lib/api/client';
	import { t } from '$lib/i18n';
	import ModelOptions from './ModelOptions.svelte';

	interface Props {
		provider: string;
		model: ModelEntry;
		/** Whether this is the model her turns run on. Switching it is the composer's job. */
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

<li>
	<Collapsible {open} lazy ontoggle={() => ontoggle()}>
		{#snippet title()}{model.name}{/snippet}
		{#snippet subtitle()}{model.name !== model.id ? model.id : t.models.sameId}{/snippet}
		{#snippet actions()}
			{#if count}<Pill>{t.models.optionsSet(count)}</Pill>{/if}
			{#if current}<Pill tone="authority">{t.models.active}</Pill>{/if}
			<Button variant="danger-soft" size="sm" onclick={onremove}>{t.models.removeModel}</Button>
		{/snippet}
		<ModelOptions {provider} {model} {presets} {onsaved} {onerror} onclose={ontoggle} />
	</Collapsible>
</li>

<style>
	li {
		list-style: none;
	}
</style>
