<script lang="ts">
	/**
	 * She asked something, and the turn is waiting on the answer.
	 *
	 * The second thing that can stop a turn, and deliberately the *same* mechanism as the first —
	 * `docs/tooling.md` § 4 argued for generalising the permission path rather than building a
	 * second suspension beside it. So this is `PermissionCard` with a field instead of buttons:
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
	 */
	import type { AnswerRequired } from '$lib/api/events';
	import { isAskKind } from '$lib/api/events';
	import { t } from '$lib/i18n';

	interface Props {
		card: AnswerRequired;
		/** What they typed, once they have. Read from the persisted `answer_given` rather than
		 * inferred from whether a result turned up afterwards. */
		reply?: string | null;
		busy?: boolean;
		onreply?: (text: string) => void;
	}

	let { card, reply = null, busy = false, onreply }: Props = $props();

	let draft = $state('');
	const settled = $derived(reply !== null);

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

	function send() {
		if (busy || settled) return;
		onreply?.(draft);
		draft = '';
	}

	function onkeydown(event: KeyboardEvent) {
		// Enter sends, Shift+Enter breaks the line — the composer's contract, because this is a
		// field you type a sentence into and having two different rules for that would be a
		// small cruelty.
		if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
		event.preventDefault();
		send();
	}

	/** The turn stopped for this, so the cursor belongs in it. */
	function takeover(node: HTMLTextAreaElement) {
		node.focus();
	}
</script>

<aside class="card" class:settled>
	<p class="head">
		<span class="mark" aria-hidden="true">?</span>
		{#if label}
			<span class="kind" data-kind={card.kind}>{label}</span>
		{/if}
		<span class="caption">{t.question.asked}</span>
	</p>

	<p class="question">{card.question || t.question.nothing}</p>

	{#if settled}
		<p class="reply">{reply || t.question.noReply}</p>
	{:else}
		<div class="answer">
			<textarea
				bind:value={draft}
				use:takeover
				{onkeydown}
				rows="2"
				disabled={busy}
				placeholder={t.question.placeholder}
				aria-label={card.question || t.question.asked}></textarea>
			<div class="actions">
				<span class="caption hint">{t.composer.hint}</span>
				<button type="button" disabled={busy} onclick={send}>{t.question.send}</button>
			</div>
		</div>
	{/if}
</aside>

<style>
	.card {
		margin: 16px 0;
		padding: 14px 16px;
		max-width: var(--measure);
		background: var(--surface-raised);
		border: 1px solid var(--line);
		border-left: 3px solid var(--laurel);
		border-radius: var(--radius);
	}

	.settled {
		background: var(--surface);
		opacity: 0.85;
	}

	.head {
		display: flex;
		align-items: baseline;
		gap: 8px;
		margin: 0 0 6px;
	}

	.mark {
		color: var(--laurel);
		font-family: var(--font-display);
	}

	/* What sort of question it is. Nothing here may be the danger colour: no question she can
	   ask is an error, and being asked one is not a thing going wrong.

	   Only `blocked` is set apart, and only as far as brass. It is the one of the three where
	   the turn is genuinely stopped on the reply — *unsure* and *choice* are her asking, which
	   is the card's own laurel and needs no second colour to say it twice. */
	.kind {
		font-size: 12.5px;
		letter-spacing: 0.03em;
		color: var(--text-muted);
	}

	.kind[data-kind='blocked'] {
		color: var(--brass);
	}

	.caption {
		margin: 0;
		color: var(--text-faint);
	}

	/* Her prose face at reading size. This is something she said, not a label on a control. */
	.question {
		margin: 0;
		font-family: var(--font-body);
		font-size: 17px;
		line-height: 1.5;
		color: var(--text);
	}

	.answer {
		margin-top: 12px;
	}

	textarea {
		width: 100%;
		padding: 8px 10px;
		background: var(--ground);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		color: var(--text);
		font: inherit;
		font-size: 15px;
		resize: vertical;
	}

	textarea:focus {
		outline: none;
		border-color: var(--laurel);
	}

	.actions {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 10px;
		margin-top: 8px;
	}

	.hint {
		margin: 0;
		font-size: 11.5px;
	}

	.actions button {
		padding: 6px 12px;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		background: var(--surface);
		font-size: 13px;
		transition:
			border-color var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	.actions button:not(:disabled):hover {
		border-color: var(--laurel);
		color: var(--laurel);
	}

	.actions button:disabled {
		opacity: 0.5;
		cursor: default;
	}

	/* What they answered, once they have. Indented under the question the way a reply is. */
	.reply {
		margin: 10px 0 0;
		padding-left: 12px;
		border-left: 2px solid var(--line);
		font-family: var(--font-body);
		font-size: 15px;
		color: var(--text-muted);
	}
</style>
