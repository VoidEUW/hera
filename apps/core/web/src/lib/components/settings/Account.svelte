<script lang="ts">
	/**
	 * Who you are to Hera: a name, an email and a picture — and how you sign in.
	 *
	 * While registration here is by invitation, anybody may invite somebody, and the section that
	 * does it is here — an admin has Settings → Admin → Users for that instead.
	 *
	 * The sign-in section lists the browsers you are signed in on, each one revocable, with
	 * *sign out* and *sign out everywhere*, and changes the password. Passkeys have a section of
	 * their own where they can work at all — see `Passkeys.svelte`. Signing out reloads at `/login` rather than navigating there:
	 * every store in the shell was built for you, and a reload is how none of it outlives you.
	 *
	 * The picture is cropped to a square and scaled down in the browser before it is sent: it is
	 * drawn at 24 px in the rail, and the server is not the place to learn what a 12 MB photo
	 * looks like at that size. The server still holds the upload to the limits an image
	 * attachment has (type, size, and bytes that match the type).
	 */
	import Button from '$lib/components/ui/Button.svelte';
	import Avatar from '$lib/components/ui/Avatar.svelte';
	import FileButton from '$lib/components/ui/FileButton.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';
	import { api, type SignedInSession } from '$lib/api/client';
	import { MAX_IMAGE_BYTES } from '$lib/attachments';
	import Input from '$lib/components/ui/Input.svelte';
	import { t } from '$lib/i18n';
	import { available } from '$lib/passkeys';
	import InviteForm from './InviteForm.svelte';
	import Passkeys from './Passkeys.svelte';
	import { workspace } from '$lib/stores/workspace.svelte';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	const TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'];
	const SIZE = 256;
	const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

	const account = $derived(workspace.account);

	// Drafts start from what is stored and are only reseeded when it changes underneath, so a
	// slow first answer fills the fields without trampling something already being typed.
	let name = $state('');
	let email = $state('');
	let seeded = false;
	$effect(() => {
		if (account && !seeded) {
			name = account.name;
			email = account.email;
			seeded = true;
		}
	});

	let error = $state<string | null>(null);
	let saved = $state(false);
	const emailBad = $derived(email.trim() !== '' && !EMAIL.test(email.trim()));
	const dirty = $derived(
		!!account && (name.trim() !== account.name || email.trim() !== account.email)
	);

	const shows = (...words: string[]) =>
		!filter || words.some((word) => word.toLowerCase().includes(filter));
	const showProfile = $derived(shows(t.account.name, t.account.email, t.account.avatar));
	const showSecurity = $derived(
		shows(
			t.account.security,
			t.account.password,
			t.account.passkeys,
			t.account.sessions,
			t.auth.signOut
		)
	);

	/** Whether this person may invite somebody: registration by invitation, and not an admin,
	 * who invites from the Users screen. */
	let byInvitation = $state(false);
	/** Passkeys can work here: this browser has WebAuthn, and the server can name this site. */
	let passkeysHere = $state(false);
	const showInvite = $derived(
		byInvitation && account?.role !== 'admin' && shows(t.admin.invite, t.admin.email)
	);
	void (async () => {
		try {
			byInvitation = (await api.instance()).registration === 'invite';
			passkeysHere = available() && (await api.authState()).passkeys;
		} catch {
			// Nothing to offer, and nothing worth saying: the rest of the screen still works.
		}
	})();

	let sessions = $state<SignedInSession[]>([]);
	let current = $state('');
	let fresh = $state('');
	let changed = $state(false);

	async function loadSessions() {
		try {
			sessions = await api.sessions();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		}
	}
	void loadSessions();

	function seen(session: SignedInSession): string {
		return new Date(session.last_seen_at).toLocaleString();
	}

	async function revoke(session: SignedInSession) {
		error = null;
		try {
			await api.revokeSession(session.id);
			if (session.current) return window.location.assign('/login');
			await loadSessions();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		}
	}

	async function signOut(everywhere: boolean) {
		error = null;
		try {
			await (everywhere ? api.signOutEverywhere() : api.signOut());
			window.location.assign('/login');
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		}
	}

	async function changePassword() {
		error = null;
		changed = false;
		try {
			await api.changePassword(current, fresh);
			current = fresh = '';
			changed = true;
			await loadSessions();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		}
	}

	async function save() {
		if (emailBad) return;
		error = null;
		try {
			workspace.account = await api.updateAccount({ name: name.trim(), email: email.trim() });
			saved = true;
			setTimeout(() => (saved = false), 1600);
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		}
	}

	async function choose(files: FileList) {
		const file = files[0];
		if (!file) return;
		error = null;
		if (!TYPES.includes(file.type)) {
			error = t.account.notAnImage;
			return;
		}
		if (file.size > MAX_IMAGE_BYTES) {
			error = t.account.tooBig;
			return;
		}
		try {
			workspace.account = await api.setAvatar(await squared(file));
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		}
	}

	async function clear() {
		error = null;
		try {
			workspace.account = await api.removeAvatar();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		}
	}

	/** The middle square of the picture, at {@link SIZE} px, as a PNG data URL. */
	async function squared(file: File): Promise<string> {
		const bitmap = await createImageBitmap(file);
		const side = Math.min(bitmap.width, bitmap.height);
		const canvas = document.createElement('canvas');
		canvas.width = canvas.height = SIZE;
		canvas
			.getContext('2d')
			?.drawImage(
				bitmap,
				(bitmap.width - side) / 2,
				(bitmap.height - side) / 2,
				side,
				side,
				0,
				0,
				SIZE,
				SIZE
			);
		bitmap.close();
		return canvas.toDataURL('image/png');
	}
</script>

{#if error}
	<p class="error">{error}</p>
{/if}

{#if showProfile}
	<section>
		<h3>{t.account.avatar}</h3>
		<div class="avatar-row">
			<Avatar
				name={account?.name ?? ''}
				src={account?.avatar_version ? api.avatarUrl(account.avatar_version) : undefined}
				size={64}
			/>
			<div class="actions">
				<FileButton icon="image" label={t.account.upload} accept={TYPES.join(',')} onfiles={choose}>
					{account?.avatar_version ? t.account.replace : t.account.upload}
				</FileButton>
				{#if account?.avatar_version}
					<Button variant="ghost" onclick={clear}>{t.account.remove}</Button>
				{/if}
			</div>
		</div>
		<p class="caption">{t.account.avatarNote}</p>
	</section>

	<section>
		<div class="fields">
			<Input
				label={t.account.name}
				value={name}
				placeholder={t.account.namePlaceholder}
				onchange={(value) => (name = value)}
			/>
			<Input
				kind="email"
				label={t.account.email}
				error={emailBad ? t.account.emailInvalid : undefined}
				value={email}
				placeholder={t.account.emailPlaceholder}
				onchange={(value) => (email = value)}
			/>
		</div>
		<div class="foot">
			<Button variant="highlighted" disabled={!dirty || emailBad} onclick={save}>
				{t.settings.save}
			</Button>
			{#if saved}<Pill tone="live">{t.account.saved}</Pill>{/if}
		</div>
	</section>
{/if}

{#if showSecurity}
	<section>
		<h3>{t.account.security}</h3>
		<div class="foot">
			<Button icon="exit" onclick={() => signOut(false)}>{t.auth.signOut}</Button>
			<Button variant="ghost" onclick={() => signOut(true)}>{t.auth.signOutEverywhere}</Button>
		</div>
		<p class="caption">{t.auth.signOutEverywhereNote}</p>
	</section>

	<section>
		<h3>{t.account.sessions}</h3>
		<ul class="rows">
			{#each sessions as session (session.id)}
				<li>
					<span class="what">
						<span
							>{session.current
								? t.account.thisBrowser
								: session.user_agent || t.account.unknownBrowser}</span
						>
						<span class="when">{t.account.lastSeen(seen(session))}</span>
					</span>
					<Button size="sm" variant="ghost" onclick={() => revoke(session)}>
						{t.account.revoke}
					</Button>
				</li>
			{/each}
		</ul>
	</section>

	<section>
		<h3>{t.account.password}</h3>
		<form
			class="fields"
			onsubmit={(event) => {
				event.preventDefault();
				void changePassword();
			}}
		>
			<Input
				kind="password"
				label={t.account.currentPassword}
				value={current}
				onchange={(value) => (current = value)}
			/>
			<Input
				kind="password"
				label={t.account.newPassword}
				placeholder={t.auth.passwordPlaceholder}
				value={fresh}
				onchange={(value) => (fresh = value)}
			/>
			<div class="foot">
				<Button type="submit" disabled={!current || !fresh}>{t.account.changePassword}</Button>
				{#if changed}<Pill tone="live">{t.account.passwordChanged}</Pill>{/if}
			</div>
		</form>
	</section>

	{#if passkeysHere}
		<section>
			<h3>{t.account.passkeys}</h3>
			<Passkeys />
		</section>
	{/if}
{/if}

{#if showInvite}
	<section>
		<h3>{t.admin.invite}</h3>
		<p class="caption invite-blurb">{t.admin.memberInviteBlurb}</p>
		<InviteForm />
	</section>
{/if}

{#if !(showProfile || showSecurity || showInvite)}
	<p class="empty">{t.settings.noMatch}</p>
{/if}

<style>
	section {
		padding: 14px 0;
		border-bottom: 1px solid var(--line);
	}

	h3 {
		margin: 0 0 8px;
		font-size: 14px;
		font-weight: 500;
	}

	.caption {
		margin: 6px 0 0;
	}

	.invite-blurb {
		margin: 0 0 12px;
	}

	.avatar-row {
		display: flex;
		align-items: center;
		gap: 16px;
	}

	.actions {
		display: flex;
		gap: 8px;
	}

	.fields {
		display: flex;
		flex-direction: column;
		gap: 12px;
		max-width: 360px;
		margin-bottom: 12px;
	}

	.foot {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.rows {
		margin: 0;
		padding: 0;
		list-style: none;
		max-width: 520px;
	}

	.rows li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		padding: 8px 0;
		border-top: var(--border-width) solid var(--line);
		font-size: 13.5px;
	}

	.what {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.what > span:first-child {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.when {
		color: var(--text-faint);
		font-size: 12px;
	}

	.error {
		color: var(--danger);
	}

	.error {
		margin: 0 0 14px;
		font-size: 13px;
	}

	.empty {
		margin: 18px 0;
		font-family: var(--font-body);
		font-size: 15px;
		color: var(--text-muted);
	}
</style>
