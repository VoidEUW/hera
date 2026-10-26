<script lang="ts">
	/**
	 * What replaces a screen when loading it failed (the theme's `hera/error-page`, soft look): a
	 * centred filled card with a large mark, rising into place (`error.enter`). It says what
	 * happened, what that means, and the one thing to do next.
	 *
	 * The mark is the ocellus bent by the kind: shut for offline, a red iris for a server fault, a
	 * dimmed eye for an address that leads nowhere, a broken ring for a model that does not answer.
	 * The words are the caller's, because only the caller knows what failed. A command to run sits
	 * in a box with a copy button, because the person reading this is about to go and type it.
	 */
	import type { Snippet } from 'svelte';
	import { t } from '$lib/i18n';
	import { toasts } from '$lib/toasts.svelte';
	import Button from './Button.svelte';
	import IconButton from './IconButton.svelte';
	import Ocellus from './Ocellus.svelte';

	type Kind = 'offline' | 'server' | 'not-found' | 'model';

	interface Action {
		label: string;
		onclick: () => void;
		busy?: boolean;
	}

	interface Props {
		kind: Kind;
		/** `page` replaces a whole screen; `panel` stands in for one pane of a larger one — a
		 * settings screen, a side view — and is the same card, scaled to the room it has. */
		size?: 'page' | 'panel';
		/** The small line over the title. Defaults to the kind's own word; a caller that knows the
		 * status says it (`500 · Server error`), because the number is what a person searches for. */
		code?: string;
		title: string;
		body: string;
		/** A command to copy, with a line saying what it does. */
		command?: { text: string; hint?: string };
		primary?: Action;
		secondary?: Action;
		/** What the browser or the server actually said. */
		detail?: { label: string; text: string };
		/** Anything else the screen needs under its actions — a retry countdown. */
		children?: Snippet;
	}

	let {
		kind,
		size = 'page',
		code,
		title,
		body,
		command,
		primary,
		secondary,
		detail,
		children
	}: Props = $props();

	async function copy(text: string) {
		try {
			await navigator.clipboard.writeText(text);
			toasts.show(t.message.copied);
		} catch {
			/* A browser that will not give us the clipboard: the text is on screen to be read. */
		}
	}
</script>

<div class="page {size}">
	<section class="card {kind}" role={kind === 'not-found' ? undefined : 'alert'}>
		<Ocellus
			size={size === 'panel' ? 32 : 44}
			closed={kind === 'offline'}
			tone={kind === 'server'
				? 'server'
				: kind === 'not-found'
					? 'missing'
					: kind === 'model'
						? 'model'
						: undefined}
		/>
		<div class="code">{code ?? t.errorPage[kind]}</div>
		<h1>{title}</h1>
		<p class="body">{body}</p>

		{#if command}
			<div class="command">
				<code>$ {command.text}</code>
				<IconButton icon="copy" label={t.ui.copy} onclick={() => copy(command.text)} />
			</div>
			{#if command.hint}<p class="hint">{command.hint}</p>{/if}
		{/if}

		{#if primary || secondary}
			<div class="actions">
				{#if primary}
					<Button variant="highlighted" busy={primary.busy} onclick={primary.onclick}>
						{primary.label}
					</Button>
				{/if}
				{#if secondary}
					<Button variant="ghost" onclick={secondary.onclick}>{secondary.label}</Button>
				{/if}
			</div>
		{/if}

		{@render children?.()}

		{#if detail}
			<details class="detail">
				<summary>{detail.label}</summary>
				<pre>{detail.text}</pre>
			</details>
		{/if}
	</section>
</div>

<style>
	.page {
		display: grid;
		place-items: center;
		min-height: 100%;
		padding: 40px 24px;
		background: var(--ground);
	}

	.card {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 14px;
		width: 100%;
		max-width: 480px;
		padding: 32px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-lg);
		background: var(--surface);
		text-align: center;
		animation: rise var(--motion-error-enter);
	}

	/* A pane, not a screen: no ground of its own and no claim on the full height, so it sits in
	   the panel it replaced rather than pushing the panel's frame around. */
	.panel {
		min-height: 0;
		padding: 28px 0;
		background: none;
	}

	.panel .card {
		gap: 10px;
		max-width: 440px;
		padding: 24px;
	}

	.panel h1 {
		font-size: 21px;
	}

	.panel .body {
		font-size: 13px;
	}

	@keyframes rise {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
	}

	.code {
		color: var(--danger);
		font: 500 11px var(--font-mono);
		letter-spacing: 0.12em;
		text-transform: uppercase;
	}

	.not-found .code {
		color: var(--text-faint);
	}

	h1 {
		margin: 0;
		font-family: var(--font-display);
		font-size: 28px;
		font-weight: var(--display-weight);
		line-height: 1.15;
		text-wrap: balance;
	}

	.body {
		max-width: 46ch;
		margin: 0;
		color: var(--text-muted);
		font-size: 14px;
		line-height: 1.55;
	}

	.command {
		display: flex;
		align-items: center;
		gap: 6px;
		width: 100%;
		max-width: 360px;
		padding: 4px 4px 4px 12px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: var(--ground);
		font: 12.5px var(--font-mono);
		text-align: left;
	}

	code {
		flex: 1;
		overflow: hidden;
		font: inherit;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.hint {
		margin: 0;
		color: var(--text-faint);
		font-size: 12px;
	}

	.actions {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 8px;
	}

	.detail {
		width: 100%;
		text-align: left;
	}

	summary {
		padding: 4px 0;
		color: var(--text-faint);
		font-size: 12px;
		cursor: pointer;
	}

	summary:hover {
		color: var(--text);
	}

	pre {
		max-height: 200px;
		margin: 8px 0 0;
		padding: 12px;
		overflow: auto;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: var(--ground);
		color: var(--text-muted);
		font: 12px/1.6 var(--font-mono);
		white-space: pre-wrap;
		overflow-wrap: anywhere;
	}
</style>
