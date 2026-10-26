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
	import AttachmentChip from './ui/AttachmentChip.svelte';
	import Button from './ui/Button.svelte';
	import IconButton from './ui/IconButton.svelte';
	import StallBox from './ui/StallBox.svelte';
	import Textarea from './ui/Textarea.svelte';
	import Thinking from './ui/Thinking.svelte';
	import TraceRow from './ui/TraceRow.svelte';
	import { toasts } from '$lib/toasts.svelte';
	import type { AnswerRequired, AnyEvent, Artifact, PermissionRequired } from '$lib/api/events';
	import { size } from '$lib/attachments';
	import { t } from '$lib/i18n';
	import { isAnswered, reduce, replyTo } from '$lib/turn';
	import { tooltip } from '$lib/tooltip';
	import { seconds, speed, speedOf } from '$lib/usage';
	import ActivityRow from './ActivityRow.svelte';
	import ArtifactCard from './ArtifactCard.svelte';
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
		/** Give up on a turn that stopped arriving and ask again — the stalled spinner's Retry. */
		onretry?: () => void;
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
		onredo,
		onretry
	}: Props = $props();

	let editing = $state(false);
	let draft = $state('');
	let copied = $state(false);
	/** Which blocks of the gutter are currently expanded. Two rules can make a block open
	 * collapsed behind one summary line: at any width, one that is *long* — more rows than
	 * scan at a glance, see `LONG_TRACE` — and under the phone breakpoint, anything past a
	 * single row. Keyed by block, not global: a turn with two runs of activity opens and
	 * closes them one at a time, the way two `ActivityRow`s already do. */
	let expandedGutter = $state<Record<string, boolean>>({});

	/** More rows than this make a block long: it opens collapsed at every width, not just on
	 * a phone. Three still scan — a thought, a call, another thought; four are a wall between
	 * the question and its answer, and the answer is the message. */
	const LONG_TRACE = 3;

	const turn = $derived(reduce(events));
	const closed = $derived(turn.closed);
	// The one piece of choreography (`hera/thinking`): while she is still without words, the eye
	// pulses where her answer will begin.
	const waiting = $derived(streaming && turn.inline.length === 0 && turn.activity.length === 0);

	/** How long is too long (`hera/spinner-stalled`). Nothing arriving for this many seconds while
	 * a turn is open turns the wait into a red, breathing spinner with Wait and Retry: a model that
	 * is loading or has died looks exactly like one that is thinking, and only time tells them
	 * apart. */
	const STALL_AFTER = 30;
	let quiet = $state(0);
	let held = $state(false);

	$effect(() => {
		// Restarted by every event that arrives — reading the length is the subscription.
		void events.length;
		quiet = 0;
		held = false;
		if (!streaming) return;
		const tick = setInterval(() => (quiet += 1), 1000);
		return () => clearInterval(tick);
	});

	const stalled = $derived(streaming && !held && quiet >= STALL_AFTER);

	const note = $derived.by(() => {
		if (!closed) {
			// A turn that recorded *nothing at all* -- no prose, no gutter, no terminator. The
			// server closes the record on every path now, so this should not happen; it is here
			// for the turns already persisted without one, and for any path that manages to miss.
			//
			// Without it the message drew as an empty bubble with a *Try again* and no reason, which
			// reads as *she had nothing to say* rather than *she never got to answer* -- and a
			// person retries that by rewording the question, which is the wrong response to a
			// provider that refused the request. The same failure mode as an empty list that has
			// not arrived, one level up (#72).
			//
			// `streaming` is excluded because a turn that has *begun* also has nothing in it yet,
			// and the ocellus beside it is already saying so. Only a turn that has stopped without
			// a terminator is the case this is for.
			const said = turn.inline.length > 0 || turn.activity.length > 0;
			return !streaming && !said ? t.turn.silent : '';
		}
		if (closed.reason === 'completed') return '';
		if (closed.reason === 'failed') return closed.error || t.turn.failed;
		return t.turn[closed.reason] ?? '';
	});

	/** What she generated for this turn — `completion_tokens`, not the total. The prompt side
	 * (history, skills, the question itself) is mostly *carried forward*, not produced by this
	 * message, and folding it in would make a one-line answer after a long conversation look
	 * like it cost as much as the essay it was asked to shorten. `null` on a turn still running,
	 * and on one closed against a provider that never reported usage. */
	const generated = $derived(closed?.usage?.completion_tokens ?? null);

	/** How fast she wrote it, as Hera measured it, and how long before anything came back. */
	const perSecond = $derived(speedOf(closed?.timing));
	const waited = $derived(closed?.timing?.first_token_ms ?? null);

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
			toasts.show(t.message.copied);
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
		<p class="speaker">{t.message.you}</p>
		{#if editing}
			<div class="editor">
				<Textarea
					prose
					autofocus
					resizable={false}
					value={draft}
					ariaLabel={t.message.edit}
					onchange={(value) => (draft = value)}
					onkeydown={(event) => {
						if (event.key === 'Escape') editing = false;
						if (event.key === 'Enter' && !event.shiftKey) {
							event.preventDefault();
							saveEdit();
						}
					}}
				/>
				<div class="editing">
					<span class="caption">{t.message.editNote}</span>
					<Button variant="ghost" size="sm" onclick={() => (editing = false)}>
						{t.message.cancel}
					</Button>
					<Button variant="highlighted" size="sm" onclick={saveEdit}>{t.message.saveAndSend}</Button
					>
				</div>
			</div>
		{:else}
			{#if attachments.length}
				<div class="files">
					{#each attachments as file (file.name)}
						<AttachmentChip
							name={file.name}
							size={size(file.bytes)}
							icon={file.media_type?.startsWith('image/') ? 'image' : 'file'}
						/>
					{/each}
				</div>
			{/if}
			{#if content.trim()}
				<div class="bubble"><p class="said">{content}</p></div>
			{/if}

			{#if canCopy || canRedo}
				<div class="actions right">
					{#if canCopy}
						<IconButton
							size="sm"
							icon={copied ? 'check' : 'copy'}
							on={copied}
							label={t.message.copy}
							onclick={copy}
						/>
					{/if}
					{#if canRedo}
						<IconButton size="sm" icon="edit" label={t.message.edit} onclick={startEdit} />
					{/if}
				</div>
			{/if}
		{/if}
	</div>
{:else}
	<article class="hers">
		<p class="speaker">{t.appName}</p>
		<!-- One list, in the order things happened. It used to be every gutter row and then all
		     the prose, which reads correctly only for a turn that does its thinking up front: the
		     moment she speaks, thinks again and speaks again, the second thought was drawn above
		     the sentence that prompted it. A run of consecutive rows is still one bordered block,
		     so the gutter reads as a group where it is one. -->
		{#each turn.blocks as item, index (item.key)}
			{#if item.kind === 'gutter'}
				<div class="gutter" class:long={item.rows.length > LONG_TRACE}>
					{#if item.rows.length > 1}
						<!-- CSS alone decides where a collapse exists to switch: a *long* block at any
						     width, anything past one row on the phone. Untouched blocks keep this hidden —
						     `.summary` is what CSS hides there, not a second branch of markup. -->
						<div class="summary">
							<TraceRow
								verb={t.activity.did}
								text={t.activity.didThings(item.rows.length)}
								toggle
								open={expandedGutter[item.key] ?? false}
								ontoggle={(next) => (expandedGutter[item.key] = next)}
							/>
						</div>
					{/if}
					<div
						class="rows"
						class:collapsed={item.rows.length > 1 && !(expandedGutter[item.key] ?? false)}
					>
						{#each item.rows as row, i (row.key)}
							<!-- Each row in its own wrapper, so a collapsed block can keep the newest one on
							     screen: `display: contents` makes the wrapper draw no box of its own, and the
							     CSS hides every one but the latest. -->
							<div class="entry" class:latest={i === item.rows.length - 1}>
								<ActivityRow {row} {streaming} />
							</div>
						{/each}
					</div>
				</div>
			{:else if item.kind === 'prose'}
				<!-- The caret (`stream.caret`) rides the end of the last thing she is still
				     writing, and nowhere else. -->
				<div class="said-hers" class:caret={streaming && index === turn.blocks.length - 1}>
					<Prose text={item.text ?? ''} />
				</div>
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

		{#if stalled}
			<StallBox
				title={t.message.thinking}
				seconds={quiet}
				stalled
				onwait={() => (held = true)}
				{onretry}
			/>
		{:else if waiting}
			<Thinking />
		{/if}

		{#if note}
			<p class="note" class:bad={closed?.reason === 'failed'}>{note}</p>
		{/if}

		{#if canCopy || canRedo || generated !== null}
			<div class="actions">
				{#if generated !== null}
					<span
						class="tokens"
						use:tooltip={waited !== null ? t.turn.firstToken(seconds(waited)) : undefined}
						>{t.turn.tokens(generated)}{perSecond !== null ? ` · ${speed(perSecond)}` : ''}</span
					>
				{/if}
				{#if canCopy}
					<IconButton
						size="sm"
						icon={copied ? 'check' : 'copy'}
						on={copied}
						label={t.message.copy}
						onclick={copy}
					/>
				{/if}
				{#if canRedo}
					<IconButton size="sm" icon="refresh" label={t.message.retry} onclick={() => onredo?.()} />
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
		/* A message arriving, which for the user's own bubble is the moment they pressed send.
		   `--fade` rather than something slower, because this is the plainest gesture the
		   interface has and the conversation is doing the rest of the work. */
		animation: fade var(--fade) var(--ease);
	}

	@keyframes fade {
		from {
			opacity: 0;
		}
	}

	/* Quiet until you go looking for them: a row of actions under every message would compete
	   with the conversation, and one that only appears under a pointer cannot be reached from
	   a keyboard. Hover, focus, or the moment something was copied. */
	/* Always shown (the theme's `msg.actions` part): a copy that has to be found under a pointer
	   is a copy a keyboard cannot reach, and three quiet icons do not compete with the prose. */
	.actions {
		display: flex;
		align-items: center;
		gap: 2px;
		margin-top: calc(var(--space) * 1);
		color: var(--text-faint);
	}

	/* Who is speaking, in mono capitals (`msg.label`): yours on the right over the bubble, hers
	   in her own colour, because her name is one of the two places pomegranate is for. */
	.speaker {
		margin: 0 0 calc(var(--space) * 1.5);
		font-family: var(--font-mono);
		font-size: 10.5px;
		font-weight: 500;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		color: var(--text-faint);
	}

	.hers > .speaker {
		color: var(--pomegranate);
	}

	/* The caret on the last line she is still writing. `:global` because the prose is rendered
	   through {@html}. */
	.caret :global(.prose > :last-child)::after {
		content: '';
		display: inline-block;
		width: 2px;
		height: 1.05em;
		margin-left: 2px;
		vertical-align: text-bottom;
		background: var(--laurel);
		animation: blink var(--motion-stream-caret) infinite;
	}

	@keyframes blink {
		50% {
			opacity: 0;
		}
	}

	.tokens {
		margin-right: auto;
		padding: 3px 7px;
		font-size: 12px;
		color: var(--text-faint);
	}

	.editor {
		width: min(460px, 100%);
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

	.said {
		margin: 0;
		white-space: pre-wrap;
	}

	.files {
		display: flex;
		flex-wrap: wrap;
		justify-content: flex-end;
		gap: 6px;
		margin-bottom: 8px;
	}

	/* Yours as a raised bubble on the right (`msg.user`), in her prose face so the two halves of
	   the conversation read as one text. */
	.bubble {
		max-width: min(78%, 460px);
		padding: 10px 14px;
		border-radius: var(--radius-lg);
		background: var(--surface-raised);
		font-family: var(--font-body);
		font-size: calc(var(--prose-size) - 1px);
		line-height: 1.5;
		overflow-wrap: anywhere;
	}

	.hers {
		margin: 22px 0 30px;
		/* The turn arriving. This is the moment the interface is actually about, and it was the
		   one thing with no gesture at all: the transcript's own `.turns` fade covers the skeleton
		   being replaced on load, which is a different event and fires once, so an answer landing
		   used to appear between two frames with nothing acknowledging it.

		   Slower than `.mine` on purpose, and it is the one place in the interface where that is
		   true. A person has just sent something and is waiting; the answer beginning is the
		   event, and a turn's arriving fade that is over before it registers is a wasted gesture. */
		animation: arrive var(--motion-message-enter);
	}

	@keyframes arrive {
		from {
			opacity: 0;
		}
	}

	/* Space on both sides now: a gutter block can sit between two things she said, where it
	   used to only ever sit above all of them. */
	.gutter {
		margin: 12px 0;
		/* A block arriving mid-answer, which happens constantly — she thinks again after speaking
		   and a second block appears between two sentences. Faded rather than disclosed: it grows
		   downwards as its rows stream in, so there is no final height to measure, and a height
		   animation against a container still being written would be chasing it. */
		animation: fade var(--fade) var(--ease);
	}

	.gutter:first-child {
		margin-top: 0;
	}

	/* A collapse comes in two widths. At every width, a *long* block — more rows than scan at a
	   glance — opens behind one line instead: it is a wall between the question and the reply,
	   and the reply is the message. On the phone anything past one row opens that way. Either
	   way a collapsed block keeps its most recent row on screen, so the summary is the latest
	   step she took rather than a count of steps you cannot see. The same "quiet, expandable"
	   idea `ActivityRow` already applies to a single row's own detail, one level up. */
	.summary {
		display: none;
	}

	.entry {
		display: contents;
	}

	.gutter.long .summary {
		display: block;
	}

	.gutter.long .rows.collapsed > .entry:not(.latest) {
		display: none;
	}

	@media (max-width: 780px) {
		.summary {
			display: block;
		}

		.rows.collapsed > .entry:not(.latest) {
			display: none;
		}
	}

	/* The turn's own outcome, and the only sentence in a message that can be bad news. It arrives
	   after the answer rather than with it — a turn that failed says so at the end, and that
	   ordering is the point — so it is a separate arrival and gets its own gesture. `.bad` is a
	   class rather than a colour so a failure reads as louder than a truncation, not as a
	   different kind of thing to look at. */
	.note {
		margin: 12px 0 0;
		font-size: 12.5px;
		color: var(--text-muted);
		animation: fade var(--fade) var(--ease);
	}

	.note.bad {
		color: var(--danger);
	}
</style>
