<script lang="ts">
	/**
	 * One conversation: the messages, the turn arriving, the composer.
	 *
	 * Everything on screen comes from the event list — the live one while a turn is streaming,
	 * and the persisted one the instant it finishes. Nothing here parses text.
	 */
	import { page } from '$app/state';
	import { untrack } from 'svelte';
	import Composer from '$lib/components/Composer.svelte';
	import Message from '$lib/components/Message.svelte';
	import { t } from '$lib/i18n';
	import { ChatSession } from '$lib/stores/chat.svelte';
	import { workspace } from '$lib/stores/workspace.svelte';

	const session = new ChatSession();

	let scroller = $state<HTMLElement | null>(null);

	// Deliberately not $state. Assigning scrollTop fires a scroll event, which sets this, which
	// would re-run the effect below, which assigns scrollTop again -- a loop Svelte terminates
	// by giving up on rendering. Nothing displays it, so plain state is all it needs to be.
	let pinned = true;

	$effect(() => {
		const id = page.params.id;
		if (!id) return;
		void open(id);
	});

	async function open(id: string) {
		// Taken before the load, so a slow first request cannot let a second effect run and
		// send it twice.
		const first = workspace.takeHandoff();
		await session.open(id);
		if (first) await session.send(first.text, first.files);
	}

	// Follow the answer down, but only while the person is already at the bottom. Yanking the
	// view back while they are reading something further up is the rudest thing a streaming
	// interface can do.
	$effect(() => {
		void session.draft;
		void session.messages;
		if (pinned && scroller) scroller.scrollTop = scroller.scrollHeight;
	});

	// Fold the chat's new title back into the rail. Keyed on the title so a re-render does not
	// keep rewriting the same list.
	$effect(() => {
		const chat = session.chat;
		if (chat) untrack(() => workspace.touch(chat));
	});

	function onscroll() {
		if (!scroller) return;
		const distance = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight;
		pinned = distance < 80;
	}

	function answer(callId: string, allow: boolean, remember: boolean) {
		void session.answer([callId], allow, remember);
	}
</script>

<header class="top">
	<h1 class="title">{session.chat?.title || t.empty.title}</h1>
</header>

<div class="scroll" bind:this={scroller} {onscroll}>
	<div class="column">
		{#if session.error}
			<p class="error">{session.error}</p>
		{/if}

		{#each session.messages as message (message.id)}
			<Message
				role={message.role}
				content={message.content}
				attachments={message.attachments}
				events={message.events}
				busy={session.busy}
				onanswer={answer}
			/>
		{/each}

		{#if session.pending !== null}
			<Message role="user" content={session.pending} attachments={session.pendingFiles} />
		{/if}

		{#if session.draft.length || session.streaming}
			<Message
				role="assistant"
				events={session.draft}
				streaming={session.streaming}
				busy={session.busy}
				onanswer={answer}
			/>
		{/if}

		{#if !session.messages.length && !session.draft.length && !session.pending}
			<p class="empty">{t.empty.chat}</p>
		{/if}
	</div>
</div>

<div class="foot">
	<div class="column">
		<Composer
			autofocus
			placeholder={t.composer.reply}
			busy={session.busy}
			profiles={workspace.profiles}
			profileId={session.chat?.profile_id ?? null}
			onsend={(text, files) => session.send(text, files)}
			onstop={() => session.stop()}
		/>
	</div>
</div>

<style>
	.top {
		flex: none;
		padding: 14px 24px;
		border-bottom: 1px solid var(--line);
	}

	.title {
		margin: 0;
		font-family: var(--font-body);
		font-size: 15px;
		font-weight: 400;
		color: var(--text-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.scroll {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		padding: 8px 24px 24px;
	}

	.column {
		width: min(760px, 100%);
		margin: 0 auto;
	}

	.foot {
		flex: none;
		padding: 12px 24px 20px;
		background: linear-gradient(to top, var(--ground) 70%, transparent);
	}

	.empty,
	.error {
		margin: 40px 0;
		font-family: var(--font-body);
		font-size: 16px;
		color: var(--text-muted);
	}

	.error {
		color: var(--danger);
	}
</style>
