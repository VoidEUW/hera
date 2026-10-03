/**
 * What a model's request options look like to the Models screen: text in, text out.
 *
 * The editor holds a model's options as *text*, because half-typed JSON is the normal state of
 * a textarea and a person must be able to be mid-edit without the field fighting them. Everything
 * here is therefore a function over that text — `parsed` to read it, `written` to show an
 * object, `withOption` and `withThinking` to change one key through the same text the raw
 * textarea shows — so a slider and the JSON underneath it are one piece of state, never two
 * that could drift (ADR 18: the options themselves stay an opaque pass-through).
 */
import type { ModelEntry } from '$lib/api/client';
import type { Choice } from '$lib/components/Select.svelte';
import { t } from '$lib/i18n';

/** The five sampling keys offered as sliders over `ModelEntry.options`. Bounds are soft: the
 * slider clamps to them, the paired number field does not, since someone hand-tuning a
 * `repeat_penalty` of 2.3 should not be blocked by a guessed ceiling. */
export const SAMPLING_FIELDS: {
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

/** The three shapes of thinking control, decided server-side so this screen and the composer
 * cannot disagree: `values` is a picker of the levels the model accepts, `budget` a number of
 * tokens, `toggle` a switch, and `none` the case where nobody publishes anything and the person
 * says it once. */
export const shapeOf = (model: ModelEntry): string => model.thinking_shape ?? 'none';
export const sourceOf = (model: ModelEntry): string => model.thinking_source ?? 'none';
export const effortsFor = (model: ModelEntry): Choice[] => [
	{ value: '', label: t.composer.effort.default },
	...(model.reasoning_efforts ?? []).map((effort) => ({ value: effort, label: effort }))
];

type Options = Record<string, unknown>;

/** What this model reads out of its options for a thinking *budget*, or `undefined` for none.
 * Zero is not a budget: some servers read it as *think as little as possible* rather than
 * *do not think*, so it is treated as absent here too. */
export function budgetOf(current: Options | null | undefined): number | undefined {
	const raw = current?.thinking_budget;
	return typeof raw === 'number' && raw > 0 ? raw : undefined;
}

/** Whether the model is thinking, which is the *absence* of `enable_thinking: false`.
 *
 * A boolean knob has no third state, so the model's own default — which for MiniCPM5 is to
 * think — is what an untouched configuration gets, and the switch shows that rather than an
 * "off" that was never set. */
export function thinkingOn(current: Options | null | undefined): boolean {
	const bag = current?.chat_template_kwargs;
	if (typeof bag !== 'object' || bag === null || Array.isArray(bag)) return true;
	return (bag as Options).enable_thinking !== false;
}

/** How stored options are shown: pretty-printed, and an empty set as an empty field rather
 * than as `{}` — a person opening the editor on a model that needs nothing should find room
 * to type, not a token to delete first. */
export function written(options: Options): string {
	return Object.keys(options).length ? JSON.stringify(options, null, 2) : '';
}

/** The draft as an object, or `null` while it is not valid JSON yet. An empty field is `{}`,
 * which is how the editor clears options: saving nothing means nothing is sent. */
export function parsed(text: string): Options | null {
	if (!text.trim()) return {};
	try {
		const value: unknown = JSON.parse(text);
		return value && typeof value === 'object' && !Array.isArray(value) ? (value as Options) : null;
	} catch {
		return null;
	}
}

/** The context-length field's text as a number to send, or `null` for "no ceiling" — mirrors
 * how an emptied `options` textarea means "send nothing", not "send the previous value".
 * Invalid text (not blank, not a positive number) reports itself as `undefined` so the caller
 * can refuse to save rather than silently clearing a typo. */
export function contextLengthToSave(text: string): number | null | undefined {
	const trimmed = text.trim();
	if (!trimmed) return null;
	const value = Number(trimmed);
	return Number.isFinite(value) && value > 0 ? value : undefined;
}

/** Set or clear one key. `parsed()` returns `{}` for an empty field and `null` for invalid
 * JSON, so a structured control touched mid-invalid-edit sees "nothing set" rather than
 * throwing, and starts a clean object from there. */
export function withOption(text: string, field: string, value: unknown): string {
	const current = { ...(parsed(text) ?? {}) };
	if (value === undefined || value === '') delete current[field];
	else current[field] = value;
	return written(current);
}

/** Merged, never replaced. `chat_template_kwargs` is a bag of template variables that belongs
 * to somebody else — the GLM-4.7 preset lives in it as `clear_thinking` — so this reaches into
 * it and touches one key, and an emptied bag is removed rather than left as `{}`. */
export function withThinking(text: string, on: boolean): string {
	const current = { ...(parsed(text) ?? {}) };
	const existing = current.chat_template_kwargs;
	const bag =
		typeof existing === 'object' && existing !== null && !Array.isArray(existing)
			? { ...(existing as Options) }
			: {};
	if (on) bag.enable_thinking = true;
	else delete bag.enable_thinking;
	if (Object.keys(bag).length) current.chat_template_kwargs = bag;
	else delete current.chat_template_kwargs;
	return written(current);
}
