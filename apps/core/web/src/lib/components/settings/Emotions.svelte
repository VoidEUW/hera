<script lang="ts">
	/**
	 * The stances she can show, and what each one means.
	 *
	 * Its own screen rather than a corner of Mind, because it is a *list* and the Mind screen
	 * is a set of text editors. It is also the one place where a change is visible twice: the
	 * description goes into her prompt, and the tone is the colour the card is drawn in — the
	 * same list feeding both is why neither can go stale (ADR 3).
	 *
	 * Editing is direct. There is no save button per row and no draft state to lose: a field
	 * blurs, the whole list is written, and the next turn uses it. **Reset** puts the shipped
	 * vocabulary back by deleting the file, so "reset" and "never touched" are the same state.
	 */
	import { api, type Emotion } from '$lib/api/client';
	import { t } from '$lib/i18n';
	import { workspace } from '$lib/stores/workspace.svelte';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	const TONES: Array<Emotion['tone']> = ['warm', 'cool', 'sharp', 'soft'];

	let emotions = $state<Emotion[]>([]);
	let customised = $state(false);
	let problem = $state('');
	let error = $state<string | null>(null);
	let adding = $state(false);
	let fresh = $state<Emotion>({ kind: '', description: '', tone: 'soft' });

	const shown = $derived(
		emotions.filter(
			(emotion) =>
				!filter || `${emotion.kind} ${emotion.description}`.toLowerCase().includes(filter)
		)
	);

	$effect(() => {
		void load();
	});

	async function load() {
		try {
			apply(await api.emotions());
		} catch (cause) {
			error = say(cause);
		}
	}

	function apply(body: { emotions: Emotion[]; customised: boolean; problem: string }) {
		emotions = body.emotions;
		customised = body.customised;
		problem = body.problem;
		error = null;
		// The card reads the same list, so the conversation behind this modal is correct the
		// moment it closes rather than on the next reload.
		workspace.emotions = body.emotions;
	}

	async function write(next: Emotion[]) {
		const previous = emotions;
		emotions = next;
		try {
			apply(await api.writeEmotions(next));
		} catch (cause) {
			emotions = previous;
			error = say(cause);
		}
	}

	function edit(kind: string, changes: Partial<Emotion>) {
		void write(emotions.map((entry) => (entry.kind === kind ? { ...entry, ...changes } : entry)));
	}

	function remove(kind: string) {
		if (emotions.length <= 1) return;
		void write(emotions.filter((entry) => entry.kind !== kind));
	}

	async function add() {
		const kind = fresh.kind.trim().toLowerCase();
		if (!kind || emotions.some((entry) => entry.kind === kind)) return;
		await write([...emotions, { ...fresh, kind }]);
		fresh = { kind: '', description: '', tone: 'soft' };
		adding = false;
	}

	async function reset() {
		try {
			apply(await api.resetEmotions());
		} catch (cause) {
			error = say(cause);
		}
	}

	function say(cause: unknown): string {
		return cause instanceof Error ? cause.message : String(cause);
	}
</script>

<p class="blurb">{t.emotions.blurb}</p>

{#if error}<p class="problem caption">{error}</p>{/if}
{#if problem}<p class="problem caption">{problem}</p>{/if}

{#each shown as emotion (emotion.kind)}
	<section class="row" data-tone={emotion.tone}>
		<span class="dot" aria-hidden="true"></span>

		<div class="fields">
			<span class="kind mono">{emotion.kind}</span>
			<input
				class="description"
				value={emotion.description}
				placeholder={t.emotions.when}
				aria-label={t.emotions.when}
				onblur={(event) => edit(emotion.kind, { description: event.currentTarget.value })}
			/>
			<label class="tone">
				<span class="sr-only">{t.emotions.tone}</span>
				<select
					value={emotion.tone}
					onchange={(event) =>
						edit(emotion.kind, { tone: event.currentTarget.value as Emotion['tone'] })}
				>
					{#each TONES as tone (tone)}
						<option value={tone}>{t.emotions.tones[tone]}</option>
					{/each}
				</select>
			</label>
			<button
				class="drop"
				type="button"
				disabled={emotions.length <= 1}
				onclick={() => remove(emotion.kind)}
			>
				<span class="sr-only">{t.emotions.remove}</span>
				<span aria-hidden="true">✕</span>
			</button>
		</div>
	</section>
{:else}
	<p class="empty">{t.settings.noMatch}</p>
{/each}

{#if adding}
	<section class="row adding" data-tone={fresh.tone}>
		<span class="dot" aria-hidden="true"></span>
		<div class="fields">
			<input
				class="kind mono"
				bind:value={fresh.kind}
				placeholder={t.emotions.kind}
				aria-label={t.emotions.kind}
			/>
			<input
				class="description"
				bind:value={fresh.description}
				placeholder={t.emotions.when}
				aria-label={t.emotions.when}
			/>
			<label class="tone">
				<span class="sr-only">{t.emotions.tone}</span>
				<select bind:value={fresh.tone}>
					{#each TONES as tone (tone)}
						<option value={tone}>{t.emotions.tones[tone]}</option>
					{/each}
				</select>
			</label>
			<button class="save" type="button" onclick={add}>{t.emotions.save}</button>
		</div>
	</section>
{/if}

<div class="foot">
	{#if !adding}
		<button class="action" type="button" onclick={() => (adding = true)}>{t.emotions.add}</button>
	{:else}
		<button class="action" type="button" onclick={() => (adding = false)}>
			{t.emotions.cancel}
		</button>
	{/if}
	{#if customised}
		<button class="action" type="button" onclick={reset}>{t.emotions.reset}</button>
	{/if}
</div>

<style>
	.blurb {
		margin: 0 0 14px;
		max-width: 62ch;
		font-family: var(--font-body);
		font-size: 15px;
		line-height: 1.6;
		color: var(--text-muted);
	}

	.row {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 8px 0;
		border-bottom: 1px solid var(--line);
	}

	/* The same four tones the card is drawn in, so what you pick here is what you will see. */
	.row[data-tone='warm'] {
		--edge: var(--brass);
	}
	.row[data-tone='cool'] {
		--edge: var(--laurel);
	}
	.row[data-tone='sharp'] {
		--edge: var(--brass);
	}
	.row[data-tone='soft'] {
		--edge: var(--text-faint);
	}

	.dot {
		width: 8px;
		height: 8px;
		flex: none;
		border-radius: 50%;
		background: var(--edge);
	}

	.fields {
		display: flex;
		align-items: center;
		gap: 8px;
		flex: 1;
		min-width: 0;
	}

	.kind {
		width: 12ch;
		flex: none;
		font-size: 13px;
		color: var(--edge);
	}

	input {
		padding: 5px 8px;
		background: var(--surface);
		border: 1px solid transparent;
		border-radius: var(--radius);
		font-size: 13px;
	}

	input:hover,
	input:focus {
		border-color: var(--line);
	}

	.description {
		flex: 1;
		min-width: 0;
	}

	.tone select {
		background: none;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		padding: 4px 6px;
		font-size: 12.5px;
		color: var(--text-muted);
	}

	.drop {
		color: var(--text-faint);
		font-size: 12px;
		padding: 4px;
	}

	.drop:not(:disabled):hover {
		color: var(--danger);
	}

	.drop:disabled {
		opacity: 0.3;
		cursor: default;
	}

	.save {
		padding: 5px 12px;
		border-radius: var(--radius);
		background: var(--pomegranate);
		color: var(--ground);
		font-size: 12.5px;
	}

	.foot {
		display: flex;
		gap: 8px;
		margin-top: 14px;
	}

	.action {
		padding: 6px 12px;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 13px;
		color: var(--text-muted);
	}

	.action:hover {
		border-color: var(--brass);
		color: var(--brass);
	}

	.problem {
		color: var(--danger);
	}

	.empty {
		margin: 18px 0;
		font-family: var(--font-body);
		font-size: 15px;
		color: var(--text-muted);
	}
</style>
