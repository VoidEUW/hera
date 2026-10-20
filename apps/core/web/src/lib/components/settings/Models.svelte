<script lang="ts">
	/**
	 * Where she runs.
	 *
	 * The first screen a person needs, because nothing else in Hera does anything until she is
	 * pointed at a model.
	 *
	 * **Several models, one endpoint.** A provider carries a small registry of named models, and
	 * switching which is active is a click on a row rather than retyping an id.
	 *
	 * **Test before you commit to it.** The endpoint is asked what models it has, and the answer
	 * either fills a searchable list or says plainly why it could not. A model can also be typed in
	 * by hand — some OpenAI-compatible endpoints don't implement the listing this probe uses.
	 *
	 * This file is the list and the *add an endpoint* form. Everything about one endpoint — its
	 * fields, its models, its probe — is `ProviderCard.svelte`, and one model's options are
	 * `ModelOptions.svelte`.
	 */
	import Button from '$lib/components/ui/Button.svelte';
	import { api, type ModelPreset, type Provider, type ProviderKind } from '$lib/api/client';
	import Input from '$lib/components/ui/Input.svelte';
	import Selector from '$lib/components/ui/Selector.svelte';
	import { providers as disclosed } from '$lib/disclosure.svelte';
	import { t } from '$lib/i18n';
	import { Placeholder } from '$lib/loading.svelte';
	import { PROVIDER_KINDS } from '$lib/providers';
	import ProviderCard from './ProviderCard.svelte';
	import Rows from './Rows.svelte';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	let providers = $state<Provider[]>([]);
	let presets = $state<ModelPreset[]>([]);
	let active = $state('');
	let error = $state<string | null>(null);
	let adding = $state(false);

	const blank = () => ({
		name: '',
		kind: 'generic' as ProviderKind,
		base_url: 'http://localhost:1234/v1',
		model_id: '',
		model_name: '',
		api_key: ''
	});
	let fresh = $state(blank());

	const shown = $derived(
		providers.filter(
			(p) => !filter || `${p.name} ${p.base_url} ${p.active_model}`.toLowerCase().includes(filter)
		)
	);

	/** Only the active provider is open until somebody opens another — and a search opens what it
	 * found, because a match drawn as a collapsed header looks like no match at all. */
	const isOpen = (name: string) => disclosed.isOpen(name, name === active || filter !== '');

	/** The same placeholder and the same beat as every other settings screen (`Rows`).
	 *
	 * Set where the load begins and ends rather than through an `$effect` over a flag: both
	 * halves of a fast local fetch can happen before effects next flush, and an effect that
	 * only ever sees the `false` draws nothing. It is never set back to `true` — a refresh
	 * after a change here has a list on screen already, and replacing that with grey would be
	 * saying the screen is arriving when it is only catching up. */
	const settling = new Placeholder(true);
	$effect(() => () => settling.stop());
	const waiting = $derived(settling.shown);

	$effect(() => {
		void load();
	});

	async function load() {
		try {
			const body = await api.providers();
			providers = body.providers;
			presets = body.presets;
			active = body.active;
			error = null;
		} catch (cause) {
			error = say(cause);
		} finally {
			settling.set(false);
		}
	}

	function apply(body: { providers: Provider[]; active: string }) {
		providers = body.providers;
		active = body.active;
	}

	async function add() {
		try {
			const name = fresh.name;
			apply(await api.addProvider({ ...fresh }));
			// The one you just made is the one you want to look at.
			disclosed.set(name, true);
			fresh = blank();
			adding = false;
			error = null;
		} catch (cause) {
			error = say(cause);
		}
	}

	function say(cause: unknown): string {
		return cause instanceof Error ? cause.message : String(cause);
	}
</script>

{#if waiting}
	<Rows label={t.settings.loadingModels} />
{:else}
	{#if error}
		<p class="error">{error}</p>
	{/if}

	<div class="providers">
		{#each shown as entry (entry.name)}
			<ProviderCard
				{entry}
				{active}
				{presets}
				open={isOpen(entry.name)}
				ontoggle={() => disclosed.toggle(entry.name, entry.name === active || filter !== '')}
				onchange={apply}
				onerror={(message) => (error = message)}
			/>
		{:else}
			<p class="empty">{t.models.none}</p>
		{/each}
	</div>

	{#if adding}
		<section class="entry adding">
			<h3>{t.models.add}</h3>
			<Input
				mono
				label={t.models.name}
				help={t.models.nameRule}
				value={fresh.name}
				placeholder="studio"
				onchange={(value) => (fresh = { ...fresh, name: value })}
			/>
			<Selector
				caption={t.models.kindLabel}
				choices={PROVIDER_KINDS.map((kind) => ({ value: kind, label: t.models.kind[kind] }))}
				value={fresh.kind}
				label={t.models.kindLabel}
				onchange={(value) => (fresh = { ...fresh, kind: value as ProviderKind })}
			/>
			<Input
				kind="url"
				mono
				label={t.models.baseUrl}
				value={fresh.base_url}
				onchange={(value) => (fresh = { ...fresh, base_url: value })}
			/>
			<Input
				mono
				label={t.models.modelId}
				value={fresh.model_id}
				placeholder="qwen3.6-35b"
				onchange={(value) => (fresh = { ...fresh, model_id: value })}
			/>
			<Input
				mono
				label={t.models.modelName}
				value={fresh.model_name}
				placeholder={t.models.modelId}
				onchange={(value) => (fresh = { ...fresh, model_name: value })}
			/>
			<Input
				kind="password"
				mono
				label={t.models.apiKey}
				help={t.models.keyBlank}
				value={fresh.api_key}
				onchange={(value) => (fresh = { ...fresh, api_key: value })}
			/>
			<div class="actions">
				<Button variant="ghost" onclick={() => (adding = false)}>{t.settings.cancel}</Button>
				<Button variant="highlighted" disabled={!fresh.name || !fresh.model_id} onclick={add}>
					{t.models.add}
				</Button>
			</div>
		</section>
	{:else}
		<div class="add">
			<Button icon="plus" onclick={() => (adding = true)}>{t.models.add}</Button>
		</div>
	{/if}
{/if}

<style>
	.empty {
		margin: 0 0 16px;
		max-width: 60ch;
		font-family: var(--font-body);
		font-size: 15px;
		line-height: 1.6;
		color: var(--text-muted);
	}

	.entry {
		padding: 16px 0;
		border-bottom: 1px solid var(--line);
	}

	h3 {
		margin: 0;
		font-size: 14px;
		font-weight: 500;
	}

	.providers {
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	.adding {
		display: flex;
		flex-direction: column;
		gap: 12px;
		max-width: 520px;
	}

	.actions {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-top: 12px;
		flex-wrap: wrap;
	}

	.add {
		margin-top: 16px;
	}

	.error {
		margin: 8px 0 0;
		font-size: 12.5px;
		color: var(--danger);
	}
</style>
