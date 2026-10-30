<script lang="ts">
	/**
	 * Settings → Account → Passkeys: add one, see where each was last used, rename, remove
	 * (ADR 27, M4).
	 *
	 * Drawn only where a passkey can work — this browser has WebAuthn (a secure context) and the
	 * server can name a relying party for the address it is at — so the caller decides whether this
	 * appears at all. A new passkey is named after the browser and system it was made on, so a list
	 * of them can be told apart before anybody renames one.
	 */
	import { api, type PasskeyInfo } from '$lib/api/client';
	import Button from '$lib/components/ui/Button.svelte';
	import Confirm from '$lib/components/ui/Confirm.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import { t } from '$lib/i18n';
	import { cancelled, create, deviceName } from '$lib/passkeys';
	import { toasts } from '$lib/toasts.svelte';

	let passkeys = $state<PasskeyInfo[]>([]);
	let error = $state<string | null>(null);
	let busy = $state(false);
	let renaming = $state<string | null>(null);
	let draft = $state('');
	let removing = $state<PasskeyInfo | null>(null);

	async function load() {
		try {
			passkeys = await api.passkeys();
		} catch (cause) {
			error = message(cause);
		}
	}
	void load();

	function message(cause: unknown): string {
		return cause instanceof Error ? cause.message : String(cause);
	}

	async function add() {
		busy = true;
		error = null;
		try {
			const started = await api.passkeyOptions();
			const credential = await create(started.options);
			await api.addPasskey(started.ceremony, credential, deviceName());
			toasts.show(t.account.passkeyAdded);
			await load();
		} catch (cause) {
			if (cause instanceof DOMException && cause.name === 'InvalidStateError')
				error = t.account.passkeyTwice;
			else if (!cancelled(cause)) error = message(cause);
		} finally {
			busy = false;
		}
	}

	async function rename(passkey: PasskeyInfo) {
		const label = draft.trim();
		renaming = null;
		if (!label || label === passkey.label) return;
		try {
			const renamed = await api.renamePasskey(passkey.id, label);
			passkeys = passkeys.map((each) => (each.id === renamed.id ? renamed : each));
		} catch (cause) {
			error = message(cause);
		}
	}

	async function remove() {
		const passkey = removing;
		removing = null;
		if (!passkey) return;
		try {
			await api.removePasskey(passkey.id);
			passkeys = passkeys.filter((each) => each.id !== passkey.id);
		} catch (cause) {
			error = message(cause);
		}
	}

	const used = (passkey: PasskeyInfo) =>
		passkey.last_used_at
			? t.account.passkeyUsed(new Date(passkey.last_used_at).toLocaleString())
			: t.account.passkeyNeverUsed;
</script>

<p class="caption">{t.account.passkeysBlurb}</p>
<ul class="rows">
	{#each passkeys as passkey (passkey.id)}
		<li>
			{#if renaming === passkey.id}
				<form
					class="rename"
					onsubmit={(event) => {
						event.preventDefault();
						void rename(passkey);
					}}
				>
					<Input
						ariaLabel={t.account.passkeyName(passkey.label)}
						value={draft}
						autofocus
						onchange={(value) => (draft = value)}
					/>
					<Button type="submit" size="sm">{t.account.save}</Button>
					<Button size="sm" variant="ghost" onclick={() => (renaming = null)}>
						{t.account.cancel}
					</Button>
				</form>
			{:else}
				<span class="what">
					<span>{passkey.label}</span>
					<span class="when">{used(passkey)}</span>
				</span>
				<span class="actions">
					<Button
						size="sm"
						variant="ghost"
						onclick={() => {
							draft = passkey.label;
							renaming = passkey.id;
						}}>{t.account.rename}</Button
					>
					<IconButton
						icon="trash"
						size="sm"
						label={t.account.removePasskey(passkey.label)}
						onclick={() => (removing = passkey)}
					/>
				</span>
			{/if}
		</li>
	{:else}
		<li class="none">{t.account.noPasskeys}</li>
	{/each}
</ul>
{#if error}<p class="error" role="alert">{error}</p>{/if}
<div class="foot">
	<Button icon="key" {busy} onclick={add}>{t.account.addPasskey}</Button>
</div>

{#if removing}
	<Confirm
		title={t.account.removePasskeyTitle(removing.label)}
		body={t.account.removePasskeyBody}
		confirm={t.admin.deleteYes}
		cancel={t.admin.keep}
		onconfirm={remove}
		oncancel={() => (removing = null)}
	/>
{/if}

<style>
	.caption {
		margin: 0 0 8px;
		max-width: 520px;
	}

	.rows {
		margin: 0 0 12px;
		padding: 0;
		list-style: none;
		max-width: 520px;
	}

	.rows li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		min-height: 40px;
		padding: 6px 0;
		border-top: var(--border-width) solid var(--line);
		font-size: 13.5px;
	}

	.rows .none {
		color: var(--text-faint);
	}

	.what {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.when {
		color: var(--text-faint);
		font-size: 12px;
	}

	.actions,
	.rename,
	.foot {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.rename {
		flex: 1;
	}

	.error {
		margin: 0 0 12px;
		color: var(--danger);
		font-size: 13px;
	}
</style>
