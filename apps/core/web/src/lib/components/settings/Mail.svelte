<script lang="ts">
	/**
	 * Settings → Admin → Mail, and the setup wizard's mail step: the SMTP server invitations and
	 * resets go out through (ADR 27), and a test message to yourself through it.
	 *
	 * The password is written and never read back, like an endpoint's API key: the screen knows
	 * only whether one is saved. Leaving the field empty keeps it; *forget the password* clears it.
	 * The test goes through what is *saved*, so it saves first — a test of what is on screen but
	 * not on disk would pass and then not be what sends the next invitation.
	 */
	import { api, type MailSecurity, type MailSettings } from '$lib/api/client';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import NumberField from '$lib/components/ui/NumberField.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import { t } from '$lib/i18n';
	import { Placeholder } from '$lib/loading.svelte';
	import { workspace } from '$lib/stores/workspace.svelte';
	import LoadFailed from './LoadFailed.svelte';
	import Rows from './Rows.svelte';

	/** The port each kind of security usually means. Switching security moves a port that was
	 * still the old kind's usual one, and leaves one somebody chose. */
	const USUAL: Record<MailSecurity, number> = { starttls: 587, tls: 465, none: 25 };

	interface Props {
		/** Where the test goes, for the sentence afterwards. The wizard has no workspace yet. */
		email?: string;
	}

	let { email }: Props = $props();

	let stored = $state<MailSettings | null>(null);
	let host = $state('');
	let port = $state<number | null>(587);
	let security = $state<MailSecurity>('starttls');
	let user = $state('');
	let password = $state('');
	let sender = $state('');
	let senderName = $state('');
	/** What `[mail]` falls back to for the name: this Hera's own. */
	let instanceName = $state('Hera');
	/** Signing in as one address and sending as another is the most common reason a mail is
	 * taken by the server and then refused or distrusted by the receiver: most providers only
	 * vouch for the account's own address and its aliases. Said here, where both are typed. */
	const foreign = $derived(
		user.includes('@') &&
			sender.includes('@') &&
			user.trim().toLowerCase() !== sender.trim().toLowerCase()
	);
	const from = $derived(
		sender.trim() ? `${senderName.trim() || instanceName} <${sender.trim()}>` : ''
	);

	let failed = $state<unknown>(null);
	let error = $state<string | null>(null);
	let note = $state<string | null>(null);
	let busy = $state(false);

	const settling = new Placeholder(true);
	$effect(() => () => settling.stop());

	function seed(mail: MailSettings) {
		stored = mail;
		host = mail.host;
		port = mail.port;
		security = mail.security;
		user = mail.user;
		sender = mail.sender;
		senderName = mail.sender_name;
		password = '';
	}

	async function load() {
		failed = null;
		settling.set(true);
		try {
			const [mail, instance] = await Promise.all([api.mail(), api.instance()]);
			instanceName = instance.name;
			seed(mail);
		} catch (cause) {
			failed = cause;
		} finally {
			settling.set(false);
		}
	}
	void load();

	function secure(next: MailSecurity) {
		if (port === USUAL[security]) port = USUAL[next];
		security = next;
	}

	async function run(work: () => Promise<void>) {
		busy = true;
		error = note = null;
		try {
			await work();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		} finally {
			busy = false;
		}
	}

	const write = async (extra: { password?: string } = {}) =>
		seed(
			await api.updateMail({
				host: host.trim(),
				port: port ?? USUAL[security],
				security,
				user: user.trim(),
				sender: sender.trim(),
				sender_name: senderName.trim(),
				...(password ? { password } : {}),
				...extra
			})
		);

	const save = () =>
		run(async () => {
			await write();
			note = t.mail.saved;
		});
	const forget = () => run(() => write({ password: '' }));
	const test = () =>
		run(async () => {
			await write();
			await api.testMail();
			note = t.mail.testSent(email ?? workspace.account?.email ?? '');
		});
</script>

{#if settling.shown}
	<Rows label={t.settings.loading} rows={4} />
{:else if failed !== null}
	<LoadFailed cause={failed} what={t.loadFailed.what.mail} onretry={load} />
{:else}
	<form
		onsubmit={(event) => {
			event.preventDefault();
			void save();
		}}
	>
		{#if stored && !stored.configured}
			<p class="caption">{t.mail.notConfigured}</p>
		{:else if stored?.links_need_public_url}
			<p class="caption">{t.mail.needsPublicUrl}</p>
		{/if}
		<div class="pair">
			<Input
				mono
				label={t.mail.host}
				placeholder="smtp.example.com"
				value={host}
				onchange={(value) => (host = value)}
			/>
			<NumberField
				label={t.mail.port}
				min={1}
				max={65535}
				value={port}
				onchange={(value) => (port = value)}
			/>
		</div>
		<div class="group">
			<span class="label">{t.mail.security}</span>
			<Segmented
				size="sm"
				label={t.mail.security}
				value={security}
				onchange={secure}
				options={[
					{ value: 'starttls', label: t.mail.starttls },
					{ value: 'tls', label: t.mail.tls },
					{ value: 'none', label: t.mail.none }
				]}
			/>
			<p class="caption">{t.mail.securityHelp}</p>
		</div>
		<Input
			label={t.mail.user}
			help={t.mail.userHelp}
			value={user}
			onchange={(value) => (user = value)}
		/>
		<Input
			kind="password"
			label={t.mail.password}
			placeholder={stored?.password_set ? t.mail.passwordSet : ''}
			value={password}
			onchange={(value) => (password = value)}
		/>
		<!-- Text, not email: a pasted `Hera <hera@example.com>` is welcome, and the server splits
		     it into the name and the address. -->
		<Input
			label={t.mail.sender}
			help={t.mail.senderHelp}
			placeholder="hera@example.com"
			value={sender}
			onchange={(value) => (sender = value)}
		/>
		<Input
			label={t.mail.senderName}
			help={t.mail.senderNameHelp}
			placeholder={instanceName}
			value={senderName}
			onchange={(value) => (senderName = value)}
		/>
		{#if from}<p class="caption from">{t.mail.fromPreview(from)}</p>{/if}
		{#if foreign}<p class="caption warn" role="note">{t.mail.fromNotUser(user.trim())}</p>{/if}
		{#if error}<p class="error" role="alert">{error}</p>{/if}
		<div class="foot">
			<Button type="submit" variant="highlighted" {busy}>{t.settings.save}</Button>
			<Button icon="mail" disabled={busy || !host.trim() || !sender.trim()} onclick={test}>
				{t.mail.test}
			</Button>
			{#if stored?.password_set}
				<Button variant="ghost" disabled={busy} onclick={forget}>{t.mail.clearPassword}</Button>
			{/if}
			{#if note === t.mail.saved}<Pill tone="live">{note}</Pill>{/if}
		</div>
		{#if note && note !== t.mail.saved}<p class="caption" role="status">{note}</p>{/if}
	</form>
{/if}

<style>
	form {
		display: flex;
		flex-direction: column;
		gap: 14px;
		max-width: 520px;
		padding: 14px 0;
	}

	.pair {
		display: grid;
		grid-template-columns: 1fr 110px;
		gap: 12px;
	}

	.group {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 8px;
	}

	.label {
		font-size: 12.5px;
		color: var(--text-muted);
	}

	.caption {
		margin: 0;
	}

	.from,
	.warn {
		color: var(--text);
	}

	.foot {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px;
	}

	.error {
		margin: 0;
		color: var(--danger);
		font-size: 13px;
	}
</style>
