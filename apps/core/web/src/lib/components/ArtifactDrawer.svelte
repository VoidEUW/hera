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
	import { cubicOut } from 'svelte/easing';
	import { api, type ArtifactSummary } from '$lib/api/client';
	import { downloadUrl, newest, size, titleOf } from '$lib/artifacts';
	import { t } from '$lib/i18n';
	import { artifacts } from '$lib/stores/artifacts.svelte';
	import ArtifactView from './ArtifactView.svelte';
	import Stele from './Stele.svelte';
	import Tray from './Tray.svelte';

	interface Props {
		chatId: string;
	}

	let { chatId }: Props = $props();

	/** How long the panel takes to make room for itself. Longer than `--fade`, because this is
	 * a change to the shape of the screen rather than to the look of one thing on it. */
	const REVEAL = 240;

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
		const still = matchMedia('(prefers-reduced-motion: reduce)').matches;
		if (still) return { duration: 0, css: () => '' };
		if (matchMedia('(max-width: 780px)').matches) {
			return { delay, duration: REVEAL, easing: cubicOut, css: (t: number) => `opacity: ${t}` };
		}
		const width = node.getBoundingClientRect().width;
		return {
			delay,
			duration: REVEAL,
			easing: cubicOut,
			// `overflow: hidden` for the length of it: the body is laid out for the full width
			// and reflowing it three times a frame on the way in is a different animation.
			css: (t: number) => `width: ${t * width}px; opacity: ${t}; overflow: hidden`
		};
	}

	let listed = $state<ArtifactSummary[]>([]);
	let failure = $state('');

	const chosen = $derived(artifacts.name);

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
				listed = found;
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
	<header class="top">
		<span class="mark" aria-hidden="true"><Stele size={14} /></span>
		<h2 class="title">{chosen ? titleOf(chosen) : t.artifact.panel}</h2>
		{#if chosen}
			<!-- A plain link, not a fetch and a blob: the browser knows how to save a file, and the
			     response says `attachment` with a neutral media type, so a page she wrote is never
			     a document rendered at Hera's own origin. -->
			<a class="action save" href={downloadUrl(chatId, chosen)} download={chosen} rel="external">
				<Tray size={13} />
				{t.artifact.download}
			</a>
		{/if}
		<button class="close" type="button" onclick={() => artifacts.close()}>
			<span class="sr-only">{t.artifact.close}</span>
			<span class="glyph" aria-hidden="true"></span>
		</button>
	</header>

	<div class="body">
		{#if chosen}
			{#key chosen}
				<ArtifactView {chatId} name={chosen} height="100%" />
			{/key}
		{:else if failure}
			<p class="failed">{failure}</p>
		{:else}
			<p class="empty">{t.artifact.none}</p>
		{/if}
	</div>

	{#if listed.length}
		<nav class="files" aria-label={t.artifact.files}>
			<ul>
				{#each listed as file (file.name)}
					<li>
						<button
							type="button"
							class:current={file.name === chosen}
							onclick={() => artifacts.show(chatId, file.name)}
						>
							<span class="name">{file.name}</span>
							<span class="bytes">{size(file.bytes)}</span>
						</button>
					</li>
				{/each}
			</ul>
		</nav>
	{/if}
</aside>

<style>
	.drawer {
		display: flex;
		flex-direction: column;
		width: min(46vw, 720px);
		flex: none;
		border-left: 1px solid var(--line);
		background: var(--ground);
	}

	.top {
		display: flex;
		align-items: center;
		gap: 8px;
		flex: none;
		padding: 12px 14px;
		border-bottom: 1px solid var(--line);
	}

	/* Beside the transcript at 46vw of a phone width is not a panel, it is the whole screen with
	   the conversation squeezed into a sliver beside it — so below the shared breakpoint this
	   goes full-bleed instead. Still no scrim: `artifacts.close()` above is already the way out,
	   and a full-bleed sheet leaves nothing peeking out from behind it for a scrim to dim. */
	@media (max-width: 780px) {
		.drawer {
			position: fixed;
			inset: 0;
			width: 100%;
			z-index: 12;
			border-left: 0;
		}

		.top {
			padding-top: max(12px, env(safe-area-inset-top));
		}
	}

	.mark {
		display: flex;
	}

	/* The gap belongs after the title, not before the first control. `:first-of-type` counts per
	   element, so an `<a>` and a `<button>` in this row were each the first of theirs and both
	   took the space — which put a hole between Download and Close. */
	.title {
		margin: 0 auto 0 0;
		font-family: var(--font-display);
		font-size: 15px;
		font-weight: 500;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.action {
		flex: none;
		padding: 4px 9px;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 12.5px;
		color: var(--text-muted);
		text-decoration: none;
		transition:
			color var(--fade) var(--ease),
			border-color var(--fade) var(--ease);
	}

	.action:hover {
		color: var(--text);
		border-color: var(--brass);
	}

	/* The same glyph the card carries, so *save this* is one mark wherever it appears. */
	.save {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	/* The same close control the modal shell carries (#99): a hairline circle with a 32px hit
	   area, drawn here rather than imported because a drawer is not a modal and the shell's
	   scrim and focus handling would be wrong in it. */
	.close {
		display: flex;
		align-items: center;
		justify-content: center;
		flex: none;
		width: 32px;
		height: 32px;
		padding: 0;
		background: none;
		border: 1px solid var(--line);
		border-radius: 50%;
		color: var(--text-muted);
		transition:
			border-color var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	.close:hover,
	.close:focus-visible {
		border-color: var(--brass);
		color: var(--brass);
	}

	.close:active {
		transform: scale(0.95);
	}

	.glyph {
		position: relative;
		width: 10px;
		height: 10px;
	}

	.glyph::before,
	.glyph::after {
		content: '';
		position: absolute;
		top: 50%;
		left: 50%;
		width: 12px;
		height: 1.5px;
		background: currentcolor;
		border-radius: 1px;
	}

	.glyph::before {
		transform: translate(-50%, -50%) rotate(45deg);
	}

	.glyph::after {
		transform: translate(-50%, -50%) rotate(-45deg);
	}

	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
		border: 0;
	}

	/* The body owns the height it is given, so an HTML artifact's frame fills the panel rather
	   than being a fixed box inside a taller one. */
	.body {
		flex: 1;
		min-height: 0;
		padding: 14px;
		display: flex;
		flex-direction: column;
	}

	.body :global(.frame) {
		flex: 1;
		min-height: 0;
	}

	.files {
		flex: none;
		max-height: 24vh;
		overflow: auto;
		border-top: 1px solid var(--line);
	}

	.files ul {
		margin: 0;
		padding: 6px;
		list-style: none;
	}

	.files button {
		display: flex;
		align-items: baseline;
		gap: 10px;
		width: 100%;
		padding: 5px 8px;
		border-radius: var(--radius);
		font-size: 12.5px;
		color: var(--text-muted);
		text-align: left;
	}

	.files button:hover {
		background: var(--surface);
		color: var(--text);
	}

	.files button.current {
		color: var(--text);
		background: var(--surface-raised);
	}

	.name {
		font-family: var(--font-mono);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.bytes {
		margin-left: auto;
		flex: none;
		color: var(--text-faint);
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
