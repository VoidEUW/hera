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
	import Button from '$lib/components/ui/Button.svelte';
	import CloseButton from '$lib/components/ui/CloseButton.svelte';
	import NumberField from '$lib/components/ui/NumberField.svelte';
	import Textarea from '$lib/components/ui/Textarea.svelte';
	import { untrack } from 'svelte';
	import { api, type ModelEntry, type ModelPreset, type Provider } from '$lib/api/client';
	import Checkbox from '$lib/components/ui/Checkbox.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Selector from '$lib/components/ui/Selector.svelte';
	import Slider from '$lib/components/ui/Slider.svelte';
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
					<NumberField
						compact
						step={field.step}
						placeholder={t.models.sampling.unset}
						ariaLabel={field.label}
						value={value ?? null}
						onchange={(next) => set(field.key, next ?? undefined)}
					/>
					{#if value !== undefined}
						<CloseButton
							size="sm"
							label={t.models.sampling.unset}
							onclick={() => set(field.key, undefined)}
						/>
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
				<Selector
					choices={effortsFor(model)}
					value={typeof current.reasoning_effort === 'string' ? current.reasoning_effort : ''}
					label={t.models.sampling.reasoningEffort}
					onchange={(value) => set('reasoning_effort', value)}
				/>
			{:else if shapeOf(model) === 'toggle'}
				<Checkbox
					variant="switch"
					checked={thinkingOn(current)}
					label={t.models.sampling.thinking}
					ariaLabel={t.models.sampling.thinkingToggle}
					onchange={(on) => (draft = withThinking(draft, on))}
				/>
			{:else if shapeOf(model) === 'budget'}
				<NumberField
					min={256}
					max={32768}
					step={256}
					unit={t.composer.tokens}
					ariaLabel={t.models.sampling.thinkingBudget}
					value={budgetOf(current) ?? 1024}
					onchange={(next) => set('thinking_budget', next ?? 1024)}
				/>
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

	<NumberField
		min={1}
		step={1}
		unit={t.composer.tokens}
		label={t.models.maxTokens}
		help={t.models.maxTokensHint}
		placeholder={t.models.maxTokensPlaceholder}
		value={maxTokensOf(current) ?? null}
		onchange={(next) => set('max_tokens', next === null ? undefined : tokenCountFrom(String(next)))}
	/>

	<NumberField
		min={1}
		step={1}
		unit={t.composer.tokens}
		label={t.models.contextLength}
		help={t.models.contextLengthHint}
		error={contextValid ? undefined : t.models.contextLengthInvalid}
		placeholder={t.models.contextLengthPlaceholder}
		value={contextText === '' ? null : Number(contextText)}
		onchange={(next) => (contextText = next === null ? '' : String(next))}
	/>

	<Checkbox
		checked={toolCalling}
		label={t.models.toolCalling}
		description={t.models.toolCallingHint}
		onchange={(checked) => (toolCalling = checked)}
	/>

	<Checkbox
		checked={acceptsImages}
		label={t.models.acceptsImages}
		description={t.models.acceptsImagesHint}
		onchange={(checked) => (acceptsImages = checked)}
	/>

	<Selector
		caption={t.models.optionsPreset}
		choices={[
			{ value: '', label: t.models.optionsPresetNone },
			...presets.map((preset) => ({
				value: preset.id,
				label: preset.label,
				description: preset.hint
			}))
		]}
		value=""
		label={t.models.optionsPreset}
		onchange={(chosenId) => {
			const chosen = presets.find((p) => p.id === chosenId);
			if (chosen) draft = written(chosen.options);
		}}
	/>
	<Textarea
		mono
		rows={5}
		label={t.models.options}
		help={t.models.optionsRawHint}
		error={valid ? undefined : t.models.optionsInvalid}
		value={draft}
		onchange={(value) => (draft = value)}
	/>
	<div class="options-actions">
		<Button variant="ghost" size="sm" onclick={() => (draft = '')}>
			{t.models.optionsClear}
		</Button>
		<Button
			variant="highlighted"
			size="sm"
			disabled={!valid || !contextValid}
			onclick={() => save()}
		>
			{t.models.optionsSave}
		</Button>
	</div>
</div>

<style>
	/* The options editor, open only when somebody asked for it — a model that needs nothing
	   should read exactly as it did before this existed. */
	.options {
		display: flex;
		flex-direction: column;
		gap: 14px;
		padding-top: 4px;
		color: var(--text);
	}

	.explains {
		margin: 0;
		max-width: 60ch;
		color: var(--text-muted);
		font-size: 12.5px;
		line-height: 1.5;
	}

	.sampling {
		display: flex;
		flex-direction: column;
		gap: 10px;
		padding: 10px 12px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: var(--ground);
	}

	.sampling-field > span {
		display: block;
		margin-bottom: 3px;
		color: var(--text);
		font-size: 12px;
		font-weight: 500;
	}

	.sampling-row {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	/* `:global` reaches past `Slider.svelte`'s own scope. */
	.sampling-row :global(.slider) {
		flex: 1;
	}

	small {
		display: block;
		margin-top: 4px;
		color: var(--text-faint);
		font-size: 11.5px;
	}

	.options-actions {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
	}

	/* The one line calling out that a sampling field set here can silently outrank the
	   deployment's own default (`packages/hera_providers`'s `extra` merges last). */
	.warn {
		margin: 0;
		color: var(--text-faint);
		font-size: 12px;
	}
</style>
