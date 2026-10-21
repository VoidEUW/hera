<script lang="ts">
	/**
	 * The panel beside the transcript: one artifact full size, a download, and everything else
	 * this conversation published.
	 *
	 * This is the drawer M3 planned to build once for three panels (`docs/versions/v0.2.0.md`),
	 * arriving a milestone early because artifacts is the panel that needed it. Memory and the
	 * dream log are meant to fit this frame rather than each bringing their own, so what is
	 * artifact-specific here is deliberately only the body and the file bar.
	 *
	 * **A drawer rather than a modal**, for the reason Settings is a modal and this is not: you
	 * keep working with this open — reading the page, asking for a change, watching it change.
	 * So it takes width from the conversation instead of covering it, and there is no scrim.
	 *
	 * The **file bar** is what makes an artifact reachable after the turn that made it has
	 * scrolled away. Without it, `artifact_edit` in turn nine leaves you scrolling back to turn
	 * four to find the card that opens the file it just changed.
	 */
	import { api } from '$lib/api/client';
	import { keys } from '$lib/keys';
	import { downloadUrl, hasSource, kindOf, newest } from '$lib/artifacts';
	import { t } from '$lib/i18n';
	import { saveDiagram } from '$lib/mermaid';
	import { slot, still } from '$lib/motion';
	import { artifacts } from '$lib/stores/artifacts.svelte';
	import { toasts } from '$lib/toasts.svelte';
	import ArtifactView from './ArtifactView.svelte';
	import Button from './ui/Button.svelte';
	import CloseButton from './ui/CloseButton.svelte';
	import Confirm from './ui/Confirm.svelte';
	import Icon from './ui/Icon.svelte';
	import IconButton from './ui/IconButton.svelte';
	import Segmented from './ui/Segmented.svelte';

	interface Props {
		chatId: string;
	}

	let { chatId }: Props = $props();

	/** How long it waits first, when it is opening. Just past `--fade`, so on a reload the
	 * conversation has finished arriving before the panel starts taking width from it — two
	 * things happening in a row, which is what *the drawer opens beside the chat* looks like,
	 * rather than at once, which is what it looked like when they shared a frame. Closing has
	 * no delay: that one is a click, and a control that hesitates feels broken. */
	const AFTER = 140;

	/** Take the width from the conversation over a beat instead of all at once.
	 *
	 * A width change and a fade — the two things `docs/frontend.md` § *Motion* allows — and
	 * pointedly **not** a slide, which the same paragraph rules out. Written by hand rather than
	 * taken from `svelte/transition` because none of them animates width, and the alternative is
	 * the panel arriving with the conversation already narrowed behind it, which is what a
	 * person coming back to a chat with artifacts used to see.
	 *
	 * Two cases it does not apply to. Below the phone breakpoint the panel is `position: fixed`
	 * and full-bleed, so there is no width to give and narrowing it would squeeze the content
	 * against the right edge; it fades instead. And with motion turned off it is instant, which
	 * the global `prefers-reduced-motion` rule in `app.css` cannot do for a transition that
	 * lives in JavaScript. */
	function reveal(node: HTMLElement, { delay = 0 } = {}) {
		if (still()) return { duration: 0, css: () => '' };
		// The theme's `drawer.open` slot: longer than `--fade`, because this is a change to the
		// shape of the screen rather than to the look of one thing on it.
		const { duration, easing } = slot('drawer-open');
		if (matchMedia('(max-width: 780px)').matches) {
			return { delay, duration, easing, css: (t: number) => `opacity: ${t}` };
		}
		const width = node.getBoundingClientRect().width;
		return {
			delay,
			duration,
			easing,
			// `overflow: hidden` for the length of it: the body is laid out for the full width
			// and reflowing it three times a frame on the way in is a different animation.
			css: (t: number) => `width: ${t * width}px; opacity: ${t}; overflow: hidden`
		};
	}

	let failure = $state('');

	const chosen = $derived(artifacts.name);

	let copied = $state(false);

	/** Switch the pen on or off. Writing is done on the source, so on a file that has a drawn
	 * form it also moves to Source — the box cannot be over a picture. */
	function toggleEdit() {
		const on = !artifacts.editing;
		artifacts.editing = on;
		if (on && chosen && hasSource(chosen)) artifacts.source = true;
	}

	/** Save what was typed. The server replaces the file; every view of it then looks again. */
	async function save() {
		if (!chosen || artifacts.draft === null || artifacts.saving) return;
		artifacts.saving = true;
		try {
			await api.writeArtifact(chatId, chosen, artifacts.draft);
			artifacts.draft = null;
			artifacts.version += 1;
			toasts.show(t.artifact.saved);
		} catch (cause) {
			toasts.show(t.artifact.saveFailed(cause instanceof Error ? cause.message : String(cause)));
		} finally {
			artifacts.saving = false;
		}
	}

	/** Copy the file as it is now. Fetched rather than taken from the view: the view may be
	 * showing a drawing, and what a person copies from a side view is the file. */
	async function copy() {
		if (!chosen) return;
		try {
			const content = await api.artifact(chatId, chosen);
			await navigator.clipboard.writeText(content.text);
		} catch {
			return;
		}
		copied = true;
		toasts.show(t.ui.copied);
		setTimeout(() => (copied = false), 1400);
	}

	// ⌘S is the Save button, so it only answers while there is something to save; otherwise the
	// browser's own Save keeps the chord (#112).
	$effect(() =>
		keys.on('chat.save', () => {
			if (!artifacts.dirty) return false;
			void save();
		})
	);

	$effect(() => {
		// The listing is re-read when something published changes, so a file created in the turn
		// you are watching appears in the bar without a reload.
		void artifacts.version;
		const chat = chatId;
		let current = true;
		api
			.artifacts(chat)
			.then((found) => {
				if (!current) return;
				// Two cases, one answer: nothing is chosen, or what was chosen is not in the
				// listing any more. An open panel showing *Nothing chosen yet* beside a bar of
				// files is a door that led nowhere, and one still pointed at a deleted file is
				// worse — `ArtifactView` stays mounted on a name that will not fetch. What she
				// wrote last is the best guess anybody can make about which to show instead, and
				// `newest` of an empty listing is `null`, which is the honest empty state.
				//
				// Safe inside the `.then`: this runs after the effect has finished tracking, so
				// reading `artifacts.name` here does not make the effect depend on what it sets.
				const gone = artifacts.name !== null && !found.some((file) => file.name === artifacts.name);
				if (artifacts.name === null || gone) {
					artifacts.show(chat, newest(found)?.name ?? null);
				}
			})
			.catch((cause) => {
				if (current) failure = cause instanceof Error ? cause.message : String(cause);
			});
		return () => {
			current = false;
		};
	});
</script>

<aside class="drawer" in:reveal={{ delay: AFTER }} out:reveal aria-label={t.artifact.panel}>
	<!-- The side view's header (`hera/side-view`): the file, Preview / Source when it has both, then
	     copy, download and close. Everything that acts on *which file* is here, beside its name. -->
	<header class="top">
		<span class="name">
			<Icon name="file" />
			<span>{chosen ?? t.artifact.panel}</span>
		</span>
		{#if chosen}
			{#if hasSource(chosen)}
				<Segmented
					size="sm"
					label={t.artifact.view}
					value={artifacts.source ? 'source' : 'preview'}
					options={[
						{ value: 'preview', label: t.ui.preview },
						{ value: 'source', label: t.ui.source }
					]}
					onchange={(next) => {
						artifacts.source = next === 'source';
						// The pen is over the source; leaving it for the drawn thing puts it down.
						if (next === 'preview') artifacts.editing = false;
					}}
				/>
			{/if}
			{#if kindOf(chosen) !== 'file'}
				<IconButton
					icon="edit"
					on={artifacts.editing}
					aria-pressed={artifacts.editing}
					label={t.artifact.edit}
					onclick={toggleEdit}
				/>
			{/if}
			<IconButton icon={copied ? 'check' : 'copy'} on={copied} label={t.ui.copy} onclick={copy} />
			{#if kindOf(chosen) === 'mermaid'}
				<!-- A diagram is saved as the page that draws it — a conversion only a browser can do
				     (`$lib/mermaid`), so this one is a fetch and a blob, not a link. -->
				<IconButton
					icon="download"
					label={t.artifact.downloadDrawnOne(chosen)}
					onclick={() => saveDiagram(chatId, chosen)}
				/>
			{:else}
				<IconButton
					icon="download"
					label={t.artifact.downloadOne(chosen)}
					href={downloadUrl(chatId, chosen)}
					download={chosen}
					external
				/>
			{/if}
		{/if}
		{#if artifacts.editing || artifacts.dirty}
			<Button
				variant="highlighted"
				size="sm"
				busy={artifacts.saving}
				keyId="chat.save"
				disabled={!artifacts.dirty}
				onclick={save}
			>
				{t.artifact.save}
			</Button>
		{/if}
		<CloseButton label={t.artifact.close} onclick={() => artifacts.ask(() => artifacts.close())} />
	</header>

	<div class="body">
		{#if chosen}
			{#key chosen}
				<ArtifactView
					{chatId}
					name={chosen}
					height="100%"
					source={artifacts.source}
					bare
					editable
				/>
			{/key}
		{:else if failure}
			<p class="failed">{failure}</p>
		{:else}
			<p class="empty">{t.artifact.none}</p>
		{/if}
	</div>
</aside>

{#if artifacts.asking && chosen}
	<Confirm
		title={t.artifact.discardTitle}
		body={t.artifact.discardBody(chosen)}
		confirm={t.artifact.discardYes}
		cancel={t.artifact.discardKeep}
		onconfirm={() => artifacts.discard()}
		oncancel={() => (artifacts.asking = null)}
	/>
{/if}

<style>
	/* The side view (the theme's `hera/side-view`, soft look): a filled `--surface` panel against
	   the transcript's right edge, a hairline between them. It takes its width over `drawer.open`
	   and the transcript reflows beside it. */
	.drawer {
		display: flex;
		flex: none;
		flex-direction: column;
		width: min(46vw, 720px);
		overflow: hidden;
		border-left: var(--border-width) solid var(--line);
		background: var(--surface);
	}

	/* No rule under the header (the theme's `drw.header: none`): the title, the tools and the
	   body read as one panel. */
	.top {
		display: flex;
		flex: none;
		align-items: center;
		gap: 8px;
		min-height: 52px;
		padding: 10px 10px 10px 14px;
	}

	.name {
		display: flex;
		flex: 1;
		align-items: center;
		gap: 8px;
		min-width: 0;
		overflow: hidden;
		font-size: 13px;
		font-weight: 500;
		white-space: nowrap;
	}

	.name span {
		overflow: hidden;
		text-overflow: ellipsis;
	}

	/* Beside the transcript at 46vw of a phone width is not a panel, it is the whole screen with
	   the conversation squeezed into a sliver beside it — so below the shared breakpoint this
	   goes full-bleed instead. Still no scrim: `artifacts.close()` above is already the way out,
	   and a full-bleed sheet leaves nothing peeking out from behind it for a scrim to dim. */
	@media (max-width: 780px) {
		/* Full-bleed on a phone: no edge to float off. */
		.drawer {
			position: fixed;
			inset: 0;
			width: 100%;
			margin: 0;
			border-radius: 0;
			z-index: 12;
		}

		.top {
			padding-top: max(12px, env(safe-area-inset-top));
		}
	}

	/* The body owns the height it is given, so an HTML artifact's frame fills the panel rather
	   than being a fixed box inside a taller one. */
	.body {
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
	}

	/* Whatever is shown runs to the edges of the panel. The header above draws the line a frame
	   would, so a border, a radius or a margin here is a box in a box — and the padding is gone
	   from the body rather than cancelled with a negative margin on the child, because the
	   child's own `max-height: 100%` is measured inside the padding and would stop short of the
	   bottom. */
	.body :global(.frame),
	.body :global(.drawing),
	.body :global(.document),
	.body :global(.code) {
		flex: 1;
		min-height: 0;
		border: 0;
		border-radius: 0;
	}

	/* The one-line states are text, not a surface, so they keep their own margin. */
	.body > :global(p) {
		padding: 14px;
	}

	.empty,
	.failed {
		margin: 0;
		font-size: 13px;
		color: var(--text-faint);
	}

	.failed {
		color: var(--danger);
	}
</style>
