<script lang="ts">
	/**
	 * One conversation: the messages, the turn arriving, the composer.
	 *
	 * Everything on screen comes from the event list — the live one while a turn is streaming,
	 * and the persisted one the instant it finishes. Nothing here parses text.
	 */
	import { page } from '$app/state';
	import { untrack } from 'svelte';
	import { api } from '$lib/api/client';
	import { artifactOf } from '$lib/api/events';
	import ArtifactDrawer from '$lib/components/ArtifactDrawer.svelte';
	import Backdrop from '$lib/components/Backdrop.svelte';
	import Composer from '$lib/components/Composer.svelte';
	import Message from '$lib/components/Message.svelte';
	import { t } from '$lib/i18n';
	import { artifacts } from '$lib/stores/artifacts.svelte';
	import { ChatSession } from '$lib/stores/chat.svelte';
	import { workspace } from '$lib/stores/workspace.svelte';

	const session = new ChatSession();

	let scroller = $state<HTMLElement | null>(null);
	let published = $state(0);

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
		// A drawer belongs to the conversation it was opened from, so walking to another one
		// closes it rather than leaving somebody else's page beside this transcript.
		artifacts.leave();
		// Taken before the load, so a slow first request cannot let a second effect run and
		// send it twice.
		const first = workspace.takeHandoff();
		await session.open(id);
		if (first) await session.send(first.text, first.files);
	}

	// How many artifacts this conversation has, for the control in the header. Re-read when
	// something published changes, so a page made in the turn you are watching is reachable
	// without a reload — and so an artifact made nine turns ago can be opened without scrolling
	// back to the card that made it.
	$effect(() => {
		const id = session.chat?.id;
		void artifacts.version;
		if (!id) {
			published = 0;
			return;
		}
		let current = true;
		api
			.artifacts(id)
			.then((found) => {
				if (current) published = found.length;
			})
			.catch(() => {
				/* the transcript is what matters; a count that could not be read is not an error */
			});
		return () => {
			current = false;
		};
	});

	// Anything published in the turn now streaming makes every view of an artifact look again,
	// and a page she has just finished writing opens beside the conversation. Read off the
	// events rather than passed through a callback, because the same events arrive twice — live,
	// and again as the persisted list at `done` — and both have to end up saying the same thing.
	//
	// **The `untrack` is not optional, and leaving it out is a blank page.** `noticed` bumps a
	// counter, and `counter += 1` *reads* it: without this, `artifacts.version` becomes a
	// dependency of the effect that writes it, and Svelte gives up rendering the page with
	// `effect_update_depth_exceeded` and nothing on screen to say why. That is the third time
	// this project has met that failure and the second shape of it recorded in `status.md`.
	$effect(() => {
		const arriving = session.draft;
		const id = session.chat?.id ?? null;
		untrack(() => {
			for (const event of arriving) {
				if (event.type !== 'tool_result') continue;
				const { call_id, tool } = event as { call_id: string; tool: string };
				artifacts.noticed(id, call_id, tool, artifactOf(event));
			}
		});
	});

	// Follow the answer down, but only while the person is already at the bottom. Yanking the
	// view back while they are reading something further up is the rudest thing a streaming
	// interface can do.
	$effect(() => {
		void session.draft;
		void session.messages;
		if (pinned && scroller) scroller.scrollTop = scroller.scrollHeight;
	});

	/** Keep following when the transcript grows *after* the events did.
	 *
	 * An inline artifact is fetched by name, so a chart arrives a moment after the event that
	 * announced it and is suddenly 300 px tall — by which time the effect above has already run,
	 * and the sentence underneath it has been pushed out of sight. Watching the size of the
	 * content covers that, and every later thing with the same shape.
	 *
	 * Plain DOM rather than reactive state on purpose: this callback assigns `scrollTop` and
	 * reads nothing Svelte is tracking, so it cannot be the update loop that has cost this
	 * project an afternoon twice. */
	function follows(node: HTMLElement) {
		const watcher = new ResizeObserver(() => {
			if (pinned && scroller) scroller.scrollTop = scroller.scrollHeight;
		});
		watcher.observe(node);
		return { destroy: () => watcher.disconnect() };
	}

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

	function reply(callId: string, text: string) {
		void session.reply(callId, text);
	}
</script>

<header class="top">
	<h1 class="title">{session.chat?.title || t.empty.title}</h1>
	{#if published && session.chat}
		<button
			class="published"
			type="button"
			onclick={() =>
				artifacts.open ? artifacts.close() : artifacts.show(session.chat!.id, artifacts.name)}
		>
			{t.artifact.count(published)}
		</button>
	{/if}
</header>

<!-- The conversation and the drawer are side by side rather than stacked, which is the whole
     point of a drawer: you keep working with it open — reading the page, asking for a change,
     watching it change. A modal would cover the thing you are talking about. -->
<div class="split">
	<div class="conversation">
		<Backdrop />

		<div class="scroll" bind:this={scroller} {onscroll}>
			<div class="column" use:follows>
				{#if session.error}
					<p class="error">{session.error}</p>
				{/if}

				{#each session.messages as message (message.id)}
					<Message
						role={message.role}
						content={message.content}
						attachments={message.attachments}
						events={message.events}
						chatId={session.chat?.id ?? null}
						busy={session.busy}
						onanswer={answer}
						onreply={reply}
						onredo={(text) => session.redo(message.id, text)}
					/>
				{/each}

				{#if session.pending !== null}
					<Message role="user" content={session.pending} attachments={session.pendingFiles} />
				{/if}

				{#if session.draft.length || session.streaming}
					<Message
						role="assistant"
						events={session.draft}
						chatId={session.chat?.id ?? null}
						streaming={session.streaming}
						busy={session.busy}
						onanswer={answer}
						onreply={reply}
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
					blocked={session.blocked}
					profiles={workspace.profiles}
					profileId={session.chat?.profile_id ?? null}
					providers={workspace.providers}
					activeProvider={workspace.activeProvider}
					servers={workspace.servers}
					chatSkills={session.chat?.pinned_skills ?? []}
					onsend={(text, files) => session.send(text, files)}
					onstop={() => session.stop()}
					onmodel={(name) => workspace.useProvider(name)}
					onsettings={() => workspace.openSettings()}
					onskills={(names) => session.pinSkills(names)}
				/>
			</div>
		</div>
	</div>

	{#if artifacts.open && session.chat}
		<ArtifactDrawer chatId={session.chat.id} />
	{/if}
</div>

<style>
	.top {
		display: flex;
		align-items: center;
		gap: 12px;
		flex: none;
		padding: 14px 24px;
		border-bottom: 1px solid var(--line);
	}

	/* Room for the fixed menu button `+layout.svelte` draws over the top-left corner below the
	   phone breakpoint — without it the title runs under the button instead of stopping short
	   of it. The bar grows to match rather than the button being squeezed into whatever height
	   the title alone needed: that button is 40px square at `top: 12px`, so 64px is what centres
	   it — `align-items: center` above then puts the title on the same line, instead of the two
	   merely overlapping. */
	@media (max-width: 780px) {
		.top {
			min-height: 64px;
			padding-left: 64px;
		}
	}

	/* The way back to something published nine turns ago. Without it, the only door to an
	   artifact is the card in the turn that made it, and an edit later on leaves you scrolling
	   for the thing you just changed. */
	.published {
		margin-left: auto;
		flex: none;
		padding: 3px 9px;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 12.5px;
		color: var(--text-muted);
		transition:
			color var(--fade) var(--ease),
			border-color var(--fade) var(--ease);
	}

	.published:hover {
		color: var(--text);
		border-color: var(--brass);
	}

	/* The conversation keeps its own column and its own scrolling; the drawer takes width from
	   beside it rather than from over it. `min-width: 0` on the conversation is what stops a
	   long line in the transcript refusing to give the drawer its room. */
	.split {
		display: flex;
		flex: 1;
		min-height: 0;
	}

	.conversation {
		position: relative;
		isolation: isolate;
		display: flex;
		flex-direction: column;
		flex: 1;
		min-width: 0;
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

	/* The reading column is the measure itself, so her prose fills it instead of stopping short
	   of the edge every other thing in the conversation reaches. */
	.column {
		width: min(var(--column), 100%);
		margin: 0 auto;
	}

	.foot {
		flex: none;
		padding: 12px 24px max(20px, env(safe-area-inset-bottom));
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
