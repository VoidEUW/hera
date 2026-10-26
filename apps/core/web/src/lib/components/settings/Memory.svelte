<script lang="ts">
	/**
	 * What she knows about you, and what carrying it costs (ADR 16).
	 *
	 * **This screen is the only place any of it is visible.** Every enabled memory is already in
	 * her prompt, so nothing here helps *her* — it exists because a store you cannot see is a
	 * store you cannot trust, and because the description and the `why` are never injected, which
	 * makes this list the only reason either is worth writing down.
	 *
	 * The **bar** is the feature the rest hangs off. Injecting everything means the space memory
	 * takes is bounded by nothing except what she has learned, so the ceiling has to be something
	 * a person steers by rather than something they hit: a bar answers *how close am I* before it
	 * is read, where a number in a corner has to be looked up and compared.
	 *
	 * **Switching one off keeps it and gives the space back** — the middle option between having
	 * something and deleting it, and the reason the bar is worth having at all. Deleting is here
	 * and nowhere else: her own `forget` switches a memory off and keeps the file, so the button
	 * on this row is the only thing in the system that unlinks one.
	 *
	 * **Editing is behind a Save**, unlike Settings → Emotions where a field blurs and writes.
	 * There the values are a word and a line; here the body is a paragraph, and a blur that
	 * commits is a blur that can commit half a sentence you were still thinking about. The key is
	 * not editable at all — the filename is the identity, so renaming would be a different memory
	 * with the same words in it.
	 */
	import Button from '$lib/components/ui/Button.svelte';
	import Icon from '$lib/components/ui/Icon.svelte';
	import { API, api, type MemoryBudget, type MemoryItem } from '$lib/api/client';
	import Checkbox from '$lib/components/ui/Checkbox.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';
	import ProgressBar from '$lib/components/ui/ProgressBar.svelte';
	import Textarea from '$lib/components/ui/Textarea.svelte';
	import { t } from '$lib/i18n';
	import { Placeholder } from '$lib/loading.svelte';
	import LoadFailed from './LoadFailed.svelte';
	import Rows from './Rows.svelte';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	let memories = $state<MemoryItem[]>([]);
	let budget = $state<MemoryBudget | null>(null);
	let error = $state('');
	/** Why the screen could not load, if it could not — kept as thrown, for `LoadFailed`. A
	 * failed save is `error` instead, said beside the screen that is still there. */
	let failed = $state<unknown>(null);
	let confirming = $state('');

	/** Which memory is open for editing, and the draft of it. One at a time, and separate from
	 * `confirming` for the reason the rail's menu/rename/confirm triple is three fields: only one
	 * can be true, and one mode field would let an edit survive a delete confirmation opening. */
	let editing = $state('');
	let draft = $state({ text: '', description: '', why: '' });
	/** The summary and the reason, which never reach her prompt, are shut until asked for. */
	let more = $state(false);

	const shown = $derived(
		memories.filter(
			(memory) =>
				!filter ||
				`${memory.key} ${memory.description} ${memory.text}`.toLowerCase().includes(filter)
		)
	);

	/** Nought to one. Clamped, because the ceiling is a setting and a store that was over it
	 * before the number was lowered should draw a full bar rather than one running off the end. */
	const filled = $derived(budget && budget.limit > 0 ? Math.min(1, budget.used / budget.limit) : 0);

	/** The same placeholder and the same beat as every other settings screen (`Rows`).
	 *
	 * Set where the load begins and ends rather than through an `$effect` over a flag: both
	 * halves of a fast local fetch can happen before effects next flush, and an effect that
	 * only ever sees the `false` draws nothing. It is never set back to `true` — a refresh
	 * after a change made here has a list on screen already, and replacing that with grey
	 * would say the screen is arriving when it is only catching up. */
	const settling = new Placeholder(true);
	$effect(() => () => settling.stop());
	const waiting = $derived(settling.shown);

	$effect(() => {
		void load();
	});

	async function load() {
		try {
			[memories, budget] = await Promise.all([api.memories(), api.memoryBudget()]);
			error = '';
			failed = null;
		} catch (cause) {
			failed = cause;
		} finally {
			settling.set(false);
		}
	}

	async function toggle(memory: MemoryItem) {
		// Optimistic, and rolled back on the one failure that matters: switching a memory *on*
		// is a write like any other and can be refused for want of room. The refusal names what
		// is taking the space, so it is shown rather than swallowed.
		const previous = memories;
		memories = memories.map((entry) =>
			entry.key === memory.key ? { ...entry, enabled: !entry.enabled } : entry
		);
		try {
			await api.updateMemory(memory.key, { enabled: !memory.enabled });
			budget = await api.memoryBudget();
			error = '';
		} catch (cause) {
			memories = previous;
			error = say(cause);
		}
	}

	function edit(memory: MemoryItem) {
		confirming = '';
		editing = memory.key;
		more = false;
		draft = { text: memory.text, description: memory.description, why: memory.why };
	}

	async function save(key: string) {
		try {
			const saved = await api.updateMemory(key, { ...draft });
			memories = memories.map((entry) => (entry.key === key ? saved : entry));
			// Re-read rather than adjusted here: what one memory costs and what the bar totals
			// are one piece of arithmetic on the server, and doing it a second time in the
			// browser is how a row and the bar above it come to disagree.
			budget = await api.memoryBudget();
			editing = '';
			error = '';
		} catch (cause) {
			// The draft is deliberately kept. The failure that matters is *no room*, and throwing
			// away what somebody just typed is the wrong answer to "make it shorter".
			error = say(cause);
		}
	}

	async function remove(key: string) {
		confirming = '';
		editing = '';
		try {
			await api.deleteMemory(key);
			await load();
		} catch (cause) {
			error = say(cause);
		}
	}

	function say(cause: unknown): string {
		return cause instanceof Error ? cause.message : String(cause);
	}
</script>

{#if waiting}
	<Rows label={t.settings.loadingMemory} />
{:else if failed !== null}
	<LoadFailed cause={failed} what={t.loadFailed.what.memory} onretry={load} />
{:else}
	<section class="memory">
		<!-- The same mark the gutter draws beside `remember`, so the row in a conversation and the
		     page listing what she keeps are visibly one subject. -->
		<p class="blurb">
			<span class="mark"><Icon name="brain" /></span>
			{t.memory.blurb}
		</p>

		{#if budget}
			<!-- Not a number in a corner. The one thing a person needs to know is how close they are,
			     and a bar answers that before it is read. -->
			<div class="gauge">
				<ProgressBar
					meter
					thick
					value={budget.used}
					max={budget.limit}
					tone={filled > 0.85 ? 'danger' : 'live'}
					label={t.memory.spaceLabel}
					valuetext={t.memory.used(budget.used, budget.limit)}
				/>
				<p class="reading">
					<strong>{t.memory.left(budget.limit - budget.used)}</strong>
					<span class="of">{t.memory.used(budget.used, budget.limit)}</span>
					<span class="counts">
						{t.memory.carried(budget.count)}{#if budget.disabled}
							· {t.memory.off(budget.disabled)}{/if}
					</span>
				</p>
			</div>
		{/if}

		{#if error}
			<p class="failed">{error}</p>
		{/if}

		<div class="head">
			<!-- A plain link at the export route. The browser knows how to save a file, and the
			     response says `attachment` — the document is partly text a model wrote, and Hera's
			     own origin is not where that gets rendered. -->
			<Button
				size="sm"
				icon="download"
				href={`${API}/memories/export/MEMORY.md`}
				download="MEMORY.md"
				external>{t.memory.export}</Button
			>
		</div>

		{#if !memories.length}
			<p class="empty">{t.memory.none}</p>
		{:else if !shown.length}
			<p class="empty">{t.settings.noMatch}</p>
		{:else}
			<ul class="list">
				{#each shown as memory (memory.key)}
					<li class="item" class:off={!memory.enabled}>
						<div class="top">
							<span class="key">{memory.key}</span>
							{#if memory.scope === 'chat'}<Pill tone="live">{t.memory.hereOnly}</Pill>{/if}
							<Pill>{memory.source === 'auto' ? t.memory.hers : t.memory.yours}</Pill>
							<span class="cost">{t.memory.tokens(memory.tokens)}</span>
							<!-- Left of the switch, in a slot as wide as the longer word: the switch is what a
							     person aims at, and it must not move when the word changes. -->
							<span class="state" aria-hidden="true">
								{memory.enabled ? t.memory.on : t.memory.offOne}
							</span>
							<Checkbox
								variant="switch"
								checked={memory.enabled}
								ariaLabel={t.memory.useIt(memory.key)}
								onchange={() => toggle(memory)}
							/>
						</div>

						{#if editing === memory.key}
							<div class="editor">
								<Textarea
									label={t.memory.text}
									rows={4}
									value={draft.text}
									onchange={(value) => (draft.text = value)}
								/>
								<p class="note">{t.memory.editNote}</p>
								<span class="more">
									<Button
										variant="ghost"
										size="sm"
										icon={more ? 'chevD' : 'chevR'}
										aria-expanded={more}
										onclick={() => (more = !more)}
									>
										{t.memory.more}
									</Button>
								</span>
								{#if more}
									<Input
										label={t.memory.description}
										value={draft.description}
										onchange={(value) => (draft.description = value)}
									/>
									<Input
										label={t.memory.why}
										value={draft.why}
										placeholder={t.memory.whyHint}
										onchange={(value) => (draft.why = value)}
									/>
								{/if}
							</div>
						{:else}
							{#if memory.description}<p class="description">{memory.description}</p>{/if}
							<p class="text">{memory.text}</p>
						{/if}

						<div class="foot">
							{#if memory.created}<span class="when">{memory.created}</span>{/if}
							{#if memory.why && editing !== memory.key}
								<span class="why">{t.memory.because(memory.why)}</span>
							{/if}
							{#if editing === memory.key}
								<span class="confirm">
									<Button variant="ghost" size="sm" onclick={() => (editing = '')}>
										{t.memory.cancel}
									</Button>
									<Button variant="highlighted" size="sm" onclick={() => save(memory.key)}>
										{t.memory.save}
									</Button>
								</span>
							{:else if confirming === memory.key}
								<span class="confirm">
									{t.memory.deleteAsk}
									<Button variant="ghost" size="sm" onclick={() => (confirming = '')}>
										{t.memory.cancel}
									</Button>
									<Button
										variant="danger"
										size="sm"
										icon="trash"
										onclick={() => remove(memory.key)}
									>
										{t.memory.delete}
									</Button>
								</span>
							{:else}
								<span class="confirm">
									<Button variant="ghost" size="sm" icon="edit" onclick={() => edit(memory)}>
										{t.memory.edit}
									</Button>
									<Button
										variant="danger-soft"
										size="sm"
										icon="trash"
										onclick={() => (confirming = memory.key)}
									>
										{t.memory.delete}
									</Button>
								</span>
							{/if}
						</div>

						{#each memory.problems as problem (problem)}
							<p class="problem">{problem}</p>
						{/each}
					</li>
				{/each}
			</ul>
		{/if}
	</section>
{/if}

<style>
	.memory {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.blurb {
		display: flex;
		align-items: baseline;
		gap: 8px;
		margin: 0;
		max-width: var(--measure);
		color: var(--text-muted);
		font-size: 13.5px;
	}

	.mark {
		flex: none;
		/* Baseline-aligned by hand: a `<svg>` is a replaced element and sits on the baseline as a
		   block, which reads a whisker low beside a line of prose. */
		position: relative;
		top: 2px;
	}

	.gauge {
		display: flex;
		flex-direction: column;
		gap: 7px;
	}

	.reading {
		display: flex;
		align-items: baseline;
		gap: 10px;
		margin: 0;
		font-size: 12.5px;
		color: var(--text-faint);
	}

	.reading strong {
		font-weight: 500;
		color: var(--text);
	}

	.counts {
		margin-left: auto;
	}

	.head {
		display: flex;
		justify-content: flex-end;
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 10px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.item {
		padding: 12px 14px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius);
		background: var(--surface);
	}

	/* Kept, listed and legible — just not paid for. A memory switched off is greyed rather than
	   hidden, because hiding it is how a person loses the ability to switch it back on. */
	.item.off {
		opacity: 0.62;
	}

	.top {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.key {
		font-family: var(--font-mono);
		font-size: 13px;
		color: var(--text);
	}

	.cost {
		margin-left: auto;
		font-size: 12px;
		color: var(--text-faint);
	}

	/* As wide as "Kept, not used", so the switch beside it stays where it is. */
	.state {
		min-width: 14ch;
		font-size: 13px;
		color: var(--text-faint);
		text-align: right;
	}

	.more {
		align-self: flex-start;
	}

	.description {
		margin: 6px 0 0;
		font-size: 13px;
		color: var(--text);
	}

	.text {
		margin: 4px 0 0;
		max-width: var(--measure);
		font-size: 13px;
		color: var(--text-muted);
		white-space: pre-wrap;
	}

	.editor {
		display: flex;
		flex-direction: column;
		gap: 8px;
		margin-top: 8px;
	}

	.note {
		margin: 0;
		font-size: 11.5px;
		color: var(--text-faint);
	}

	.foot {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-top: 8px;
		font-size: 11.5px;
		color: var(--text-faint);
	}

	.why {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.confirm {
		display: flex;
		flex: none;
		align-items: center;
		gap: 6px;
		margin-left: auto;
	}

	.problem {
		margin: 6px 0 0;
		font-size: 12px;
		color: var(--danger);
	}

	.empty,
	.failed {
		margin: 0;
		max-width: var(--measure);
		font-size: 13px;
		color: var(--text-faint);
	}

	.failed {
		color: var(--danger);
	}
</style>
