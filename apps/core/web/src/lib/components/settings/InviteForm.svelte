<script lang="ts">
	/**
	 * Inviting somebody: an address, a name if you like, and — for an admin — a role. The account
	 * is made at once, with no password; the link that goes to them is how they choose one.
	 * Used on Settings → Admin → Users, and on Settings → Account while registration is by
	 * invitation, where anybody may invite somebody as a user.
	 */
	import { api, type Invitation } from '$lib/api/client';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import { t } from '$lib/i18n';
	import SentLink from './SentLink.svelte';

	interface Props {
		/** Offers the role: only an admin may invite an admin. */
		admin?: boolean;
		oninvited?: (invitation: Invitation) => void;
	}

	let { admin = false, oninvited }: Props = $props();

	let email = $state('');
	let name = $state('');
	let role = $state<'user' | 'admin'>('user');
	let busy = $state(false);
	let error = $state<string | null>(null);
	let last = $state<Invitation | null>(null);

	async function send() {
		busy = true;
		error = null;
		try {
			last = await api.invite({ email: email.trim(), name: name.trim(), role });
			oninvited?.(last);
			email = name = '';
			role = 'user';
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		} finally {
			busy = false;
		}
	}
</script>

<form
	class="invite"
	onsubmit={(event) => {
		event.preventDefault();
		void send();
	}}
>
	<div class="fields">
		<Input
			kind="email"
			label={t.admin.email}
			placeholder="someone@example.org"
			value={email}
			onchange={(value) => (email = value)}
		/>
		<Input
			label={t.admin.name}
			placeholder={t.admin.namePlaceholder}
			value={name}
			onchange={(value) => (name = value)}
		/>
	</div>
	<div class="foot">
		{#if admin}
			<Segmented
				size="sm"
				label={t.admin.role}
				bind:value={role}
				options={[
					{ value: 'user', label: t.admin.roleUser },
					{ value: 'admin', label: t.admin.roleAdmin }
				]}
			/>
		{/if}
		<Button type="submit" variant="highlighted" icon="mail" {busy} disabled={!email.trim()}>
			{t.admin.send}
		</Button>
	</div>
	{#if error}<p class="error" role="alert">{error}</p>{/if}
</form>
{#if last}
	<SentLink sent={last} email={last.user.email} />
{/if}

<style>
	.invite {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.fields {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
		gap: 12px;
		max-width: 560px;
	}

	.foot {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.error {
		margin: 0;
		color: var(--danger);
		font-size: 13px;
	}
</style>
