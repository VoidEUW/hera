<script lang="ts">
	/**
	 * One registered endpoint: a header you can collapse, and under it the fields, the models it
	 * carries and the test that asks what else it has.
	 *
	 * **State lives here, not in the screen.** What was a record keyed by provider name — the
	 * field drafts, the probe and its search, the model being typed — is now simply the card's own,
	 * and collapsing only removes DOM: an unsaved URL survives closing and reopening the card,
	 * because the draft is not in the part that goes away. Whether the card is *open* is the
	 * screen's to say (it outlives this component, see `disclosure.svelte.ts`).
	 *
	 * **The key is write-only.** It never comes back from the API, so an empty field means "leave
	 * what is stored alone", and saying so under the field is the difference between that being a
	 * sensible rule and a trap. A custom logo follows the same rule: left alone unless a new file
	 * is chosen or explicitly cleared.
	 */
	import Button from '$lib/components/ui/Button.svelte';
	import Collapsible from '$lib/components/ui/Collapsible.svelte';
	import FileButton from '$lib/components/ui/FileButton.svelte';
	import NumberField from '$lib/components/ui/NumberField.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';
	import SearchBar from '$lib/components/ui/SearchBar.svelte';
	import {
		api,
		type ModelPreset,
		type Probe,
		type Provider,
		type ProviderKind
	} from '$lib/api/client';
	import Input from '$lib/components/ui/Input.svelte';
	import Selector from '$lib/components/ui/Selector.svelte';
	import { t } from '$lib/i18n';
	import { kindFallbackIcon, kindIcon, PROVIDER_KINDS } from '$lib/providers';
	import ModelRow from './ModelRow.svelte';

	type Registry = { providers: Provider[]; active: string };

	interface Props {
		entry: Provider;
		/** The name of the provider her turns run on. */
		active: string;
		presets: ModelPreset[];
		open: boolean;
		ontoggle: () => void;
		/** Called with whatever registry the server answered with. */
		onchange: (body: Registry) => void;
		onerror: (message: string) => void;
	}

	let { entry, active, presets, open, ontoggle, onchange, onerror }: Props = $props();

	const isActive = $derived(entry.name === active);
	function host(url: string): string {
		try {
			return new URL(url).host;
		} catch {
			return url;
		}
	}

	// Typing in a field must not fight the list refreshing under it, so edits are held here
	// until Save. `logo_data_url` rides along: a staged upload is not a fact about the endpoint
	// until Save sends it.
	let draft = $state<Partial<Provider> & { api_key?: string; logo_data_url?: string }>({});
	let saved = $state(false);
	let probeState = $state<Probe | 'running' | null>(null);
	let probeQuery = $state('');
	// A model typed by hand: it adds to the registry rather than changing a field on the endpoint.
	let newModel = $state({ id: '', name: '' });
	// Which model's options are open. One at a time per provider; `null` is none.
	let openModel = $state<string | null>(null);

	const result = $derived(probeState);
	const effectiveKind = $derived(current(entry, 'kind') as ProviderKind);

	function say(cause: unknown): string {
		return cause instanceof Error ? cause.message : String(cause);
	}

	/** Runs a registry-changing call and reports whichever way it went. */
	async function run(call: () => Promise<Registry>) {
		try {
			onchange(await call());
		} catch (cause) {
			onerror(say(cause));
		}
	}

	async function save() {
		if (Object.keys(draft).length === 0) return;
		await run(async () => {
			const body = await api.updateProvider(entry.name, {
				kind: draft.kind as ProviderKind | undefined,
				base_url: draft.base_url,
				api_key: draft.api_key,
				embedding_model: draft.embedding_model,
				timeout_s: draft.timeout_s,
				connect_timeout_s: draft.connect_timeout_s,
				logo_data_url: draft.logo_data_url,
				logo_media_type: draft.logo_media_type
			});
			draft = {};
			saved = true;
			setTimeout(() => (saved = false), 1600);
			return body;
		});
	}

	const activate = () => run(() => api.activateProvider(entry.name));
	const remove = () => run(() => api.deleteProvider(entry.name));
	const removeModel = (modelId: string) => run(() => api.removeModel(entry.name, modelId));

	async function runProbe() {
		probeState = 'running';
		probeQuery = '';
		try {
			probeState = await api.probeProvider(entry.name);
		} catch (cause) {
			probeState = { ok: false, models: [], error: say(cause) };
		}
	}

	async function addModel() {
		if (!newModel.id.trim()) return;
		await run(async () => {
			const body = await api.addModel(entry.name, {
				id: newModel.id.trim(),
				name: newModel.name.trim()
			});
			newModel = { id: '', name: '' };
			return body;
		});
	}

	// Applied as it is clicked rather than staged behind Save — the same rule the skill picker
	// uses for a set of switches: a click that needs confirming is a click you have to remember
	// you made.
	const pickFromProbe = (modelId: string) => run(() => api.addModel(entry.name, { id: modelId }));

	function edit(field: string, value: string | number) {
		draft = { ...draft, [field]: value };
	}

	function readLogo(files: FileList) {
		const file = files[0];
		if (!file) return;
		const reader = new FileReader();
		reader.onload = () => {
			draft = { ...draft, logo_data_url: String(reader.result), logo_media_type: file.type };
		};
		reader.readAsDataURL(file);
	}

	function clearLogo() {
		draft = { ...draft, logo_data_url: '', logo_media_type: '' };
	}

	function current(source: Provider, field: 'base_url' | 'embedding_model' | 'kind'): string {
		const staged = draft[field];
		return staged !== undefined ? String(staged) : source[field];
	}

	/** What to preview for the logo: the file just chosen, the one already on disk, or nothing —
	 * a staged clear (`''`) must win over what is stored, or clicking "Remove logo" would keep
	 * showing the old picture until Save. */
	function logoPreview(source: Provider): string {
		const staged = draft.logo_data_url;
		if (staged !== undefined) return staged;
		return source.logo_media_type ? api.logoUrl(source.name) : '';
	}

	/** The silence budget, in seconds, as the field shows it. Kept a number all the way to the
	 * request: the API validates it as one, and a `""` from an emptied field would be a 422 under
	 * a box the person had merely cleared to retype. */
	function seconds(source: Provider): number {
		return typeof draft.timeout_s === 'number' ? draft.timeout_s : source.timeout_s;
	}

	/** A bundled logo file can be listed and still be missing on disk — swap to the monogram
	 * rather than showing a broken image. `onerror` is removed first so a fallback that somehow
	 * also fails does not loop. */
	function onLogoError(kind: ProviderKind) {
		return (event: Event) => {
			const img = event.currentTarget as HTMLImageElement;
			img.onerror = null;
			img.src = kindFallbackIcon(kind);
		};
	}

	function probeShown(): string[] {
		if (!result || result === 'running' || !result.ok) return [];
		const query = probeQuery.trim().toLowerCase();
		return result.models.filter((id) => !query || id.toLowerCase().includes(query));
	}
</script>

<!-- One endpoint (the theme's `hera/collapsible`, "provider cards"): its logo and name on the
     header, the host under it, Active or Activate beside it; the fields, its models and the probe
     inside once opened. -->
<div class="provider">
	<Collapsible {open} lazy ontoggle={() => ontoggle()}>
		{#snippet title()}
			<span class="named">
				<img
					class="logo"
					src={logoPreview(entry) || kindIcon(effectiveKind)}
					alt=""
					onerror={onLogoError(effectiveKind)}
				/>
				{entry.name}
			</span>
		{/snippet}
		{#snippet subtitle()}{host(entry.base_url)} · {t.models.kind[effectiveKind]}{/snippet}
		{#snippet actions()}
			{#if isActive}
				<Pill tone="authority">{t.models.active}</Pill>
			{:else}
				<Button size="sm" onclick={activate}>{t.models.activate}</Button>
			{/if}
		{/snippet}

		<div class="body">
			<Selector
				caption={t.models.kindLabel}
				choices={PROVIDER_KINDS.map((kind) => ({ value: kind, label: t.models.kind[kind] }))}
				value={current(entry, 'kind')}
				label={t.models.kindLabel}
				onchange={(value) => edit('kind', value)}
			/>

			{#if effectiveKind === 'custom'}
				<div class="logo-field">
					<span class="label">{t.models.logo}</span>
					<div class="logo-row">
						{#if logoPreview(entry)}
							<img class="logo-preview" src={logoPreview(entry)} alt="" />
						{/if}
						<FileButton
							icon="image"
							label={t.models.logo}
							accept="image/png,image/jpeg,image/webp,image/gif"
							size="sm"
							onfiles={readLogo}>{t.models.logoPick}</FileButton
						>
						{#if logoPreview(entry)}
							<Button variant="ghost" size="sm" onclick={() => clearLogo()}>
								{t.models.logoClear}
							</Button>
						{/if}
					</div>
					<small>{t.models.logoHint}</small>
				</div>
			{/if}

			<Input
				kind="url"
				mono
				label={t.models.baseUrl}
				value={current(entry, 'base_url')}
				onchange={(value) => edit('base_url', value)}
			/>

			<Input
				kind="password"
				mono
				label={t.models.apiKey}
				help={entry.api_key_set ? t.models.keyStored : t.models.keyBlank}
				placeholder={entry.api_key_set ? '••••••••' : ''}
				value={draft.api_key ?? ''}
				onchange={(value) => edit('api_key', value)}
			/>

			<Input
				mono
				label={t.models.embeddingModel}
				help={t.models.embeddingHint}
				value={current(entry, 'embedding_model')}
				onchange={(value) => edit('embedding_model', value)}
			/>

			<NumberField
				label={t.models.timeout}
				help={t.models.timeoutHint}
				unit="s"
				min={1}
				step={10}
				value={seconds(entry)}
				onchange={(value) => {
					if (value !== null && value > 0) edit('timeout_s', value);
				}}
			/>

			<div class="actions">
				<Button variant="danger-soft" size="sm" icon="trash" onclick={remove}>
					{t.models.remove}
				</Button>
				<span class="space"></span>
				{#if saved}<Pill tone="live">{t.models.saved}</Pill>{/if}
				<Button size="sm" icon="refresh" busy={result === 'running'} onclick={runProbe}>
					{result === 'running' ? t.models.testing : t.models.test}
				</Button>
				<Button
					variant="highlighted"
					size="sm"
					disabled={Object.keys(draft).length === 0}
					onclick={save}
				>
					{t.settings.save}
				</Button>
			</div>

			<div class="models">
				<span class="label">{t.models.modelsHeading}</span>
				{#if entry.models.length}
					<ul class="registered" aria-label={t.models.modelsHeading}>
						{#each entry.models as model (model.id)}
							<ModelRow
								provider={entry.name}
								{model}
								current={model.id === entry.active_model}
								open={openModel === model.id}
								{presets}
								ontoggle={() => (openModel = openModel === model.id ? null : model.id)}
								onremove={() => removeModel(model.id)}
								onsaved={onchange}
								{onerror}
							/>
						{/each}
					</ul>
				{:else}
					<p class="empty">{t.models.noModels}</p>
				{/if}

				<div class="add-model">
					<Input
						mono
						placeholder={t.models.modelId}
						ariaLabel={t.models.modelId}
						value={newModel.id}
						onchange={(value) => (newModel = { ...newModel, id: value })}
					/>
					<Input
						mono
						placeholder={t.models.modelName}
						ariaLabel={t.models.modelName}
						value={newModel.name}
						onchange={(value) => (newModel = { ...newModel, name: value })}
					/>
					<Button size="sm" icon="plus" disabled={!newModel.id.trim()} onclick={addModel}>
						{t.models.addModel}
					</Button>
				</div>
			</div>

			{#if result && result !== 'running'}
				{#if result.ok}
					<Pill tone="live">{t.models.reachable(result.models.length)}</Pill>
					<SearchBar
						placeholder={t.models.search}
						value={probeQuery}
						onchange={(value) => (probeQuery = value)}
					/>
					<ul class="probed">
						{#each probeShown() as id (id)}
							{@const already = entry.models.some((m) => m.id === id)}
							<li>
								<code class="id">{id}</code>
								{#if already}
									<Pill tone="live">{t.models.alreadyAdded}</Pill>
								{:else}
									<Button variant="ghost" size="sm" icon="plus" onclick={() => pickFromProbe(id)}>
										{t.models.pick}
									</Button>
								{/if}
							</li>
						{:else}
							<li class="empty">{t.settings.noMatch}</li>
						{/each}
					</ul>
				{:else}
					<p class="error">{t.models.unreachable} — {result.error}</p>
				{/if}
			{/if}
		</div>
	</Collapsible>
</div>

<style>
	.named {
		display: inline-flex;
		align-items: center;
		gap: 8px;
	}

	.logo {
		width: var(--icon-size);
		height: var(--icon-size);
		object-fit: contain;
	}

	.body {
		display: flex;
		flex-direction: column;
		gap: 14px;
		max-width: 560px;
		color: var(--text);
	}

	.label {
		color: var(--text);
		font-size: 12px;
		font-weight: 500;
	}

	.logo-field {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.logo-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.logo-preview {
		width: 28px;
		height: 28px;
		border-radius: var(--radius-sm);
		object-fit: contain;
	}

	small {
		color: var(--text-faint);
		font-size: 11.5px;
	}

	.actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px;
	}

	.space {
		flex: 1;
	}

	.models {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.registered {
		display: flex;
		flex-direction: column;
		gap: 6px;
		margin: 0;
		padding: 0;
	}

	.add-model {
		display: grid;
		grid-template-columns: 1fr 1fr auto;
		gap: 8px;
		align-items: center;
	}

	.probed {
		display: flex;
		flex-direction: column;
		max-height: 260px;
		margin: 0;
		padding: 4px;
		overflow-y: auto;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		list-style: none;
	}

	.probed li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		min-height: 32px;
		padding: 0 4px 0 9px;
		border-radius: max(calc(var(--radius) - 4px), 2px);
	}

	.probed li:hover {
		background: var(--hover);
	}

	.id {
		overflow: hidden;
		font: 12.5px var(--font-mono);
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.empty {
		margin: 0;
		color: var(--text-faint);
		font-size: 13px;
	}

	.error {
		margin: 0;
		color: var(--danger);
		font-size: 12.5px;
	}
</style>
