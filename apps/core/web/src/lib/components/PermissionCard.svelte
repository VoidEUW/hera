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
	import type { PermissionRequired } from '$lib/api/events';
	import { t } from '$lib/i18n';

	interface Props {
		card: PermissionRequired;
		/** Settled cards render their outcome instead of buttons — read from the persisted
		 * `permission_decided`, never inferred from what turned up afterwards. */
		decided?: { allowed: boolean; remembered: boolean } | null;
		busy?: boolean;
		onanswer?: (allow: boolean, remember: boolean) => void;
	}

	let { card, decided = null, busy = false, onanswer }: Props = $props();

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

<aside class="card" class:settled={!!decided}>
	<p class="title">
		<span class="mark" aria-hidden="true">⬡</span>
		{t.permission.title(card.tool)}
	</p>

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
			<button type="button" disabled={busy} onclick={() => onanswer?.(true, false)}>
				{t.permission.allowOnce}
			</button>
			<button type="button" disabled={busy} onclick={() => onanswer?.(true, true)}>
				{t.permission.alwaysAllow}
			</button>
			<button class="deny" type="button" disabled={busy} onclick={() => onanswer?.(false, false)}>
				{t.permission.deny}
			</button>
		</div>
	{/if}
</aside>

<style>
	.card {
		margin: 16px 0;
		padding: 14px 16px;
		max-width: var(--measure);
		background: var(--surface-raised);
		border: 1px solid var(--line);
		border-left: 3px solid var(--brass);
		border-radius: var(--radius);
	}

	.settled {
		background: var(--surface);
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
		color: var(--brass);
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

	.outcome {
		margin: 10px 0 0;
		font-size: 12.5px;
		color: var(--brass);
	}

	.actions {
		display: flex;
		gap: 8px;
		justify-content: flex-end;
		margin-top: 14px;
		flex-wrap: wrap;
	}

	.actions button {
		padding: 6px 12px;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		background: var(--surface);
		font-size: 13px;
		transition:
			border-color var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	.actions button:not(:disabled):hover {
		border-color: var(--brass);
		color: var(--brass);
	}

	.actions button:disabled {
		opacity: 0.5;
		cursor: default;
	}

	.deny:not(:disabled):hover {
		border-color: var(--danger);
		color: var(--danger);
	}
</style>
