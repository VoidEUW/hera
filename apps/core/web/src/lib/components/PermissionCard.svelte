<script lang="ts">
	/**
	 * The one moment the interface blocks.
	 *
	 * An `ask` outcome stops the turn and puts the decision in front of a person, inline where
	 * the call would have happened. Brass edge — this is authority.
	 *
	 * The second line is the arguments; the third is the rule's own `reason`, and filling that
	 * field in server-side is exactly why it exists: "why am I being asked this" should not be a
	 * question only the configuration file can answer.
	 *
	 * **Always allow** writes a rule and says so afterwards, because a person should never
	 * wonder whether a decision stuck.
	 */
	import Button from './ui/Button.svelte';
	import Pill from './ui/Pill.svelte';
	import Icon from './ui/Icon.svelte';
	import Kbd from './ui/Kbd.svelte';
	import type { PermissionRequired } from '$lib/api/events';
	import { t } from '$lib/i18n';
	import { toolName } from '$lib/tools';

	interface Props {
		card: PermissionRequired;
		/** Settled cards render their outcome instead of buttons — read from the persisted
		 * `permission_decided`, never inferred from what turned up afterwards. */
		decided?: { allowed: boolean; remembered: boolean } | null;
		busy?: boolean;
		onanswer?: (allow: boolean, remember: boolean) => void;
	}

	let { card, decided = null, busy = false, onanswer }: Props = $props();

	/** The three answers, each with its key (the theme's boxed option keys): Allow once, Always
	 * allow — the one the card leads with, brass, because it is her authority being granted for
	 * good — and Deny, the soft danger, because it is a refusal rather than a destruction. */
	const CHOICES = [
		{ key: '1', label: t.permission.allowOnce, variant: 'neutral', allow: true, remember: false },
		{
			key: '2',
			label: t.permission.alwaysAllow,
			variant: 'highlighted',
			allow: true,
			remember: true
		},
		{ key: '3', label: t.permission.deny, variant: 'danger-soft', allow: false, remember: false }
	] as const;

	/** The keys answer the card that is waiting, unless a person is typing somewhere — a `1` in
	 * the composer is a `1`, not a decision. */
	function onkeydown(event: KeyboardEvent) {
		if (decided || busy || event.metaKey || event.ctrlKey || event.altKey) return;
		const target = event.target as HTMLElement | null;
		if (target?.closest('input, textarea, select, [contenteditable="true"]')) return;
		const choice = CHOICES.find((option) => option.key === event.key);
		if (!choice) return;
		event.preventDefault();
		onanswer?.(choice.allow, choice.remember);
	}

	// "Run docker__mcp-find?" is a question about machinery. The decision being asked for is
	// about an action and where it will happen, so that is what the sentence says -- with the
	// qualified name kept underneath, because that is the thing a rule gets written against
	// and a person answering "always allow" deserves to see it.
	const named = $derived(toolName(card.tool));

	const args = $derived(
		Object.entries(card.arguments)
			.map(([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`)
			.join('  ')
	);

	const outcome = $derived.by(() => {
		if (!decided) return '';
		if (!decided.allowed) return t.permission.denied;
		return decided.remembered ? t.permission.alwaysAllowed : t.permission.allowedOnce;
	});
</script>

<svelte:window {onkeydown} />

<!-- The theme's permission card (`hera/question-card`, `qc.frame: none`, `qc.keys: boxed`): a
     brass capital header with the shield, what she wants to run as a sentence, exactly what will
     run in a mono box on the ground, then the three answers with their keys. -->
<aside class="card" class:settled={!!decided}>
	<p class="head">
		<Icon name="shield" />
		<span>{t.permission.heading}</span>
		{#if decided}
			<Pill tone={decided.allowed ? 'live' : 'danger'}>{outcome}</Pill>
		{/if}
	</p>

	<p class="title">
		{named.server
			? t.permission.titleFrom(named.action, named.server)
			: t.permission.title(named.action)}
	</p>
	{#if card.reason}
		<p class="reason">{card.reason}</p>
	{/if}

	<div class="command">
		<span class="qualified">{named.qualified}</span>
		{#if args}<span>{args}</span>{/if}
	</div>

	{#if !decided}
		<div class="actions">
			{#each CHOICES as choice (choice.key)}
				<Button
					variant={choice.variant}
					size="sm"
					disabled={busy}
					aria-keyshortcuts={choice.key}
					onclick={() => onanswer?.(choice.allow, choice.remember)}
				>
					<!-- Drawn, not read: `aria-keyshortcuts` already tells a screen reader the key. -->
					<span aria-hidden="true"><Kbd>{choice.key}</Kbd></span>
					{choice.label}
				</Button>
			{/each}
		</div>
	{/if}
</aside>

<style>
	.card {
		display: flex;
		flex-direction: column;
		gap: 12px;
		max-width: var(--measure);
		margin: calc(var(--space) * 4) 0;
		animation: card-in var(--motion-card-enter);
	}

	@keyframes card-in {
		from {
			opacity: 0;
		}
	}

	.head {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0;
		color: var(--brass);
		font-size: 11px;
		font-weight: 600;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.settled .head {
		color: var(--text-faint);
	}

	.title {
		margin: 0;
		font-family: var(--font-body);
		font-size: 16px;
		line-height: 1.5;
	}

	.reason {
		margin: 0;
		color: var(--text-muted);
		font-size: 13px;
	}

	/* Exactly what will run (`.pc .cmd`): mono, on the ground, in a hairline box. */
	.command {
		display: flex;
		flex-direction: column;
		gap: 2px;
		padding: 9px 12px;
		overflow-x: auto;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-sm);
		background: var(--ground);
		color: var(--text);
		font: 12.5px var(--font-mono);
		overflow-wrap: anywhere;
	}

	.qualified {
		color: var(--text-faint);
	}

	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
</style>
