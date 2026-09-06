<script lang="ts">
	/**
	 * Where she runs.
	 *
	 * The first screen a person needs, because nothing else in Hera does anything until she is
	 * pointed at a model — and until now there was no way to do it without an environment
	 * variable and a restart.
	 *
	 * **Several models, one endpoint.** A provider used to carry exactly one model string. Now
	 * it carries a small registry of named ones, and switching which is active is a click on a
	 * row rather than retyping an id.
	 *
	 * **Test before you commit to it.** The endpoint is asked what models it has, and the answer
	 * either fills a searchable list or says plainly why it could not. "Nothing is listening on
	 * that port" is the commonest thing to be wrong on a fresh install, and it belongs on the
	 * screen you are already looking at. A model can also be typed in by hand — some
	 * OpenAI-compatible endpoints don't implement the listing this probe uses.
	 *
	 * **The key is write-only.** It never comes back from the API, so an empty field means
	 * "leave what is stored alone". Saying so under the field is the difference between that
	 * being a sensible rule and a trap. A custom logo follows the same rule: left alone unless a
	 * new file is chosen or explicitly cleared.
	 */
	import { api, type Probe, type Provider, type ProviderKind } from '$lib/api/client';
	import { t } from '$lib/i18n';
	import { kindFallbackIcon, kindIcon, PROVIDER_KINDS } from '$lib/providers';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	let providers = $state<Provider[]>([]);
	let active = $state('');
	let error = $state<string | null>(null);
	let saved = $state<string | null>(null);
	let probes = $state<Record<string, Probe | 'running'>>({});
	let probeQuery = $state<Record<string, string>>({});
	let adding = $state(false);

	// One draft per endpoint, so typing in a field does not fight the list refreshing under it.
	// `logo_data_url`/`logo_media_type` ride along here rather than on `Provider` itself — a
	// staged upload is not a fact about the endpoint until Save sends it.
	let drafts = $state<
		Record<string, Partial<Provider> & { api_key?: string; logo_data_url?: string }>
	>({});
	let fresh = $state({
		name: '',
		kind: 'generic' as ProviderKind,
		base_url: 'http://localhost:1234/v1',
		model_id: '',
		model_name: '',
		api_key: ''
	});

	// A model typed by hand, one draft per provider — kept apart from `drafts` because it adds
	// to the registry rather than changing a field on the endpoint itself.
	let newModel = $state<Record<string, { id: string; name: string }>>({});

	const shown = $derived(
		providers.filter(
			(p) => !filter || `${p.name} ${p.base_url} ${p.active_model}`.toLowerCase().includes(filter)
		)
	);

	$effect(() => {
		void load();
	});

	async function load() {
		try {
			const body = await api.providers();
			providers = body.providers;
			active = body.active;
			drafts = Object.fromEntries(body.providers.map((p) => [p.name, {}]));
			newModel = Object.fromEntries(body.providers.map((p) => [p.name, { id: '', name: '' }]));
			error = null;
		} catch (cause) {
			error = say(cause);
		}
	}

	function apply(body: { providers: Provider[]; active: string }) {
		providers = body.providers;
		active = body.active;
	}

	async function save(entry: Provider) {
		const patch = drafts[entry.name] ?? {};
		if (Object.keys(patch).length === 0) return;
		try {
			apply(
				await api.updateProvider(entry.name, {
					kind: patch.kind as ProviderKind | undefined,
					base_url: patch.base_url,
					api_key: patch.api_key,
					embedding_model: patch.embedding_model,
					timeout_s: patch.timeout_s,
					connect_timeout_s: patch.connect_timeout_s,
					logo_data_url: patch.logo_data_url,
					logo_media_type: patch.logo_media_type
				})
			);
			drafts = { ...drafts, [entry.name]: {} };
			saved = entry.name;
			setTimeout(() => (saved = null), 1600);
		} catch (cause) {
			error = say(cause);
		}
	}

	async function add() {
		try {
			apply(await api.addProvider({ ...fresh }));
			fresh = {
				name: '',
				kind: 'generic',
				base_url: 'http://localhost:1234/v1',
				model_id: '',
				model_name: '',
				api_key: ''
			};
			adding = false;
			error = null;
		} catch (cause) {
			error = say(cause);
		}
	}

	async function probe(name: string) {
		probes = { ...probes, [name]: 'running' };
		probeQuery = { ...probeQuery, [name]: '' };
		try {
			probes = { ...probes, [name]: await api.probeProvider(name) };
		} catch (cause) {
			probes = { ...probes, [name]: { ok: false, models: [], error: say(cause) } };
		}
	}

	function edit(name: string, field: string, value: string | number) {
		drafts = { ...drafts, [name]: { ...drafts[name], [field]: value } };
	}

	function readLogo(name: string, event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		input.value = '';
		if (!file) return;
		const reader = new FileReader();
		reader.onload = () => {
			drafts = {
				...drafts,
				[name]: {
					...drafts[name],
					logo_data_url: String(reader.result),
					logo_media_type: file.type
				}
			};
		};
		reader.readAsDataURL(file);
	}

	function clearLogo(name: string) {
		drafts = { ...drafts, [name]: { ...drafts[name], logo_data_url: '', logo_media_type: '' } };
	}

	function current(entry: Provider, field: 'base_url' | 'embedding_model' | 'kind'): string {
		const draft = drafts[entry.name]?.[field];
		return draft !== undefined ? String(draft) : entry[field];
	}

	/** What to preview for the logo: the file just chosen, the one already on disk, or nothing —
	 * a staged clear (`''`) must win over what is stored, or clicking "Remove logo" would keep
	 * showing the old picture until Save. */
	function logoPreview(entry: Provider): string {
		const draft = drafts[entry.name]?.logo_data_url;
		if (draft !== undefined) return draft;
		return entry.logo_media_type ? api.logoUrl(entry.name) : '';
	}

	/** The silence budget, in seconds, as the field shows it.
	 *
	 * Kept as a number all the way to the request rather than sent as a string: the API validates
	 * it as one, and a `""` from an emptied field would be a 422 saying "input should be a valid
	 * number" under a box the person had merely cleared to retype. An unparseable value falls
	 * back to what is stored, so clearing the field and clicking away changes nothing. */
	function seconds(entry: Provider): number {
		const draft = drafts[entry.name]?.timeout_s;
		return typeof draft === 'number' ? draft : entry.timeout_s;
	}

	async function addModel(name: string) {
		const draft = newModel[name];
		if (!draft?.id.trim()) return;
		try {
			apply(await api.addModel(name, { id: draft.id.trim(), name: draft.name.trim() }));
			newModel = { ...newModel, [name]: { id: '', name: '' } };
		} catch (cause) {
			error = say(cause);
		}
	}

	async function pickFromProbe(name: string, modelId: string) {
		// Applied as it is clicked rather than staged behind Save — the same rule the skill
		// picker uses for a set of switches: a click that needs confirming is a click you have
		// to remember you made.
		try {
			apply(await api.addModel(name, { id: modelId }));
		} catch (cause) {
			error = say(cause);
		}
	}

	async function removeModel(name: string, modelId: string) {
		try {
			apply(await api.removeModel(name, modelId));
		} catch (cause) {
			error = say(cause);
		}
	}

	async function setActiveModel(name: string, modelId: string) {
		try {
			apply(await api.activateProvider(name, modelId));
		} catch (cause) {
			error = say(cause);
		}
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

	function probeShown(entry: Provider): string[] {
		const result = probes[entry.name];
		if (!result || result === 'running' || !result.ok) return [];
		const query = (probeQuery[entry.name] ?? '').trim().toLowerCase();
		return result.models.filter((id) => !query || id.toLowerCase().includes(query));
	}

	function say(cause: unknown): string {
		return cause instanceof Error ? cause.message : String(cause);
	}
</script>

<p class="blurb">{t.models.blurb}</p>

{#if error}
	<p class="error">{error}</p>
{/if}

{#each shown as entry (entry.name)}
	{@const result = probes[entry.name]}
	{@const effectiveKind = current(entry, 'kind') as ProviderKind}
	<section class="entry" class:current={entry.name === active}>
		<header>
			<div class="identity">
				<img
					class="logo"
					src={logoPreview(entry) || kindIcon(effectiveKind)}
					alt=""
					aria-hidden="true"
					onerror={onLogoError(effectiveKind)}
				/>
				<h3>{entry.name}</h3>
			</div>
			{#if entry.name === active}
				<span class="badge">{t.models.active}</span>
			{:else}
				<button
					class="ghost"
					type="button"
					onclick={async () => apply(await api.activateProvider(entry.name))}
				>
					{t.models.activate}
				</button>
			{/if}
		</header>

		<label>
			<span>{t.models.kindLabel}</span>
			<select
				value={current(entry, 'kind')}
				onchange={(e) => edit(entry.name, 'kind', e.currentTarget.value)}
			>
				{#each PROVIDER_KINDS as kind (kind)}
					<option value={kind}>{t.models.kind[kind]}</option>
				{/each}
			</select>
		</label>

		{#if effectiveKind === 'custom'}
			<label class="logo-field">
				<span>{t.models.logo}</span>
				<div class="logo-row">
					{#if logoPreview(entry)}
						<img class="logo-preview" src={logoPreview(entry)} alt="" />
					{/if}
					<input
						type="file"
						accept="image/png,image/jpeg,image/webp,image/gif"
						onchange={(e) => readLogo(entry.name, e)}
					/>
					{#if logoPreview(entry)}
						<button class="ghost tiny" type="button" onclick={() => clearLogo(entry.name)}>
							{t.models.logoClear}
						</button>
					{/if}
				</div>
				<small>{t.models.logoHint}</small>
			</label>
		{/if}

		<label>
			<span>{t.models.baseUrl}</span>
			<input
				value={current(entry, 'base_url')}
				oninput={(e) => edit(entry.name, 'base_url', e.currentTarget.value)}
			/>
		</label>

		<label>
			<span>{t.models.apiKey}</span>
			<input
				type="password"
				placeholder={entry.api_key_set ? '••••••••' : ''}
				value={drafts[entry.name]?.api_key ?? ''}
				oninput={(e) => edit(entry.name, 'api_key', e.currentTarget.value)}
			/>
			<small>{entry.api_key_set ? t.models.keyStored : t.models.keyBlank}</small>
		</label>

		<label>
			<span>{t.models.embeddingModel}</span>
			<input
				value={current(entry, 'embedding_model')}
				oninput={(e) => edit(entry.name, 'embedding_model', e.currentTarget.value)}
			/>
			<small>{t.models.embeddingHint}</small>
		</label>

		<label>
			<span>{t.models.timeout}</span>
			<input
				type="number"
				min="1"
				step="10"
				value={seconds(entry)}
				oninput={(e) => {
					const parsed = Number(e.currentTarget.value);
					if (Number.isFinite(parsed) && parsed > 0) edit(entry.name, 'timeout_s', parsed);
				}}
			/>
			<small>{t.models.timeoutHint}</small>
		</label>

		<div class="actions">
			<button
				class="primary"
				type="button"
				disabled={Object.keys(drafts[entry.name] ?? {}).length === 0}
				onclick={() => save(entry)}
			>
				{t.settings.save}
			</button>
			<button class="ghost" type="button" onclick={() => probe(entry.name)}>
				{result === 'running' ? t.models.testing : t.models.test}
			</button>
			{#if saved === entry.name}
				<span class="ok">{t.models.saved}</span>
			{/if}
			<button
				class="ghost danger"
				type="button"
				onclick={async () => apply(await api.deleteProvider(entry.name))}
			>
				{t.models.remove}
			</button>
		</div>

		<div class="models-block">
			<h4>{t.models.modelsHeading}</h4>
			{#if entry.models.length}
				<ul class="registered">
					{#each entry.models as model (model.id)}
						<li class:on={model.id === entry.active_model}>
							<span class="what">
								<span class="name">{model.name}</span>
								{#if model.name !== model.id}<code class="hint">{model.id}</code>{/if}
							</span>
							{#if model.id === entry.active_model}
								<span class="badge">{t.models.active}</span>
							{:else if entry.name === active}
								<button
									class="ghost tiny"
									type="button"
									onclick={() => setActiveModel(entry.name, model.id)}
								>
									{t.models.setActiveModel}
								</button>
							{/if}
							<button
								class="ghost tiny danger"
								type="button"
								onclick={() => removeModel(entry.name, model.id)}
							>
								{t.models.removeModel}
							</button>
						</li>
					{/each}
				</ul>
			{:else}
				<p class="empty">{t.models.noModels}</p>
			{/if}

			<div class="add-model">
				<input
					class="mono"
					placeholder={t.models.modelId}
					value={newModel[entry.name]?.id ?? ''}
					oninput={(e) =>
						(newModel = {
							...newModel,
							[entry.name]: {
								...newModel[entry.name],
								id: e.currentTarget.value,
								name: newModel[entry.name]?.name ?? ''
							}
						})}
				/>
				<input
					placeholder={t.models.modelName}
					value={newModel[entry.name]?.name ?? ''}
					oninput={(e) =>
						(newModel = {
							...newModel,
							[entry.name]: {
								...newModel[entry.name],
								name: e.currentTarget.value,
								id: newModel[entry.name]?.id ?? ''
							}
						})}
				/>
				<button
					class="ghost tiny"
					type="button"
					disabled={!newModel[entry.name]?.id.trim()}
					onclick={() => addModel(entry.name)}
				>
					{t.models.addModel}
				</button>
			</div>
		</div>

		{#if result && result !== 'running'}
			{#if result.ok}
				<p class="ok">{t.models.reachable(result.models.length)}</p>
				<label class="search">
					<span class="sr-only">{t.models.search}</span>
					<input
						type="search"
						placeholder={t.models.search}
						value={probeQuery[entry.name] ?? ''}
						oninput={(e) => (probeQuery = { ...probeQuery, [entry.name]: e.currentTarget.value })}
					/>
				</label>
				<ul class="probed">
					{#each probeShown(entry) as id (id)}
						{@const already = entry.models.some((m) => m.id === id)}
						<li>
							<button
								class="row"
								class:on={already}
								type="button"
								disabled={already}
								onclick={() => pickFromProbe(entry.name, id)}
							>
								<span class="mark" aria-hidden="true">{already ? '✓' : ''}</span>
								<code class="id">{id}</code>
								{#if !already}<span class="add-hint">{t.models.pick}</span>{/if}
								{#if already}<span class="caption">{t.models.alreadyAdded}</span>{/if}
							</button>
						</li>
					{:else}
						<li class="empty">{t.settings.noMatch}</li>
					{/each}
				</ul>
			{:else}
				<p class="error">{t.models.unreachable} — {result.error}</p>
			{/if}
		{/if}
	</section>
{:else}
	<p class="empty">{t.models.none}</p>
{/each}

{#if adding}
	<section class="entry adding">
		<h3>{t.models.add}</h3>
		<label>
			<span>{t.models.name}</span>
			<input bind:value={fresh.name} placeholder="studio" />
			<small>{t.models.nameRule}</small>
		</label>
		<label>
			<span>{t.models.kindLabel}</span>
			<select bind:value={fresh.kind}>
				{#each PROVIDER_KINDS as kind (kind)}
					<option value={kind}>{t.models.kind[kind]}</option>
				{/each}
			</select>
		</label>
		<label>
			<span>{t.models.baseUrl}</span>
			<input bind:value={fresh.base_url} />
		</label>
		<label>
			<span>{t.models.modelId}</span>
			<input bind:value={fresh.model_id} placeholder="qwen3.6-35b" />
		</label>
		<label>
			<span>{t.models.modelName}</span>
			<input bind:value={fresh.model_name} placeholder={t.models.modelId} />
		</label>
		<label>
			<span>{t.models.apiKey}</span>
			<input type="password" bind:value={fresh.api_key} />
			<small>{t.models.keyBlank}</small>
		</label>
		<div class="actions">
			<button class="primary" type="button" disabled={!fresh.name || !fresh.model_id} onclick={add}>
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

<style>
	.blurb,
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

	.entry.current header h3 {
		color: var(--brass);
	}

	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		margin-bottom: 10px;
	}

	.identity {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}

	.logo {
		width: 20px;
		height: 20px;
		flex: none;
		border-radius: 5px;
		object-fit: cover;
	}

	h3 {
		margin: 0;
		font-size: 14px;
		font-weight: 500;
	}

	.badge {
		font-size: 11px;
		letter-spacing: 0.06em;
		text-transform: uppercase;
		color: var(--brass);
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

	input,
	select {
		width: 100%;
		padding: 7px 10px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-family: var(--font-mono);
		font-size: 13px;
	}

	small {
		display: block;
		margin-top: 3px;
		font-size: 12px;
		color: var(--text-faint);
	}

	.logo-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.logo-row input[type='file'] {
		flex: 1;
		min-width: 0;
	}

	.logo-preview {
		width: 32px;
		height: 32px;
		flex: none;
		border-radius: 6px;
		border: 1px solid var(--line);
		object-fit: cover;
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

	.danger:not(:disabled):hover {
		border-color: var(--danger);
		color: var(--danger);
	}

	.tiny {
		padding: 1px 8px;
		font-size: 12px;
	}

	.add {
		margin-top: 16px;
	}

	.models-block {
		margin-top: 14px;
		padding-top: 14px;
		border-top: 1px dashed var(--line);
	}

	.models-block h4 {
		margin: 0 0 8px;
		font-size: 12.5px;
		font-weight: 500;
		color: var(--text-muted);
	}

	.registered {
		list-style: none;
		margin: 0 0 10px;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.registered li {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 6px 8px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}

	.registered li.on {
		border-color: var(--brass);
	}

	.registered .what {
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: baseline;
		gap: 8px;
	}

	.registered .name {
		font-size: 13px;
		color: var(--text);
	}

	.registered .hint {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-size: 11.5px;
		color: var(--text-faint);
	}

	.add-model {
		display: flex;
		gap: 6px;
	}

	.add-model input {
		flex: 1;
		min-width: 0;
	}

	code {
		font-family: var(--font-mono);
		font-size: 12.5px;
	}

	.ok {
		font-size: 12.5px;
		color: var(--laurel);
	}

	.error {
		margin: 8px 0 0;
		font-size: 12.5px;
		color: var(--danger);
	}

	.search input {
		margin: 8px 0;
	}

	.probed {
		list-style: none;
		margin: 0;
		padding: 0;
		max-height: 220px;
		overflow-y: auto;
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}

	.probed li + li {
		border-top: 1px solid var(--line);
	}

	.row {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		padding: 6px 10px;
		text-align: left;
		border: 0;
		border-radius: 0;
	}

	.row.on {
		cursor: default;
	}

	.mark {
		width: 13px;
		flex: none;
		color: var(--brass);
		font-size: 11px;
	}

	.row .id {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.add-hint {
		flex: none;
		font-size: 11.5px;
		color: var(--text-faint);
	}

	.probed .empty {
		margin: 0;
		padding: 10px;
	}
</style>
