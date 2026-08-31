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
	import { API, api, type MemoryBudget, type MemoryItem } from '$lib/api/client';
	import Brain from '$lib/components/Brain.svelte';
	import { t } from '$lib/i18n';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	let memories = $state<MemoryItem[]>([]);
	let budget = $state<MemoryBudget | null>(null);
	let error = $state('');
	let confirming = $state('');

	/** Which memory is open for editing, and the draft of it. One at a time, and separate from
	 * `confirming` for the reason the rail's menu/rename/confirm triple is three fields: only one
	 * can be true, and one mode field would let an edit survive a delete confirmation opening. */
	let editing = $state('');
	let draft = $state({ text: '', description: '', why: '' });

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

	$effect(() => {
		void load();
	});

	async function load() {
		try {
			[memories, budget] = await Promise.all([api.memories(), api.memoryBudget()]);
			error = '';
		} catch (cause) {
			error = say(cause);
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

<section class="memory">
	<!-- The same mark the gutter draws beside `remember`, so the row in a conversation and the
	     page listing what she keeps are visibly one subject. -->
	<p class="blurb">
		<span class="mark" aria-hidden="true"><Brain size={15} /></span>
		{t.memory.blurb}
	</p>

	{#if budget}
		<!-- Not a number in a corner. The one thing a person needs to know is how close they are,
		     and a bar answers that before it is read. -->
		<div class="gauge">
			<div
				class="track"
				role="meter"
				aria-valuenow={budget.used}
				aria-valuemin={0}
				aria-valuemax={budget.limit}
				aria-label={t.memory.spaceLabel}
			>
				<div class="fill" class:tight={filled > 0.85} style:width={`${filled * 100}%`}></div>
			</div>
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
		<a class="action" href={`${API}/memories/export/MEMORY.md`} download="MEMORY.md">
			{t.memory.export}
		</a>
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
						{#if memory.scope === 'chat'}<span class="tag">{t.memory.hereOnly}</span>{/if}
						<span class="tag quiet">
							{memory.source === 'auto' ? t.memory.hers : t.memory.yours}
						</span>
						<span class="cost">{t.memory.tokens(memory.tokens)}</span>
						<label class="switch">
							<input
								type="checkbox"
								checked={memory.enabled}
								onchange={() => toggle(memory)}
								aria-label={t.memory.useIt(memory.key)}
							/>
							<span class="word">{memory.enabled ? t.memory.on : t.memory.offOne}</span>
						</label>
					</div>

					{#if editing === memory.key}
						<div class="editor">
							<label>
								<span class="label">{t.memory.description}</span>
								<input type="text" bind:value={draft.description} />
							</label>
							<label>
								<span class="label">{t.memory.text}</span>
								<textarea bind:value={draft.text} rows="4"></textarea>
							</label>
							<label>
								<span class="label">{t.memory.why}</span>
								<input type="text" bind:value={draft.why} placeholder={t.memory.whyHint} />
							</label>
							<p class="note">{t.memory.editNote}</p>
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
								<button type="button" class="save" onclick={() => save(memory.key)}>
									{t.memory.save}
								</button>
								<button type="button" onclick={() => (editing = '')}>{t.memory.cancel}</button>
							</span>
						{:else if confirming === memory.key}
							<span class="confirm">
								{t.memory.deleteAsk}
								<button type="button" class="danger" onclick={() => remove(memory.key)}>
									{t.memory.delete}
								</button>
								<button type="button" onclick={() => (confirming = '')}>{t.memory.cancel}</button>
							</span>
						{:else}
							<span class="confirm">
								<button type="button" onclick={() => edit(memory)}>{t.memory.edit}</button>
								<button type="button" onclick={() => (confirming = memory.key)}>
									{t.memory.delete}
								</button>
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

	/* The empty part has to read as a track, or a nearly-empty bar looks like a stray mark
	   rather than like plenty of room. `--surface-raised` alone is too close to the panel it sits
	   on, so the outline is what makes the shape legible when the fill is 0.4 % wide. */
	.track {
		height: 9px;
		border: 1px solid var(--line);
		border-radius: 999px;
		background: var(--surface-raised);
		overflow: hidden;
	}

	.fill {
		height: 100%;
		background: var(--brass);
		transition: width var(--fade) var(--ease);
	}

	/* The only colour change on this screen, and it is at 85 %: the point where the next thing
	   she tries to remember is likely to be refused, which is the moment to say something. */
	.fill.tight {
		background: var(--danger);
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
	}

	.action {
		margin-left: auto;
		padding: 4px 10px;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 12.5px;
		color: var(--text-muted);
		text-decoration: none;
	}

	.action:hover {
		color: var(--text);
		border-color: var(--brass);
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
		padding: 11px 12px;
		border: 1px solid var(--line);
		border-left: 3px solid var(--brass);
		border-radius: var(--radius);
		background: var(--surface);
	}

	/* Kept, listed and legible — just not paid for. A memory switched off is greyed rather than
	   hidden, because hiding it is how a person loses the ability to switch it back on. */
	.item.off {
		border-left-color: var(--line);
		opacity: 0.62;
	}

	.top {
		display: flex;
		align-items: baseline;
		gap: 8px;
	}

	.key {
		font-family: var(--font-mono);
		font-size: 13px;
		color: var(--text);
	}

	.tag {
		padding: 1px 6px;
		border-radius: 999px;
		background: var(--surface-raised);
		font-size: 11px;
		color: var(--text-muted);
	}

	.tag.quiet {
		background: none;
		padding: 0;
		color: var(--text-faint);
	}

	.cost {
		margin-left: auto;
		font-size: 12px;
		color: var(--text-faint);
	}

	.switch {
		display: flex;
		align-items: center;
		gap: 5px;
		font-size: 12px;
		color: var(--text-muted);
		cursor: pointer;
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

	.editor label {
		display: flex;
		flex-direction: column;
		gap: 3px;
	}

	.label {
		font-size: 11.5px;
		color: var(--text-faint);
	}

	.editor input,
	.editor textarea {
		width: 100%;
		padding: 6px 8px;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		background: var(--ground);
		font-size: 13px;
		color: var(--text);
		font-family: inherit;
		resize: vertical;
	}

	.editor input:focus,
	.editor textarea:focus {
		outline: none;
		border-color: var(--brass);
	}

	.note {
		margin: 0;
		font-size: 11.5px;
		color: var(--text-faint);
	}

	.foot {
		display: flex;
		align-items: baseline;
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
		align-items: baseline;
		gap: 8px;
		margin-left: auto;
		flex: none;
	}

	.confirm button {
		font-size: 11.5px;
		color: var(--text-faint);
	}

	.confirm button:hover {
		color: var(--text);
	}

	.confirm .danger:hover {
		color: var(--danger);
	}

	.confirm .save {
		color: var(--brass);
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
