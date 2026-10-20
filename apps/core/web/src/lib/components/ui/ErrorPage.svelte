<script lang="ts">
	/**
	 * What replaces a screen when loading it failed (the theme's `hera/error-page`): offline, a
	 * server error, not found, a model that does not answer. It says what happened, what that
	 * means, and the one thing to do next — in that order, in a centred card with a large mark.
	 *
	 * The kind decides the mark and nothing else; the words are the caller's, because only the
	 * caller knows what failed. A command to run is copyable with one click, because the person
	 * reading this screen is about to go and type it. Technical detail is there for whoever needs
	 * it and quiet for whoever does not.
	 */
	import type { Snippet } from 'svelte';
	import { t } from '$lib/i18n';
	import type { IconName } from '$lib/icons';
	import { toasts } from '$lib/toasts.svelte';
	import Button from './Button.svelte';
	import Icon from './Icon.svelte';

	type Kind = 'offline' | 'server' | 'not-found' | 'model';

	interface Action {
		label: string;
		onclick: () => void;
		busy?: boolean;
	}

	interface Props {
		kind: Kind;
		title: string;
		body: string;
		/** A command to copy, with a line saying what it does. */
		command?: { text: string; hint?: string };
		primary?: Action;
		secondary?: Action;
		/** What the browser or the server actually said. */
		detail?: { label: string; text: string };
		/** Anything else the screen needs under its actions. */
		children?: Snippet;
	}

	let { kind, title, body, command, primary, secondary, detail, children }: Props = $props();

	const MARK: Record<Kind, IconName> = {
		offline: 'plug',
		server: 'alert',
		'not-found': 'search',
		model: 'cube'
	};

	async function copy(text: string) {
		try {
			await navigator.clipboard.writeText(text);
			toasts.show(t.message.copied);
		} catch {
			/* A browser that will not give us the clipboard: the text is on screen to be read. */
		}
	}
</script>

<div class="page">
	<section class="card {kind}" role={kind === 'not-found' ? undefined : 'alert'}>
		<span class="mark"><Icon name={MARK[kind]} size="28px" /></span>
		<h1 class="title">{title}</h1>
		<p class="body">{body}</p>

		{#if command}
			<button class="command" type="button" onclick={() => copy(command.text)}>
				<span class="mono">{command.text}</span>
				<Icon name="copy" />
			</button>
			{#if command.hint}<p class="hint">{command.hint}</p>{/if}
		{/if}

		{#if primary || secondary}
			<div class="actions">
				{#if secondary}
					<Button variant="ghost" onclick={secondary.onclick}>{secondary.label}</Button>
				{/if}
				{#if primary}
					<Button variant="highlighted" disabled={primary.busy} onclick={primary.onclick}>
						{primary.label}
					</Button>
				{/if}
			</div>
		{/if}

		{@render children?.()}

		{#if detail}
			<details class="detail">
				<summary>{detail.label}</summary>
				<p class="mono">{detail.text}</p>
			</details>
		{/if}
	</section>
</div>

<style>
	.page {
		display: grid;
		place-items: center;
		min-height: 100%;
		padding: calc(var(--space) * 6);
	}

	/* The soft look: a filled card, centred, rising into place (`error.enter`). */
	.card {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: calc(var(--space) * 3);
		width: min(480px, 100%);
		padding: calc(var(--space) * 10) calc(var(--space) * 8);
		border-radius: var(--radius-lg);
		background: var(--surface);
		box-shadow: var(--shadow-sm);
		text-align: center;
		animation: rise var(--motion-error-enter);
	}

	@keyframes rise {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
	}

	.mark {
		display: grid;
		place-items: center;
		width: 64px;
		height: 64px;
		border-radius: 50%;
		background: var(--danger-soft);
		color: var(--danger);
	}

	/* Not found is not a failure of anything: the address simply leads nowhere. */
	.not-found .mark {
		background: var(--hover);
		color: var(--text-muted);
	}

	.title {
		margin: calc(var(--space) * 1) 0 0;
		font-family: var(--font-display);
		font-size: 30px;
		font-weight: var(--display-weight);
		line-height: 1.15;
	}

	.body {
		max-width: 40ch;
		margin: 0;
		color: var(--text-muted);
		line-height: 1.55;
	}

	.command {
		display: flex;
		align-items: center;
		gap: calc(var(--space) * 3);
		margin-top: calc(var(--space) * 2);
		padding: calc(var(--space) * 2) calc(var(--space) * 3.5);
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: var(--ground);
		color: var(--text);
		transition: border-color var(--fade) var(--ease);
	}

	.command:hover {
		border-color: var(--text-faint);
	}

	.command :global(.icon) {
		color: var(--text-faint);
	}

	.hint {
		margin: 0;
		color: var(--text-faint);
		font-size: calc(var(--ui-size) - 1.5px);
	}

	.actions {
		display: flex;
		gap: calc(var(--space) * 2);
		margin-top: calc(var(--space) * 3);
	}

	.detail {
		width: 100%;
		margin-top: calc(var(--space) * 2);
		color: var(--text-faint);
		font-size: calc(var(--ui-size) - 1.5px);
		text-align: left;
	}

	.detail summary {
		cursor: pointer;
		text-align: center;
	}

	.detail p {
		margin: calc(var(--space) * 2) 0 0;
		overflow-wrap: anywhere;
	}
</style>
