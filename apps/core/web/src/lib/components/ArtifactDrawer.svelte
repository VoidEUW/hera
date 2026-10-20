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
	import { headingOf, newest } from '$lib/artifacts';
	import { t } from '$lib/i18n';
	import { slot, still } from '$lib/motion';
	import { artifacts } from '$lib/stores/artifacts.svelte';
	import ArtifactView from './ArtifactView.svelte';
	import CloseButton from './ui/CloseButton.svelte';
	import Icon from './ui/Icon.svelte';

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
	<header class="top">
		<span class="mark"><Icon name="file" /></span>
		<h2 class="title">{chosen ? headingOf(chosen) : t.artifact.panel}</h2>
		<CloseButton label={t.artifact.close} onclick={() => artifacts.close()} />
	</header>

	<div class="body">
		{#if chosen}
			{#key chosen}
				<ArtifactView {chatId} name={chosen} height="100%" source={artifacts.source} />
			{/key}
		{:else if failure}
			<p class="failed">{failure}</p>
		{:else}
			<p class="empty">{t.artifact.none}</p>
		{/if}
	</div>
</aside>

<style>
	/* The side view (the theme's `hera/side-view`): a filled `--surface` panel, floating on the
	   ground like the sidebar on the other edge, so the two sides of the screen are one family. */
	.drawer {
		display: flex;
		flex-direction: column;
		width: min(46vw, 720px);
		flex: none;
		margin: calc(var(--space) * 2);
		border-radius: var(--radius-lg);
		background: var(--surface);
		box-shadow: var(--shadow-sm);
		overflow: hidden;
	}

	/* No rule under the header (the theme's `drw.header: none`): the title, the tools and the
	   body read as one panel. */
	.top {
		display: flex;
		align-items: center;
		gap: 8px;
		flex: none;
		padding: calc(var(--space) * 3) calc(var(--space) * 3.5);
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

	.mark {
		display: flex;
		color: var(--brass);
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
	.body :global(.source) {
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
