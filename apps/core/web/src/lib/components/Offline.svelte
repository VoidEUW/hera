<script lang="ts">
	/**
	 * Nothing answered, so there is nothing to draw: the screen that replaces the application
	 * when the very first load never landed.
	 *
	 * The whole shell rather than a banner over it, because without that first answer there is
	 * no rail, no profile, no endpoint and no conversation — and a rail that draws its chrome
	 * beside an empty list is inviting somebody to click seven things that cannot work. The one
	 * control here is the one that can.
	 *
	 * It says *she is not answering* rather than *network error*. Hera is served by the
	 * application she talks to (ADR 6), so the request that failed did not cross a network: if
	 * the page loaded and `/api/v1` did not, a process is not running, and the next thing anybody
	 * needs is the command that starts it.
	 */
	import { t } from '$lib/i18n';
	import { workspace } from '$lib/stores/workspace.svelte';
	import Ocellus from './Ocellus.svelte';

	let copied = $state(false);

	async function copy() {
		try {
			await navigator.clipboard.writeText(t.offline.command);
			copied = true;
			setTimeout(() => (copied = false), 1600);
		} catch {
			/* A browser that will not give us the clipboard: the text is on screen to be read. */
		}
	}
</script>

<div class="offline">
	<div class="middle" role="alert">
		<!-- Still, and dimmed to half. The mark is how the interface says *she is here*; this is
		     the one screen where the honest thing for it to say is that she is not. -->
		<span class="mark" aria-hidden="true"><Ocellus size={34} /></span>

		<h1 class="display">{t.offline.title}</h1>
		<p class="body">{t.offline.body}</p>

		<button class="command mono" type="button" onclick={copy}>
			<span>{t.offline.command}</span>
			<span class="copied caption" class:on={copied}>{t.message.copied}</span>
		</button>
		<p class="caption hint">{t.offline.commandHint}</p>

		<button
			class="retry"
			type="button"
			disabled={workspace.retrying}
			onclick={() => workspace.retry()}
		>
			{workspace.retrying ? t.error.retrying : t.error.retry}
		</button>

		{#if workspace.error}
			<p class="detail caption">
				<span class="label">{t.offline.detail}</span>
				<span class="mono">{workspace.error}</span>
			</p>
		{/if}
	</div>
</div>

<style>
	.offline {
		display: grid;
		place-items: center;
		height: 100%;
		padding: 24px;
	}

	.middle {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		width: min(58ch, 100%);
		animation: fade var(--fade) var(--ease);
	}

	@keyframes fade {
		from {
			opacity: 0;
		}
	}

	.mark {
		display: block;
		margin-bottom: 18px;
		opacity: 0.5;
	}

	h1 {
		margin: 0;
		font-size: 28px;
	}

	.body {
		margin: 10px 0 0;
		font-family: var(--font-body);
		font-size: 16px;
		line-height: 1.6;
		color: var(--text-muted);
	}

	/* The command is the answer, so it is a thing you can take rather than a thing you retype. */
	.command {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-top: 20px;
		padding: 9px 12px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 13px;
		color: var(--text);
		transition: border-color var(--fade) var(--ease);
	}

	.command:hover {
		border-color: var(--brass);
	}

	.copied {
		opacity: 0;
		color: var(--laurel);
		transition: opacity var(--fade) var(--ease);
	}

	.copied.on {
		opacity: 1;
	}

	.hint {
		margin: 6px 0 0;
	}

	.retry {
		margin-top: 24px;
		padding: 8px 18px;
		background: var(--brass);
		border-radius: var(--radius);
		color: var(--ground);
		font-size: 14px;
		transition: opacity var(--fade) var(--ease);
	}

	.retry:hover {
		opacity: 0.88;
	}

	.retry:disabled {
		opacity: 0.6;
	}

	/* What actually went wrong, kept under the thing to do about it: the sentence above is the
	   answer for almost everybody, and this is for the case where it was not. */
	.detail {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		margin: 20px 0 0;
		padding-top: 14px;
		border-top: 1px solid var(--line);
		width: 100%;
	}

	.detail .label {
		color: var(--text-faint);
	}
</style>
