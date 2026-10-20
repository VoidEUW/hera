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

	/** The three answers, each with its key (the theme's boxed option keys). Allowing is her
	 * authority being granted, so the first is brass; denying is the soft danger, because it is a
	 * refusal rather than a destruction. */
	const CHOICES = [
		{
			key: '1',
			label: t.permission.allowOnce,
			variant: 'highlighted',
			allow: true,
			remember: false
		},
		{ key: '2', label: t.permission.alwaysAllow, variant: 'neutral', allow: true, remember: true },
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

<aside class="card" class:settled={!!decided}>
	<p class="title">
		<span class="mark"><Icon name="shield" /></span>
		{named.server
			? t.permission.titleFrom(named.action, named.server)
			: t.permission.title(named.action)}
	</p>

	<p class="qualified mono">{named.qualified}</p>

	{#if args}
		<p class="args mono">{args}</p>
	{/if}
	{#if card.reason}
		<p class="reason">{card.reason}</p>
	{/if}

	{#if decided}
		<p class="outcome">{outcome}</p>
	{:else}
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
	/* No frame (the theme's `qc.frame: none`): the card is the question in the flow of the
	   answer, marked by its brass icon and its keys rather than boxed off from it. */
	.card {
		margin: calc(var(--space) * 4) 0;
		max-width: var(--measure);
		animation: card-in var(--motion-card-enter);
		/* Answering is the card settling: the three buttons leave and the card takes on the quieter
		   surface it keeps for the rest of the conversation's life. Both halves of that used to
		   happen in one frame, so the decision read as the card being replaced rather than as the
		   card being answered. */
		transition:
			background-color var(--fade) var(--ease),
			opacity var(--fade) var(--ease);
	}

	@keyframes card-in {
		from {
			opacity: 0;
		}
	}

	.settled {
		opacity: 0.85;
	}

	.title {
		margin: 0;
		font-family: var(--font-body);
		font-size: 16px;
		display: flex;
		gap: 8px;
		align-items: baseline;
	}

	.mark {
		display: flex;
		align-self: center;
		color: var(--brass);
	}

	.qualified {
		margin: 4px 0 0;
		font-size: 12px;
		color: var(--text-faint);
	}

	.args {
		margin: 6px 0 0;
		color: var(--text-muted);
		overflow-wrap: anywhere;
	}

	.reason {
		margin: 6px 0 0;
		font-size: 13px;
		color: var(--text-muted);
	}

	/* What was decided, said once and kept. It replaces the buttons, so it is the half of the
	   answer that arrives — faded rather than instant, so the card is seen to change its mind
	   about asking. */
	.outcome {
		margin: 10px 0 0;
		font-size: 12.5px;
		color: var(--brass);
		animation: fade var(--fade) var(--ease);
	}

	@keyframes fade {
		from {
			opacity: 0;
		}
	}

	.actions {
		display: flex;
		gap: 8px;
		justify-content: flex-end;
		margin-top: 14px;
		flex-wrap: wrap;
	}
</style>
