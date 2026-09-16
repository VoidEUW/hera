<script lang="ts">
	/**
	 * One conversation: the messages, the turn arriving, the composer.
	 *
	 * Everything on screen comes from the event list — the live one while a turn is streaming,
	 * and the persisted one the instant it finishes. Nothing here parses text.
	 */
	import { page } from '$app/state';
	import { untrack } from 'svelte';
	import { API, api } from '$lib/api/client';
	import { artifactOf } from '$lib/api/events';
	import ArtifactDrawer from '$lib/components/ArtifactDrawer.svelte';
	import Backdrop from '$lib/components/Backdrop.svelte';
	import Composer from '$lib/components/Composer.svelte';
	import Message from '$lib/components/Message.svelte';
	import Skeleton from '$lib/components/Skeleton.svelte';
	import Tray from '$lib/components/Tray.svelte';
	import { t } from '$lib/i18n';
	import { Placeholder } from '$lib/loading.svelte';
	import { artifacts } from '$lib/stores/artifacts.svelte';
	import { ChatSession } from '$lib/stores/chat.svelte';
	import { workspace } from '$lib/stores/workspace.svelte';

	const session = new ChatSession();

	let scroller = $state<HTMLElement | null>(null);
	let published = $state(0);

	/** The shape of a conversation while it is being fetched, on the same beat as the rail's.
	 *
	 * Two turns rather than a remembered count: the transcript is pinned to its own bottom and
	 * sits between a fixed header and a fixed composer, so what it holds is the reading column,
	 * not the page's furniture. Getting the number of turns right would buy a scroll offset
	 * nobody is looking at yet. */
	const settling = new Placeholder(true);
	$effect(() => settling.set(!session.loaded));
	$effect(() => () => settling.stop());
	const waiting = $derived(settling.shown);

	// Deliberately not $state. Assigning scrollTop fires a scroll event, which sets this, which
	// would re-run the effect below, which assigns scrollTop again -- a loop Svelte terminates
	// by giving up on rendering. Nothing displays it, so plain state is all it needs to be.
	let pinned = true;

	/** Which conversation has already been opened, so the effect below does not open it twice.
	 *
	 * Not a nicety. `page.params` settles in more than one step during a navigation, so the
	 * effect can re-run with the same id — and a second `open()` calls `session.reset()`, which
	 * aborts the turn the first one started, after `takeHandoff()` has already handed the
	 * message over and cleared it. The sentence somebody typed on the start screen is gone and
	 * nothing says so ([issue #122](https://github.com/VoidEUW/hera/issues/122)). It is rare and
	 * load-dependent, which is why it surfaced as a flaky test rather than a bug report.
	 *
	 * `untrack` for the same reason `project/[id]` uses it: this both reads and writes state the
	 * effect depends on, which is the shape that ends in `effect_update_depth_exceeded`. */
	let opened = $state<string | null>(null);

	$effect(() => {
		const id = page.params.id;
		if (!id || untrack(() => opened) === id) return;
		untrack(() => (opened = id));
		void open(id);
	});

	async function open(id: string) {
		// A drawer belongs to the conversation it was opened from, so walking to another one
		// closes it rather than leaving somebody else's page beside this transcript.
		artifacts.leave();
		// Taken before the load, so a slow first request cannot let a second effect run and
		// send it twice.
		const first = workspace.takeHandoff();
		// Everything after this belongs to *this* conversation, and `send` goes to whichever
		// chat the session currently holds -- so a load that was overtaken has to stop here
		// rather than put the message a chat was started with into the one that overtook it.
		if (!(await session.open(id))) {
			// Handed back rather than dropped. `takeHandoff` clears as it reads, so a load that
			// does not finish is the one place a person's first sentence can go missing with
			// nothing on screen to say it did. Whoever overtook this one can carry it instead.
			if (first) workspace.handOff(first.text, first.files);
			return;
		}
		if (first) await session.send(first.text, first.files);
		await reopenIfPublished(id);
	}

	/** Coming back to a conversation that already published something reopens the drawer on it,
	 * the same door a fresh artifact opens for itself mid-turn -- without this, the only way
	 * back in is the header button, and the person has to already know it is worth clicking.
	 *
	 * It opens with no filename, which means *pick one*: the drawer chooses the most recently
	 * written file once its own listing lands. Choosing here instead would mean fetching the same
	 * listing twice to answer the same question.
	 *
	 * **Never over an open drawer.** A turn that publishes while this is in flight opens the
	 * drawer on the file it just made (`noticed`), and this landing afterwards would hand the
	 * choice back -- taking the page away the moment it arrived. Checked on both sides of the
	 * request, because that is the gap the turn streams through. */
	async function reopenIfPublished(id: string) {
		if (artifacts.open) return;
		try {
			const found = await api.artifacts(id);
			// `page.params.id` rather than `session.chat?.id`: a faster later switch may have
			// moved both on by the time this resolves, and neither should show for the old id.
			if (found.length && page.params.id === id && !artifacts.open) artifacts.show(id, null);
		} catch {
			/* the transcript is what matters; failing to reopen is not an error */
		}
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

<!-- What a turn looks like before it arrives: her question, then her answer. The bubble is one
     block because that is what a bubble is; the prose is lines, because that is what prose is. -->
{#snippet waitingTurn()}
	<div class="held-mine"><Skeleton rows={1} height={45} widths={[62]} /></div>
	<div class="held-hers"><Skeleton rows={4} height={16} gap={9} widths={[100, 96, 100, 58]} /></div>
{/snippet}

<header class="top">
	<h1 class="title">{session.chat?.title || t.empty.title}</h1>
	<div class="right">
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
		<!-- The first tool, and likely not the last -- a home for anything else that acts on the
		     conversation as a whole rather than on one message in it. -->
		<div class="toolbar" role="toolbar" aria-label={t.chat.toolbar}>
			{#if session.chat}
				<a
					class="tool"
					aria-label={t.chat.export}
					title={t.chat.export}
					href={`${API}/chats/${session.chat.id}/export.md`}
					download
					rel="external"
				>
					<Tray size={15} />
				</a>
			{/if}
		</div>
	</div>
</header>

<!-- The conversation and the drawer are side by side rather than stacked, which is the whole
     point of a drawer: you keep working with it open — reading the page, asking for a change,
     watching it change. A modal would cover the thing you are talking about. -->
<div class="split">
	<div class="conversation">
		<Backdrop />

		<div class="scroll" bind:this={scroller} {onscroll}>
			<div class="column" use:follows>
				{#if waiting}
					<div class="held" role="status" aria-busy="true" aria-label={t.chat.loading}>
						{@render waitingTurn()}
						{@render waitingTurn()}
					</div>
				{:else}
					<div class="turns">
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
					onmodel={(name, modelId) => workspace.useProvider(name, modelId)}
					onreasoning={(name, modelId, value) => workspace.setReasoningEffort(name, modelId, value)}
					onsettings={(section) => workspace.openSettings(section)}
					onskills={(names) => session.pinSkills(names)}
					usage={session.usage}
				/>
			</div>
		</div>
	</div>

	<!-- `!waiting` as well as `open`: a panel that takes half the width away from a transcript
	     that is still a placeholder has rearranged the screen twice before anybody has read
	     anything on it. It opens once the conversation is there, and `ArtifactDrawer` takes its
	     width over a beat rather than all at once. -->
	{#if artifacts.open && session.chat && !waiting}
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

	/* Everything that is not the title, pinned to the far edge as one group -- the artifact
	   count and the toolbar read as a pair rather than as two things that happen to have
	   ended up on the same side. */
	.right {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-left: auto;
	}

	/* The way back to something published nine turns ago. Without it, the only door to an
	   artifact is the card in the turn that made it, and an edit later on leaves you scrolling
	   for the thing you just changed. */
	.published {
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

	.toolbar {
		display: flex;
		align-items: center;
		gap: 4px;
	}

	.tool {
		display: grid;
		place-items: center;
		width: 28px;
		height: 28px;
		flex: none;
		border-radius: 50%;
		color: var(--text-muted);
		transition:
			color var(--fade) var(--ease),
			background var(--fade) var(--ease);
	}

	.tool:hover,
	.tool:focus-visible {
		color: var(--brass);
		background: var(--surface);
		outline: none;
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

	/* The conversation arrives where its shape was, rather than replacing it between frames. */
	.turns {
		animation: fade var(--fade) var(--ease);
	}

	@keyframes fade {
		from {
			opacity: 0;
		}
	}

	/* The same 22px the real messages sit in (`Message.svelte`'s `.mine`), so the conversation
	   lands where its shape was rather than a little above or below it. */
	.held-mine {
		display: flex;
		justify-content: flex-end;
		margin: 22px 0;
	}

	/* The measure a bubble is allowed (`Message.svelte`'s `.bubble`), given explicitly: a
	   percentage width inside a flex item that sizes to its content resolves against nothing
	   and comes out zero, which is a bubble you cannot see. */
	.held-mine :global(.skeleton) {
		width: min(46ch, 100%);
	}

	.held-hers {
		margin: 22px 0;
	}

	.held-mine :global(.bar) {
		border-radius: var(--radius-lg);
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
