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
	import {
		api,
		type ModelEntry,
		type ModelPreset,
		type Probe,
		type Provider,
		type ProviderKind
	} from '$lib/api/client';
	import Checkbox from '$lib/components/Checkbox.svelte';
	import Select from '$lib/components/Select.svelte';
	import { t } from '$lib/i18n';
	import { Placeholder } from '$lib/loading.svelte';
	import { kindFallbackIcon, kindIcon, PROVIDER_KINDS } from '$lib/providers';
	import Rows from './Rows.svelte';

	/** The five sampling keys offered as sliders over `ModelEntry.options` (ADR 18 — still an
	 * opaque pass-through, just with a form over the JSON instead of a blank textarea). Bounds
	 * are soft: the slider clamps to them, the paired number field does not, since someone
	 * hand-tuning a `repeat_penalty` of 2.3 should not be blocked by a guessed ceiling. */
	const SAMPLING_FIELDS: {
		key: string;
		label: string;
		min: number;
		max: number;
		step: number;
	}[] = [
		{ key: 'temperature', label: t.models.sampling.temperature, min: 0, max: 2, step: 0.05 },
		{ key: 'top_p', label: t.models.sampling.topP, min: 0, max: 1, step: 0.01 },
		{ key: 'top_k', label: t.models.sampling.topK, min: 0, max: 100, step: 1 },
		{ key: 'min_p', label: t.models.sampling.minP, min: 0, max: 1, step: 0.01 },
		{ key: 'repeat_penalty', label: t.models.sampling.repeatPenalty, min: 0.5, max: 2, step: 0.01 }
	];

	const REASONING_CHOICES = [
		{ value: '', label: t.composer.effort.default },
		{ value: 'low', label: t.composer.effort.low },
		{ value: 'medium', label: t.composer.effort.medium },
		{ value: 'high', label: t.composer.effort.high }
	];

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	let providers = $state<Provider[]>([]);
	let presets = $state<ModelPreset[]>([]);
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

	// The options editor, keyed by `provider/model`. Held as *text* rather than as an object,
	// because half-typed JSON is the normal state of a textarea and a person must be able to be
	// mid-edit without the field fighting them. `null` is closed.
	let optionsDraft = $state<Record<string, string>>({});

	// `context_length` rides beside the options editor rather than inside it — a typed field on
	// `ModelEntry`, not one of its opaque `options`. Text, same reason as `optionsDraft`: an
	// emptied field mid-edit must not be forced back into a number before the person is done.
	let contextDraft = $state<Record<string, string>>({});

	// `tool_calling` (ADR 19), the same way — a typed field beside the options editor, seeded
	// from the model rather than defaulted to `true`, so saving an unrelated option never
	// silently turns tools back on for a model somebody already flagged off.
	let toolCallingDraft = $state<Record<string, boolean>>({});

	const shown = $derived(
		providers.filter(
			(p) => !filter || `${p.name} ${p.base_url} ${p.active_model}`.toLowerCase().includes(filter)
		)
	);

	/** The same placeholder and the same beat as every other settings screen (`Rows`).
	 *
	 * Set where the load begins and ends rather than through an `$effect` over a flag: both
	 * halves of a fast local fetch can happen before effects next flush, and an effect that
	 * only ever sees the `false` draws nothing. It is never set back to `true` — a refresh
	 * after a change here has a list on screen already, and replacing that with grey would be
	 * saying the screen is arriving when it is only catching up.
	 */
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
			drafts = Object.fromEntries(body.providers.map((p) => [p.name, {}]));
			newModel = Object.fromEntries(body.providers.map((p) => [p.name, { id: '', name: '' }]));
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

	// -- request options, per registered model ------------------------------------------------

	const optionsKey = (name: string, modelId: string) => `${name}/${modelId}`;

	/** Closes one editor. A new object rather than `delete`, so the rune sees the change. */
	function closeOptions(key: string) {
		optionsDraft = Object.fromEntries(Object.entries(optionsDraft).filter(([k]) => k !== key));
		contextDraft = Object.fromEntries(Object.entries(contextDraft).filter(([k]) => k !== key));
		toolCallingDraft = Object.fromEntries(
			Object.entries(toolCallingDraft).filter(([k]) => k !== key)
		);
	}

	function toggleOptions(name: string, model: ModelEntry) {
		const key = optionsKey(name, model.id);
		if (key in optionsDraft) {
			closeOptions(key);
			return;
		}
		optionsDraft = { ...optionsDraft, [key]: written(model.options) };
		contextDraft = {
			...contextDraft,
			[key]: model.context_length != null ? String(model.context_length) : ''
		};
		toolCallingDraft = { ...toolCallingDraft, [key]: model.tool_calling };
	}

	/** Set or clear one key in a model's options, through the same text the raw textarea reads
	 * and writes — a slider and the JSON underneath it are one piece of state, never two that
	 * could drift. `parsed()` already returns `{}` for an empty field and `null` for invalid
	 * JSON, so a structured control touched mid-invalid-edit sees "nothing set" rather than
	 * throwing, and starts a clean object from there. */
	function updateOption(name: string, model: ModelEntry, field: string, value: unknown) {
		const key = optionsKey(name, model.id);
		const current = { ...(parsed(optionsDraft[key] ?? '') ?? {}) };
		if (value === undefined || value === '') delete current[field];
		else current[field] = value;
		optionsDraft = { ...optionsDraft, [key]: written(current) };
	}

	/** How stored options are shown: pretty-printed, and an empty set as an empty field rather
	 * than as `{}` — a person opening the editor on a model that needs nothing should find room
	 * to type, not a token to delete first. */
	function written(options: Record<string, unknown>): string {
		return Object.keys(options).length ? JSON.stringify(options, null, 2) : '';
	}

	/** The draft as an object, or `null` while it is not valid JSON yet. An empty field is `{}`,
	 * which is how the editor clears options: saving nothing means nothing is sent. */
	function parsed(text: string): Record<string, unknown> | null {
		if (!text.trim()) return {};
		try {
			const value: unknown = JSON.parse(text);
			return value && typeof value === 'object' && !Array.isArray(value)
				? (value as Record<string, unknown>)
				: null;
		} catch {
			return null;
		}
	}

	/** `contextDraft`'s text as a number to send, or `null` for "no ceiling" — mirrors how an
	 * emptied `options` textarea means "send nothing", not "send the previous value". Invalid
	 * text (not blank, not a positive number) reports itself as `undefined` so the caller can
	 * refuse to save rather than silently clearing a typo. */
	function contextLengthToSave(text: string): number | null | undefined {
		const trimmed = text.trim();
		if (!trimmed) return null;
		const parsedValue = Number(trimmed);
		return Number.isFinite(parsedValue) && parsedValue > 0 ? parsedValue : undefined;
	}

	async function saveOptions(name: string, model: ModelEntry) {
		const key = optionsKey(name, model.id);
		const options = parsed(optionsDraft[key] ?? '');
		const contextLength = contextLengthToSave(contextDraft[key] ?? '');
		if (options === null || contextLength === undefined) return;
		try {
			// The same call that registers a model: an id already there is replaced, so this is
			// an edit. The server is what validates the options — the parse above only decides
			// whether the button is worth offering.
			apply(
				await api.addModel(name, {
					id: model.id,
					name: model.name,
					options,
					context_length: contextLength,
					tool_calling: toolCallingDraft[key] ?? model.tool_calling
				})
			);
			closeOptions(key);
			saved = name;
			setTimeout(() => (saved = null), 1600);
		} catch (cause) {
			error = say(cause);
		}
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

{#if waiting}
	<Rows label={t.settings.loadingModels} />
{:else}
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
				<Select
					choices={PROVIDER_KINDS.map((kind) => ({ value: kind, label: t.models.kind[kind] }))}
					value={current(entry, 'kind')}
					label={t.models.kindLabel}
					field
					onchange={(value) => edit(entry.name, 'kind', value)}
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
							{@const key = optionsKey(entry.name, model.id)}
							{@const draft = optionsDraft[key]}
							{@const count = Object.keys(model.options).length}
							<li class:on={model.id === entry.active_model}>
								<div class="row">
									<span class="what">
										<span class="name">{model.name}</span>
										{#if model.name !== model.id}<code class="hint">{model.id}</code>{/if}
										{#if count}<span class="badge quiet">{t.models.optionsSet(count)}</span>{/if}
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
										class="ghost tiny"
										type="button"
										aria-expanded={draft !== undefined}
										onclick={() => toggleOptions(entry.name, model)}
									>
										{t.models.optionsOpen}
									</button>
									<button
										class="ghost tiny danger"
										type="button"
										onclick={() => removeModel(entry.name, model.id)}
									>
										{t.models.removeModel}
									</button>
								</div>

								{#if draft !== undefined}
									{@const valid = parsed(draft) !== null}
									{@const current = parsed(draft) ?? {}}
									{@const contextValid = contextLengthToSave(contextDraft[key] ?? '') !== undefined}
									<div class="options">
										<!-- Not `hint`: that class is the one-line ellipsised model id above, and
									     this is a sentence that has to wrap. -->
										<p class="explains">{t.models.optionsHint}</p>

										<div class="sampling">
											{#each SAMPLING_FIELDS as field (field.key)}
												{@const raw = current[field.key]}
												{@const value = typeof raw === 'number' ? raw : undefined}
												<div class="sampling-field">
													<span>{field.label}</span>
													<div class="sampling-row">
														<input
															type="range"
															min={field.min}
															max={field.max}
															step={field.step}
															value={value ?? field.min}
															oninput={(e) =>
																updateOption(
																	entry.name,
																	model,
																	field.key,
																	Number(e.currentTarget.value)
																)}
														/>
														<input
															class="mono"
															type="number"
															step={field.step}
															placeholder={t.models.sampling.unset}
															value={value ?? ''}
															oninput={(e) => {
																const text = e.currentTarget.value;
																updateOption(
																	entry.name,
																	model,
																	field.key,
																	text === '' ? undefined : Number(text)
																);
															}}
														/>
														{#if value !== undefined}
															<button
																class="clear"
																type="button"
																title={t.models.sampling.unset}
																onclick={() =>
																	updateOption(entry.name, model, field.key, undefined)}
															>
																<span class="sr-only">{t.models.sampling.unset}</span>
																<span aria-hidden="true">✕</span>
															</button>
														{/if}
													</div>
												</div>
											{/each}

											<div class="sampling-field">
												<span>{t.models.sampling.reasoningEffort}</span>
												<Select
													choices={REASONING_CHOICES}
													value={typeof current.reasoning_effort === 'string'
														? current.reasoning_effort
														: ''}
													label={t.models.sampling.reasoningEffort}
													field
													onchange={(value) =>
														updateOption(entry.name, model, 'reasoning_effort', value)}
												/>
												<small>{t.models.sampling.reasoningEffortHint}</small>
											</div>
										</div>

										<p class="warn note">{t.models.sampling.overrideNote}</p>

										<label>
											<span>{t.models.contextLength}</span>
											<input
												type="number"
												min="1"
												step="1"
												placeholder={t.models.contextLengthPlaceholder}
												value={contextDraft[key] ?? ''}
												oninput={(e) =>
													(contextDraft = { ...contextDraft, [key]: e.currentTarget.value })}
											/>
											<small>{t.models.contextLengthHint}</small>
										</label>
										{#if !contextValid}
											<p class="warn">{t.models.contextLengthInvalid}</p>
										{/if}

										<div class="field">
											<span class="label">{t.models.toolCalling}</span>
											<Checkbox
												checked={toolCallingDraft[key] ?? model.tool_calling}
												ariaLabel={t.models.toolCalling}
												onchange={(checked) =>
													(toolCallingDraft = {
														...toolCallingDraft,
														[key]: checked
													})}
											/>
											<small>{t.models.toolCallingHint}</small>
										</div>

										<label>
											<span>{t.models.optionsPreset}</span>
											<Select
												choices={[
													{ value: '', label: t.models.optionsPresetNone },
													...presets.map((preset) => ({
														value: preset.id,
														label: preset.label,
														hint: preset.hint
													}))
												]}
												value=""
												label={t.models.optionsPreset}
												field
												onchange={(chosenId) => {
													const chosen = presets.find((p) => p.id === chosenId);
													if (chosen)
														optionsDraft = { ...optionsDraft, [key]: written(chosen.options) };
												}}
											/>
										</label>
										<label>
											<span>{t.models.options}</span>
											<textarea
												class="mono"
												rows="5"
												spellcheck="false"
												value={draft}
												oninput={(e) =>
													(optionsDraft = { ...optionsDraft, [key]: e.currentTarget.value })}
											></textarea>
											<small>{t.models.optionsRawHint}</small>
										</label>
										{#if !valid}
											<p class="warn">{t.models.optionsInvalid}</p>
										{/if}
										<div class="options-actions">
											<button
												class="ghost tiny"
												type="button"
												disabled={!valid || !contextValid}
												onclick={() => saveOptions(entry.name, model)}
											>
												{t.models.optionsSave}
											</button>
											<button
												class="ghost tiny"
												type="button"
												onclick={() => (optionsDraft = { ...optionsDraft, [key]: '' })}
											>
												{t.models.optionsClear}
											</button>
										</div>
									</div>
								{/if}
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

	/* The same shape as a `label` block, for the one control that brings its own label — a
	   `Checkbox` rooted in a `<label>` of its own, and nested labels are invalid HTML that
	   announce twice. The wrapper carries the layout; the text rides on the control. */
	.field {
		display: block;
		margin-bottom: 10px;
	}

	label > span,
	.field > .label {
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
		padding: 6px 8px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}

	.registered li.on {
		border-color: var(--brass);
	}

	.registered .row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	/* The options editor, open only when somebody asked for it — a model that needs nothing
	   should read exactly as it did before this existed. */
	.options {
		margin-top: 8px;
		padding-top: 8px;
		border-top: 1px solid var(--line);
	}

	.options .explains {
		margin: 0 0 8px;
		max-width: 60ch;
		font-family: var(--font-body);
		font-size: 12.5px;
		line-height: 1.5;
		color: var(--text-muted);
	}

	.options textarea {
		width: 100%;
		padding: 7px 10px;
		background: var(--bg);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-family: var(--font-mono);
		font-size: 12.5px;
		line-height: 1.5;
		resize: vertical;
	}

	.sampling {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin-bottom: 10px;
		padding: 10px;
		background: var(--bg);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}

	.sampling-field span {
		display: block;
		font-size: 12px;
		color: var(--text-muted);
		margin-bottom: 3px;
	}

	.sampling-row {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.sampling-row input[type='range'] {
		flex: 1;
		width: auto;
		padding: 0;
		background: none;
		border: none;
	}

	.sampling-row input[type='number'] {
		width: 8ch;
		flex: none;
		padding: 3px 6px;
		font-size: 12.5px;
	}

	.sampling-row .clear {
		flex: none;
		padding: 1px 6px;
		font-size: 11px;
		color: var(--text-faint);
	}

	.sampling-row .clear:hover {
		color: var(--danger);
	}

	.options-actions {
		display: flex;
		gap: 6px;
	}

	.warn {
		margin: 0 0 8px;
		font-family: var(--font-body);
		font-size: 12.5px;
		color: var(--text-muted);
	}

	/* The one line calling out that a sampling field set here can silently outrank the
	   deployment's own default (`packages/hera_providers`'s `extra` merges last) — worth saying
	   plainly now that this form is the encouraged way to set it, not a JSON edge case. */
	.warn.note {
		color: var(--text-faint);
	}

	.badge.quiet {
		color: var(--text-faint);
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
