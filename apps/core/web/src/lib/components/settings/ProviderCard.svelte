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
	import {
		api,
		type ModelPreset,
		type Probe,
		type Provider,
		type ProviderKind
	} from '$lib/api/client';
	import Input from '$lib/components/Input.svelte';
	import Select from '$lib/components/Select.svelte';
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
	const bodyId = $derived(`provider-${entry.name}`);

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
	const setActiveModel = (modelId: string) => run(() => api.activateProvider(entry.name, modelId));
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

	function readLogo(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		input.value = '';
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

<section class="entry" class:current={isActive}>
	<header>
		<h3>
			<button
				class="disclosure"
				type="button"
				aria-expanded={open}
				aria-controls={bodyId}
				onclick={ontoggle}
			>
				<span class="chevron" class:open aria-hidden="true">▸</span>
				<img
					class="logo"
					src={logoPreview(entry) || kindIcon(effectiveKind)}
					alt=""
					aria-hidden="true"
					onerror={onLogoError(effectiveKind)}
				/>
				<span class="title">{entry.name}</span>
				{#if isActive}<span class="badge">{t.models.active}</span>{/if}
			</button>
		</h3>
		{#if !isActive}
			<button class="ghost" type="button" onclick={activate}>{t.models.activate}</button>
		{/if}
	</header>

	{#if open}
		<div class="body" id={bodyId}>
			<label>
				<span>{t.models.kindLabel}</span>
				<Select
					choices={PROVIDER_KINDS.map((kind) => ({ value: kind, label: t.models.kind[kind] }))}
					value={current(entry, 'kind')}
					label={t.models.kindLabel}
					field
					onchange={(value) => edit('kind', value)}
				/>
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
							onchange={(e) => readLogo(e)}
						/>
						{#if logoPreview(entry)}
							<button class="ghost tiny" type="button" onclick={() => clearLogo()}>
								{t.models.logoClear}
							</button>
						{/if}
					</div>
					<small>{t.models.logoHint}</small>
				</label>
			{/if}

			<label>
				<span>{t.models.baseUrl}</span>
				<Input
					kind="url"
					mono
					value={current(entry, 'base_url')}
					onchange={(value) => edit('base_url', value)}
				/>
			</label>

			<label>
				<span>{t.models.apiKey}</span>
				<Input
					kind="password"
					mono
					placeholder={entry.api_key_set ? '••••••••' : ''}
					value={draft.api_key ?? ''}
					onchange={(value) => edit('api_key', value)}
				/>
				<small>{entry.api_key_set ? t.models.keyStored : t.models.keyBlank}</small>
			</label>

			<label>
				<span>{t.models.embeddingModel}</span>
				<Input
					mono
					value={current(entry, 'embedding_model')}
					onchange={(value) => edit('embedding_model', value)}
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
						if (Number.isFinite(parsed) && parsed > 0) edit('timeout_s', parsed);
					}}
				/>
				<small>{t.models.timeoutHint}</small>
			</label>

			<div class="actions">
				<button
					class="primary"
					type="button"
					disabled={Object.keys(draft).length === 0}
					onclick={save}
				>
					{t.settings.save}
				</button>
				<button class="ghost" type="button" onclick={runProbe}>
					{result === 'running' ? t.models.testing : t.models.test}
				</button>
				{#if saved}
					<span class="ok">{t.models.saved}</span>
				{/if}
				<button class="ghost danger" type="button" onclick={remove}>
					{t.models.remove}
				</button>
			</div>

			<div class="models">
				{#if entry.models.length}
					<ul class="registered" aria-label={t.models.modelsHeading}>
						{#each entry.models as model (model.id)}
							<ModelRow
								provider={entry.name}
								{model}
								current={model.id === entry.active_model}
								canActivate={isActive}
								open={openModel === model.id}
								{presets}
								ontoggle={() => (openModel = openModel === model.id ? null : model.id)}
								onactivate={() => setActiveModel(model.id)}
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
						value={newModel.id}
						onchange={(value) => (newModel = { ...newModel, id: value })}
					/>
					<Input
						mono
						placeholder={t.models.modelName}
						value={newModel.name}
						onchange={(value) => (newModel = { ...newModel, name: value })}
					/>
					<button
						class="ghost tiny"
						type="button"
						disabled={!newModel.id.trim()}
						onclick={addModel}
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
						<Input
							kind="search"
							mono
							placeholder={t.models.search}
							value={probeQuery}
							onchange={(value) => (probeQuery = value)}
						/>
					</label>
					<ul class="probed">
						{#each probeShown() as id (id)}
							{@const already = entry.models.some((m) => m.id === id)}
							<li>
								<button
									class="row"
									class:on={already}
									type="button"
									disabled={already}
									onclick={() => pickFromProbe(id)}
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
		</div>
	{/if}
</section>

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

	.entry.current .title {
		color: var(--brass);
	}

	header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
	}

	header h3 {
		flex: 1;
		min-width: 0;
	}

	/* The whole header is the control: a click on the logo, the name or the empty space beside
	   them opens or closes the card. It sits inside the `<h3>` — the usual shape for a
	   disclosure — and **Activate** sits beside the heading rather than inside the button. */
	.disclosure {
		display: flex;
		align-items: center;
		gap: 8px;
		width: 100%;
		padding: 2px 0;
		border: 0;
		text-align: left;
		font: inherit;
		color: inherit;
		cursor: pointer;
	}

	.disclosure:hover .title {
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

	.title {
		transition: color var(--fade) var(--ease);
	}

	.body {
		margin-top: 12px;
	}

	/* Spacing alone sets the model list apart from the fields above it: it is the same provider,
	   and a rule and a heading made it read as a separate section. */
	.models {
		margin-top: 20px;
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

	input {
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

	.registered {
		list-style: none;
		margin: 0 0 10px;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.add-model {
		display: flex;
		gap: 6px;
	}

	/* `:global` reaches past `Input.svelte`'s own scope — its root is the `<input>` itself, with
	   no wrapper `div` this rule could otherwise land on (same reason `Slider.svelte` needs it). */
	.add-model :global(.control) {
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

	.search :global(.control) {
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
