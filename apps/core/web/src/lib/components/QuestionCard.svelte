<script lang="ts">
	/**
	 * She asked something, and the turn is waiting on the answer.
	 *
	 * The second thing that can stop a turn, and deliberately the *same* mechanism as the first:
	 * the permission path, generalised, rather than a second suspension beside it. So this is `PermissionCard` with a field instead of buttons:
	 * same inline placement, same settled state read from a persisted event, same block on the
	 * composer while it is open.
	 *
	 * What is different is who is being served. A permission card asks *may I?* and the answer is
	 * a word; this asks something she actually wants to know, and the answer is a sentence. So the
	 * question is set in her prose face at reading size rather than as machinery, and there is no
	 * qualified tool name on it: `hera__ask` is not what a person is looking at, it is how the
	 * question got here.
	 *
	 * **Laurel, not brass.** Brass is authority — the colour of *this needs a decision*. A
	 * question is her turning towards you, and drawing it in the permission colour would make
	 * being asked feel like being stopped.
	 *
	 * **One card per call, however many questions are in it** (ADR 26). They are one call and so
	 * have one result; a card each would be three things to settle for one answer. One field per
	 * question, one Reply for all of them. A question with `options` offers them as chips above
	 * its field — picking one is the answer, typing replaces the pick — because the choices are a
	 * shortcut she offered, not a fence around what a person may say.
	 */
	import Button from './ui/Button.svelte';
	import Chip from './ui/Chip.svelte';
	import Pill from './ui/Pill.svelte';
	import Textarea from './ui/Textarea.svelte';
	import Icon from './ui/Icon.svelte';
	import type { AnswerRequired } from '$lib/api/events';
	import { isAskKind } from '$lib/api/events';
	import { t } from '$lib/i18n';

	interface Props {
		card: AnswerRequired;
		/** What they answered, one per question, once they have. Read from the persisted
		 * `answer_given` rather than inferred from whether a result turned up afterwards. */
		replies?: string[] | null;
		busy?: boolean;
		onreply?: (answers: string[]) => void;
	}

	let { card, replies = null, busy = false, onreply }: Props = $props();

	// By position, because a question has no identity but its place in the call. A pick and a
	// draft never both hold for one question: whichever the person touched last is the answer.
	let drafts = $state<Record<number, string>>({});
	let picked = $state<Record<number, number>>({});
	const settled = $derived(replies !== null);

	// What sort of question it is, said in the person's words rather than the tool's (ADR 17).
	//
	// A small table here is the right shape *because* the set is closed: three kinds, fixed in
	// `hera__ask`'s schema, so there is nothing for a list on a settings screen to disagree with.
	// This used to look `card.kind` up in the stance vocabulary, which meant a question could be
	// labelled with whatever mood she happened to reach for — and a kind the person had edited
	// out of that list drew with no tone at all.
	//
	// A kind this build does not recognise renders as nothing rather than as the raw word: the
	// only way to get one is a turn persisted before the set was closed, carrying a stance, and
	// *doubt* on a question card in 2026 is a puzzle rather than information.
	const label = $derived(isAskKind(card.kind) ? t.question.kinds[card.kind] : '');

	function answerTo(index: number): string {
		const choice = picked[index];
		if (choice !== undefined) return card.questions[index].options[choice] ?? '';
		return drafts[index] ?? '';
	}

	function pick(index: number, choice: number) {
		if (busy || settled) return;
		// Pressing the picked chip again lets go of it, the way any toggle does.
		if (picked[index] === choice) {
			delete picked[index];
			return;
		}
		picked[index] = choice;
		drafts[index] = '';
	}

	function write(index: number, value: string) {
		drafts[index] = value;
		if (value) delete picked[index];
	}

	function send() {
		if (busy || settled) return;
		onreply?.(card.questions.map((_, index) => answerTo(index)));
		drafts = {};
		picked = {};
	}

	function onkeydown(event: KeyboardEvent) {
		// Enter sends, Shift+Enter breaks the line — the composer's contract, because this is a
		// field you type a sentence into and having two different rules for that would be a
		// small cruelty.
		if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
		event.preventDefault();
		send();
	}
</script>

<!-- The theme's question card (`hera/question-card`, soft look with `qc.frame: none`): a brass
     capital header with its mark, then each question in the body face with its choices and the
     free answer under it.
     No frame — it sits in the flow of her answer, where she asked. -->
<aside class="card" class:settled>
	<p class="head">
		<Icon name="help" />
		<span>{settled ? t.question.answered : t.question.asked}</span>
		{#if label}<Pill tone={card.kind === 'blocked' ? 'authority' : 'neutral'}>{label}</Pill>{/if}
	</p>

	{#each card.questions as question, index (index)}
		<div class="item">
			<p class="question">{question.text || t.question.nothing}</p>

			{#if settled}
				<p class="reply">{replies?.[index] || t.question.noReply}</p>
			{:else}
				{#if question.options.length > 0}
					<div class="options" role="group" aria-label={t.question.options}>
						{#each question.options as option, choice (choice)}
							<Chip
								on={picked[index] === choice}
								pressed={picked[index] === choice}
								disabled={busy}
								onclick={() => pick(index, choice)}>{option}</Chip
							>
						{/each}
					</div>
				{/if}
				<Textarea
					autofocus={index === 0}
					rows={2}
					value={drafts[index] ?? ''}
					disabled={busy}
					placeholder={question.options.length > 0 ? t.question.ownWords : t.question.placeholder}
					ariaLabel={question.text || t.question.asked}
					{onkeydown}
					onchange={(value) => write(index, value)}
				/>
			{/if}
		</div>
	{/each}

	{#if !settled}
		<div class="actions">
			<span class="hint">{t.composer.hint}</span>
			<Button variant="highlighted" size="sm" disabled={busy} onclick={send}>
				{t.question.send}
			</Button>
		</div>
	{/if}
</aside>

<style>
	.card {
		display: flex;
		flex-direction: column;
		gap: 12px;
		max-width: var(--measure);
		margin: calc(var(--space) * 4) 0;
		animation: card-in var(--motion-card-enter);
	}

	@keyframes card-in {
		from {
			opacity: 0;
		}
	}

	.head {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0;
		color: var(--brass);
		font-size: 11px;
		font-weight: 600;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.settled .head {
		color: var(--text-faint);
	}

	.question {
		margin: 0;
		color: var(--text);
		font-family: var(--font-body);
		font-size: 16px;
		line-height: 1.5;
	}

	/* One question and its answer. The card's own gap separates them from each other. */
	.item {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.options {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
	}

	.actions {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 10px;
	}

	.hint {
		color: var(--text-faint);
		font-size: 11px;
	}

	/* What they answered, once they have, indented under the question the way a reply is. */
	.reply {
		margin: 0;
		padding-left: 12px;
		border-left: 2px solid var(--line);
		color: var(--text-muted);
		font-family: var(--font-body);
		font-size: 15px;
		animation: card-in var(--motion-card-enter);
	}
</style>
