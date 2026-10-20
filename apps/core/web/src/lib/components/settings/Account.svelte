<script lang="ts">
	/**
	 * Who you are to Hera: a name, an email and a picture.
	 *
	 * **A record, not a login.** Nothing here authenticates anybody — there is one owner and no
	 * sign-in — so password, two-factor and passkeys are drawn as disabled rows saying *coming
	 * later*. They are here so the shape of what is coming is visible, and not built, because a
	 * login half-built is worse than none.
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
	import { api } from '$lib/api/client';
	import { MAX_IMAGE_BYTES } from '$lib/attachments';
	import Input from '$lib/components/ui/Input.svelte';
	import { t } from '$lib/i18n';
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
		shows(t.account.security, t.account.password, t.account.twoFactor, t.account.passkeys)
	);

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
		<p class="caption">{t.account.securityNote}</p>
		<ul class="later">
			{#each [t.account.password, t.account.twoFactor, t.account.passkeys] as label (label)}
				<li>
					<span>{label}</span>
					<Pill>{t.account.later}</Pill>
				</li>
			{/each}
		</ul>
	</section>
{/if}

{#if !(showProfile || showSecurity)}
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

	.later {
		margin: 10px 0 0;
		padding: 0;
		list-style: none;
	}

	.later li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		max-width: 420px;
		padding: 8px 0;
		border-top: var(--border-width) solid var(--line);
		color: var(--text-faint);
		font-size: 13.5px;
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
