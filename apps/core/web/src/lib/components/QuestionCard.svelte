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
	import Button from './ui/Button.svelte';
	import Pill from './ui/Pill.svelte';
	import Textarea from './ui/Textarea.svelte';
	import Icon from './ui/Icon.svelte';
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
</script>

<!-- The theme's question card (`hera/question-card`, soft look with `qc.frame: none`): a brass
     capital header with its mark, her question in the body face, and the free answer under it.
     No frame — it sits in the flow of her answer, where she asked. -->
<aside class="card" class:settled>
	<p class="head">
		<Icon name="help" />
		<span>{settled ? t.question.answered : t.question.asked}</span>
		{#if label}<Pill tone={card.kind === 'blocked' ? 'authority' : 'neutral'}>{label}</Pill>{/if}
	</p>

	<p class="question">{card.question || t.question.nothing}</p>

	{#if settled}
		<p class="reply">{reply || t.question.noReply}</p>
	{:else}
		<div class="answer">
			<Textarea
				autofocus
				rows={2}
				value={draft}
				disabled={busy}
				placeholder={t.question.placeholder}
				ariaLabel={card.question || t.question.asked}
				{onkeydown}
				onchange={(value) => (draft = value)}
			/>
			<div class="actions">
				<span class="hint">{t.composer.hint}</span>
				<Button variant="highlighted" size="sm" disabled={busy} onclick={send}>
					{t.question.send}
				</Button>
			</div>
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

	.answer {
		display: flex;
		flex-direction: column;
		gap: 8px;
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
