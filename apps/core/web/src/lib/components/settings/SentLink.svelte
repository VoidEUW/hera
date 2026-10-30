<script lang="ts">
	/**
	 * What became of a link made for somebody: handed to the mail server, or not — and the link
	 * itself with a copy button either way. A mail can take a while, or bounce after the server
	 * took it, and the person waiting for it should not wait on Hera to find out.
	 */
	import type { Sent } from '$lib/api/client';
	import Button from '$lib/components/ui/Button.svelte';
	import { t } from '$lib/i18n';
	import { copyText } from '$lib/clipboard';
	import { toasts } from '$lib/toasts.svelte';

	interface Props {
		sent: Sent;
		email: string;
	}

	let { sent, email }: Props = $props();

	async function copy() {
		toasts.show((await copyText(sent.link)) ? t.admin.copied : t.admin.copyFailed);
	}
</script>

<div class="sent" role="status">
	{#if sent.mailed}
		<p>{t.admin.mailed(email)}</p>
		<p class="quiet">{t.admin.orCopy}</p>
	{:else}
		{#if sent.mail_error}<p class="failed">{t.admin.mailFailed(sent.mail_error)}</p>{/if}
		<p>{t.admin.handOver}</p>
	{/if}
	<div class="link">
		<code>{sent.link}</code>
		<Button size="sm" icon="copy" onclick={copy}>{t.admin.copy}</Button>
	</div>
</div>

<style>
	.sent {
		display: flex;
		flex-direction: column;
		gap: 6px;
		max-width: 560px;
		margin-top: 10px;
		padding: 10px 12px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius);
		background: var(--surface);
		font-size: 13px;
	}

	p {
		margin: 0;
	}

	.failed {
		color: var(--danger);
	}

	.quiet {
		color: var(--text-muted);
	}

	.link {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	code {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		user-select: all;
		font-family: var(--font-mono);
		font-size: 12px;
		color: var(--text-muted);
	}
</style>
