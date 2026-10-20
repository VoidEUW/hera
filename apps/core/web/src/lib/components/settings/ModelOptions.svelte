<script lang="ts">
	/**
	 * One model's request options: sampling sliders, how it thinks, its context ceiling, whether
	 * it calls tools, and the raw JSON underneath all of it.
	 *
	 * **Mounted only while open**, so closing it *is* discarding the draft — the same thing the
	 * screen did before, now without a keyed map to clean up. The draft is held as text for the
	 * reason `modelOptions.ts` gives, and the sliders write through that same text, so a slider
	 * and the textarea are one piece of state.
	 *
	 * `context_length`, `tool_calling` and `accepts_images` ride beside the options rather than inside them: they
	 * are typed fields on `ModelEntry`, not opaque options. `tool_calling` is seeded from the
	 * model rather than defaulted to `true`, so saving an unrelated option never silently turns
	 * tools back on for a model somebody already flagged off (ADR 19).
	 */
	import { untrack } from 'svelte';
	import { api, type ModelEntry, type ModelPreset, type Provider } from '$lib/api/client';
	import Checkbox from '$lib/components/Checkbox.svelte';
	import Input from '$lib/components/Input.svelte';
	import Select from '$lib/components/Select.svelte';
	import Slider from '$lib/components/Slider.svelte';
	import { t } from '$lib/i18n';
	import {
		SAMPLING_FIELDS,
		budgetOf,
		contextLengthToSave,
		maxTokensOf,
		effortsFor,
		parsed,
		shapeOf,
		sourceOf,
		tokenCountFrom,
		thinkingOn,
		withOption,
		withThinking,
		written
	} from '$lib/modelOptions';

	interface Props {
		/** The provider's name — the registry key `api.addModel` is called against. */
		provider: string;
		model: ModelEntry;
		presets: ModelPreset[];
		/** Called with the registry the server answered with, after a save. */
		onsaved: (body: { providers: Provider[]; active: string }) => void;
		onerror: (message: string) => void;
		onclose: () => void;
	}

	let { provider, model, presets, onsaved, onerror, onclose }: Props = $props();

	// Seeded once, when the editor opens. Text, for `contextText` too: an emptied field
	// mid-edit must not be forced back into a number before the person is done.
	const seed = untrack(() => model);
	let draft = $state(written(seed.options));
	let contextText = $state(seed.context_length != null ? String(seed.context_length) : '');
	let toolCalling = $state(seed.tool_calling);
	let acceptsImages = $state(seed.accepts_images);

	const valid = $derived(parsed(draft) !== null);
	const current = $derived(parsed(draft) ?? {});
	const contextValid = $derived(contextLengthToSave(contextText) !== undefined);

	function set(field: string, value: unknown) {
		draft = withOption(draft, field, value);
	}

	async function save() {
		const options = parsed(draft);
		const contextLength = contextLengthToSave(contextText);
		if (options === null || contextLength === undefined) return;
		try {
			// The same call that registers a model: an id already there is replaced, so this is
			// an edit. The server is what validates the options — the parse above only decides
			// whether the button is worth offering.
			onsaved(
				await api.addModel(provider, {
					id: model.id,
					name: model.name,
					options,
					context_length: contextLength,
					tool_calling: toolCalling,
					accepts_images: acceptsImages
				})
			);
			onclose();
		} catch (cause) {
			onerror(cause instanceof Error ? cause.message : String(cause));
		}
	}
</script>

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
					<Slider
						min={field.min}
						max={field.max}
						step={field.step}
						value={value ?? field.min}
						ariaLabel={field.label}
						onchange={(next) => set(field.key, next)}
					/>
					<input
						class="mono"
						type="number"
						step={field.step}
						placeholder={t.models.sampling.unset}
						value={value ?? ''}
						oninput={(e) => {
							const text = e.currentTarget.value;
							set(field.key, text === '' ? undefined : Number(text));
						}}
					/>
					{#if value !== undefined}
						<button
							class="clear"
							type="button"
							title={t.models.sampling.unset}
							onclick={() => set(field.key, undefined)}
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
			<!-- Whichever of the three shapes this model has,
								     decided server-side. And where nobody publishes
								     anything, a field to say it once -- which is the
								     only way the ~17 prose-only providers are
								     reachable at all. -->
			{#if shapeOf(model) === 'values'}
				<Select
					choices={effortsFor(model)}
					value={typeof current.reasoning_effort === 'string' ? current.reasoning_effort : ''}
					label={t.models.sampling.reasoningEffort}
					field
					onchange={(value) => set('reasoning_effort', value)}
				/>
			{:else if shapeOf(model) === 'toggle'}
				<Checkbox
					checked={thinkingOn(current)}
					label={t.models.sampling.thinking}
					ariaLabel={t.models.sampling.thinkingToggle}
					onchange={(on) => (draft = withThinking(draft, on))}
				/>
			{:else if shapeOf(model) === 'budget'}
				<!-- A raw number input rather than `Input`, whose
				     `kind` is a closed set of *text* kinds on
				     purpose. Matches the context-length field
				     below it. -->
				<div class="sampling-row">
					<input
						type="number"
						min="256"
						max="32768"
						step="256"
						aria-label={t.models.sampling.thinkingBudget}
						value={budgetOf(current) ?? 1024}
						onchange={(event) => set('thinking_budget', Number(event.currentTarget.value) || 1024)}
					/>
					<span class="caption">tokens</span>
				</div>
			{:else}
				<Input
					mono
					value={typeof current.reasoning_effort === 'string' ? current.reasoning_effort : ''}
					ariaLabel={t.models.sampling.reasoningEffort}
					placeholder={t.models.sampling.reasoningEffortFree}
					onchange={(value) => set('reasoning_effort', value)}
				/>
			{/if}
			<!-- Where the offered vocabulary came from. Said on
			     the screen rather than assumed, because a
			     hand-entered one can be out of date with
			     nothing failing until a turn is refused. -->
			<small>
				{t.models.sampling.thinkingSource[
					sourceOf(model) as keyof typeof t.models.sampling.thinkingSource
				] ?? t.models.sampling.thinkingSource.none}
			</small>
		</div>
	</div>

	<p class="warn note">{t.models.sampling.overrideNote}</p>

	<label>
		<span>{t.models.maxTokens}</span>
		<input
			type="number"
			min="1"
			step="1"
			placeholder={t.models.maxTokensPlaceholder}
			value={maxTokensOf(current) ?? ''}
			oninput={(e) => set('max_tokens', tokenCountFrom(e.currentTarget.value))}
		/>
		<small>{t.models.maxTokensHint}</small>
	</label>

	<label>
		<span>{t.models.contextLength}</span>
		<input
			type="number"
			min="1"
			step="1"
			placeholder={t.models.contextLengthPlaceholder}
			value={contextText}
			oninput={(e) => (contextText = e.currentTarget.value)}
		/>
		<small>{t.models.contextLengthHint}</small>
	</label>
	{#if !contextValid}
		<p class="warn">{t.models.contextLengthInvalid}</p>
	{/if}

	<div class="field">
		<span class="label">{t.models.toolCalling}</span>
		<Checkbox
			checked={toolCalling}
			ariaLabel={t.models.toolCalling}
			onchange={(checked) => (toolCalling = checked)}
		/>
		<small>{t.models.toolCallingHint}</small>
	</div>

	<div class="field">
		<span class="label">{t.models.acceptsImages}</span>
		<Checkbox
			checked={acceptsImages}
			ariaLabel={t.models.acceptsImages}
			onchange={(checked) => (acceptsImages = checked)}
		/>
		<small>{t.models.acceptsImagesHint}</small>
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
				if (chosen) draft = written(chosen.options);
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
			oninput={(e) => (draft = e.currentTarget.value)}></textarea>
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
			onclick={() => save()}
		>
			{t.models.optionsSave}
		</button>
		<button class="ghost tiny" type="button" onclick={() => (draft = '')}>
			{t.models.optionsClear}
		</button>
	</div>
</div>

<style>
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

	.tiny {
		padding: 1px 8px;
		font-size: 12px;
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
		background: var(--ground);
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
		background: var(--ground);
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

	/* `:global` reaches past `Slider.svelte`'s own scope — its root is the `<input>` itself, with
	   no wrapper `div` this rule could otherwise land on. */
	.sampling-row :global(.slider) {
		flex: 1;
	}

	/* Wide enough for the `unset` placeholder to read in full rather than clip, and the native
	   spinner is dropped — it was eating into that same width, which is what made 8ch too
	   narrow for a five-letter word to begin with. */
	.sampling-row input[type='number'] {
		width: 10ch;
		flex: none;
		padding: 3px 6px;
		font-size: 12.5px;
		text-align: center;
		appearance: textfield;
	}

	.sampling-row input[type='number']::-webkit-inner-spin-button,
	.sampling-row input[type='number']::-webkit-outer-spin-button {
		appearance: none;
		margin: 0;
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
</style>
