<script lang="ts">
	/**
	 * One message: the activity gutter above, then her prose with cards in the flow of it.
	 *
	 * Renders one component per event variant and recovers nothing from text. A new kind of
	 * thing a turn can contain is one branch here, never a regular expression — that rule is
	 * the single largest source of bugs in the previous version, and it is designed out. Her
	 * prose is then *typeset* by `$lib/markdown`, which is a different thing from parsing it
	 * for meaning; ADR 11 draws the line.
	 *
	 * Under each message sit the three things you want when an answer is not the one you
	 * wanted: **copy** it, **edit** the question, **try again**. Edit and try again are the same
	 * request — the conversation goes forward from this point differently — so both go through
	 * `redo` and both delete what came after. That is why the confirmation for editing is the
	 * edit itself: you can see the answer you are about to replace while you retype the
	 * question.
	 */
	import type { AnswerRequired, AnyEvent, Artifact, PermissionRequired } from '$lib/api/events';
	import { size } from '$lib/attachments';
	import { t } from '$lib/i18n';
	import { isAnswered, reduce, replyTo } from '$lib/turn';
	import ActivityRow from './ActivityRow.svelte';
	import ArtifactCard from './ArtifactCard.svelte';
	import Ocellus from './Ocellus.svelte';
	import PermissionCard from './PermissionCard.svelte';
	import QuestionCard from './QuestionCard.svelte';
	import Prose from './Prose.svelte';

	interface Props {
		role: 'user' | 'assistant';
		content?: string;
		/** Files sent with a user message. Names, sizes and kinds, drawn as chips — the contents
		 * went to the model and are not needed to render them. A picture is a chip too: the
		 * browser threw the bytes away when the message was sent, and a thumbnail that appeared
		 * for one turn and became a chip on reload would be the interface contradicting itself. */
		attachments?: Array<{ name: string; bytes: number; media_type?: string }>;
		events?: AnyEvent[];
		/** Which conversation this message is in, so an artifact card can open the drawer on the
		 * right chat. Absent on a message rendered outside one — the card then draws without its
		 * Open rather than guessing. */
		chatId?: string | null;
		/** Whether this message is the turn currently arriving. */
		streaming?: boolean;
		busy?: boolean;
		onanswer?: (callId: string, allow: boolean, remember: boolean) => void;
		/** Reply to a question she asked. The turn resumes with the words as that call's result. */
		onreply?: (callId: string, text: string) => void;
		/** Ask again from this message. Text rewords the question; nothing repeats it. */
		onredo?: (text?: string) => void;
	}

	let {
		role,
		content = '',
		attachments = [],
		events = [],
		chatId = null,
		streaming = false,
		busy = false,
		onanswer,
		onreply,
		onredo
	}: Props = $props();

	let editing = $state(false);
	let draft = $state('');
	let copied = $state(false);

	const turn = $derived(reduce(events));
	const closed = $derived(turn.closed);
	// The one piece of choreography: the ocellus appears where her answer will begin, and when
	// the first text arrives it shrinks into the gutter as the first eye of the turn.
	const waiting = $derived(streaming && turn.inline.length === 0 && turn.activity.length === 0);

	const note = $derived.by(() => {
		if (!closed || closed.reason === 'completed') return '';
		if (closed.reason === 'failed') return closed.error || t.turn.failed;
		return t.turn[closed.reason] ?? '';
	});

	/** What the clipboard gets. `content` is the server's derived text and is what a reloaded
	 * message carries; a turn still streaming has only its events, so the prose is joined back
	 * out of them — the same runs, in the same order, without the cards between them. */
	const copyable = $derived(
		content.trim() ||
			turn.inline
				.filter((item) => item.kind === 'prose')
				.map((item) => item.text ?? '')
				.join('\n\n')
				.trim()
	);

	/** Whether this message's own controls are live. Nothing to act on while the answer is still
	 * arriving, or while another turn is. */
	const settled = $derived(!streaming && !busy);

	/** Copy is about the words, so it needs some. A button that puts an empty string on the
	 * clipboard is worse than no button. */
	const canCopy = $derived(settled && Boolean(copyable || attachments.length));

	/** **Try again** and **edit** are about the *question*, not about the answer — so they do not
	 * need one. These used to share a flag with Copy, which meant the single case where trying
	 * again matters most had no way to: a turn that failed before she said anything produced no
	 * text, so the whole row was withheld from the one message a person was staring at wanting
	 * to retry. A failed turn is exactly a turn worth asking again. */
	const canRedo = $derived(settled && Boolean(onredo));

	async function copy() {
		try {
			await navigator.clipboard.writeText(copyable);
			copied = true;
			setTimeout(() => (copied = false), 1400);
		} catch {
			/* a browser that refuses the clipboard is not something to interrupt a person over */
		}
	}

	function startEdit() {
		draft = content;
		editing = true;
	}

	function saveEdit() {
		const text = draft.trim();
		editing = false;
		if (text && text !== content) onredo?.(text);
	}

	/** The cursor lands in the field with the question selected, the way renaming works. */
	function takeover(node: HTMLTextAreaElement) {
		node.focus();
		node.select();
		node.style.height = `${Math.min(node.scrollHeight, 300)}px`;
	}

	function decision(callId: string) {
		if (!isAnswered(events, callId)) return null;
		const event = events.find(
			(candidate) =>
				candidate.type === 'permission_decided' &&
				(candidate as { call_id: string }).call_id === callId
		) as { allowed: boolean; remembered: boolean } | undefined;
		return event ?? null;
	}
</script>

{#if role === 'user'}
	<div class="mine">
		{#if editing}
			<div class="editor">
				<textarea
					bind:value={draft}
					use:takeover
					aria-label={t.message.edit}
					onkeydown={(event) => {
						if (event.key === 'Escape') editing = false;
						if (event.key === 'Enter' && !event.shiftKey) {
							event.preventDefault();
							saveEdit();
						}
					}}
				></textarea>
				<div class="editing">
					<span class="caption">{t.message.editNote}</span>
					<button class="quiet" type="button" onclick={() => (editing = false)}>
						{t.message.cancel}
					</button>
					<button class="primary" type="button" onclick={saveEdit}>{t.message.saveAndSend}</button>
				</div>
			</div>
		{:else}
			<div class="bubble">
				{#if content.trim()}<p class="said">{content}</p>{/if}
				{#if attachments.length}
					<ul class="files">
						{#each attachments as file (file.name)}
							<li>
								<span class="mono">{file.name}</span>
								{#if file.media_type?.startsWith('image/')}
									<span class="bytes">{t.attach.image}</span>
								{/if}
								<span class="bytes">{size(file.bytes)}</span>
							</li>
						{/each}
					</ul>
				{/if}
			</div>

			{#if canCopy || canRedo}
				<div class="actions right">
					{#if canCopy}
						<button type="button" onclick={copy}>
							{copied ? t.message.copied : t.message.copy}
						</button>
					{/if}
					{#if canRedo}
						<button type="button" onclick={startEdit}>{t.message.edit}</button>
					{/if}
				</div>
			{/if}
		{/if}
	</div>
{:else}
	<article class="hers">
		<!-- One list, in the order things happened. It used to be every gutter row and then all
		     the prose, which reads correctly only for a turn that does its thinking up front: the
		     moment she speaks, thinks again and speaks again, the second thought was drawn above
		     the sentence that prompted it. A run of consecutive rows is still one bordered block,
		     so the gutter reads as a group where it is one. -->
		{#each turn.blocks as item (item.key)}
			{#if item.kind === 'gutter'}
				<div class="gutter">
					{#each item.rows as row (row.key)}
						<ActivityRow {row} {streaming} />
					{/each}
				</div>
			{:else if item.kind === 'prose'}
				<Prose text={item.text ?? ''} />
			{:else if item.kind === 'artifact'}
				<!-- What she published, drawn where she published it. `inline` decides whether that
				     is the thing itself or a card to go and open it (ADR 13) — the model chose when
				     it made the file, because it is the only thing that knew which it meant. -->
				<ArtifactCard {chatId} artifact={item.artifact as Artifact} />
			{:else if item.kind === 'permission'}
				{@const card = item.event as PermissionRequired}
				<PermissionCard
					{card}
					decided={decision(card.call_id)}
					{busy}
					onanswer={(allow, remember) => onanswer?.(card.call_id, allow, remember)}
				/>
			{:else if item.kind === 'question'}
				{@const card = item.event as AnswerRequired}
				<QuestionCard
					{card}
					reply={isAnswered(events, card.call_id) ? replyTo(events, card.call_id) : null}
					{busy}
					onreply={(text) => onreply?.(card.call_id, text)}
				/>
			{/if}
		{/each}

		{#if waiting}
			<p class="waiting"><Ocellus size={16} alive /> <span class="sr-only">Thinking</span></p>
		{/if}

		{#if note}
			<p class="note" class:bad={closed?.reason === 'failed'}>{note}</p>
		{/if}

		{#if canCopy || canRedo}
			<div class="actions">
				{#if canCopy}
					<button type="button" onclick={copy}>{copied ? t.message.copied : t.message.copy}</button>
				{/if}
				{#if canRedo}
					<button type="button" onclick={() => onredo?.()}>{t.message.retry}</button>
				{/if}
			</div>
		{/if}
	</article>
{/if}

<style>
	.mine {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		margin: 22px 0;
	}

	/* Quiet until you go looking for them: a row of actions under every message would compete
	   with the conversation, and one that only appears under a pointer cannot be reached from
	   a keyboard. Hover, focus, or the moment something was copied. */
	.actions {
		display: flex;
		gap: 4px;
		margin-top: 4px;
		opacity: 0;
		transition: opacity var(--fade) var(--ease);
	}

	.mine:hover .actions,
	.mine:focus-within .actions,
	.hers:hover .actions,
	.hers:focus-within .actions {
		opacity: 1;
	}

	.actions button {
		padding: 3px 7px;
		border-radius: 6px;
		font-size: 12px;
		color: var(--text-faint);
		transition:
			background var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	.actions button:hover {
		background: var(--surface);
		color: var(--text);
	}

	.editor {
		width: min(46ch, 100%);
	}

	.editor textarea {
		width: 100%;
		padding: 10px 14px;
		background: var(--surface);
		border: 1px solid var(--brass);
		border-radius: var(--radius-lg);
		font-family: var(--font-body);
		font-size: 16px;
		line-height: 1.55;
		resize: none;
	}

	.editor textarea:focus {
		outline: none;
	}

	.editing {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-top: 6px;
	}

	.editing .caption {
		margin-right: auto;
		color: var(--text-faint);
	}

	.editing button {
		padding: 4px 10px;
		border-radius: var(--radius);
		font-size: 12.5px;
	}

	.quiet {
		color: var(--text-muted);
		border: 1px solid var(--line);
	}

	.primary {
		background: var(--pomegranate);
		color: var(--ground);
	}

	.said {
		margin: 0;
		white-space: pre-wrap;
	}

	.files {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		list-style: none;
		margin: 8px 0 0;
		padding: 0;
	}

	.files:first-child {
		margin-top: 0;
	}

	.files li {
		display: flex;
		align-items: baseline;
		gap: 8px;
		padding: 3px 10px;
		background: var(--ground);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 12.5px;
	}

	.bytes {
		color: var(--text-faint);
	}

	.bubble {
		max-width: 46ch;
		padding: 10px 14px;
		background: var(--surface-raised);
		border-radius: var(--radius-lg);
		border-bottom-right-radius: 4px;
		font-family: var(--font-body);
		font-size: 16px;
		line-height: 1.55;
		overflow-wrap: anywhere;
	}

	.hers {
		margin: 22px 0 30px;
	}

	/* Space on both sides now: a gutter block can sit between two things she said, where it
	   used to only ever sit above all of them. */
	.gutter {
		margin: 12px 0;
	}

	.gutter:first-child {
		margin-top: 0;
	}

	.waiting {
		margin: 0;
	}

	.note {
		margin: 12px 0 0;
		font-size: 12.5px;
		color: var(--text-muted);
	}

	.note.bad {
		color: var(--danger);
	}
</style>
