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
	import { api, type ModelPreset, type Provider, type ProviderKind } from '$lib/api/client';
	import Input from '$lib/components/Input.svelte';
	import Select from '$lib/components/Select.svelte';
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

	{#if adding}
		<section class="entry adding">
			<h3>{t.models.add}</h3>
			<label>
				<span>{t.models.name}</span>
				<Input
					mono
					value={fresh.name}
					placeholder="studio"
					onchange={(value) => (fresh = { ...fresh, name: value })}
				/>
				<small>{t.models.nameRule}</small>
			</label>
			<label>
				<span>{t.models.kindLabel}</span>
				<Select
					choices={PROVIDER_KINDS.map((kind) => ({ value: kind, label: t.models.kind[kind] }))}
					value={fresh.kind}
					label={t.models.kindLabel}
					field
					onchange={(value) => (fresh = { ...fresh, kind: value as ProviderKind })}
				/>
			</label>
			<label>
				<span>{t.models.baseUrl}</span>
				<Input
					kind="url"
					mono
					value={fresh.base_url}
					onchange={(value) => (fresh = { ...fresh, base_url: value })}
				/>
			</label>
			<label>
				<span>{t.models.modelId}</span>
				<Input
					mono
					value={fresh.model_id}
					placeholder="qwen3.6-35b"
					onchange={(value) => (fresh = { ...fresh, model_id: value })}
				/>
			</label>
			<label>
				<span>{t.models.modelName}</span>
				<Input
					mono
					value={fresh.model_name}
					placeholder={t.models.modelId}
					onchange={(value) => (fresh = { ...fresh, model_name: value })}
				/>
			</label>
			<label>
				<span>{t.models.apiKey}</span>
				<Input
					kind="password"
					mono
					value={fresh.api_key}
					onchange={(value) => (fresh = { ...fresh, api_key: value })}
				/>
				<small>{t.models.keyBlank}</small>
			</label>
			<div class="actions">
				<button
					class="primary"
					type="button"
					disabled={!fresh.name || !fresh.model_id}
					onclick={add}
				>
					{t.models.add}
				</button>
				<button class="ghost" type="button" onclick={() => (adding = false)}>Cancel</button>
			</div>
		</section>
	{:else}
		<button class="ghost add" type="button" onclick={() => (adding = true)}>
			<span aria-hidden="true">＋</span>
			{t.models.add}
		</button>
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

	label {
		display: block;
		margin-bottom: 10px;
	}

	label > span {
		display: block;
		font-size: 12.5px;
		color: var(--text-muted);
		margin-bottom: 3px;
	}

	small {
		display: block;
		margin-top: 3px;
		font-size: 12px;
		color: var(--text-faint);
	}

	.actions {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-top: 12px;
		flex-wrap: wrap;
	}

	button {
		padding: 5px 12px;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 13px;
		color: var(--text-muted);
		transition:
			border-color var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	button:not(:disabled):hover {
		border-color: var(--text-faint);
		color: var(--text);
	}

	button:disabled {
		opacity: 0.4;
		cursor: default;
	}

	.primary {
		border-color: var(--brass);
		color: var(--brass);
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
