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
	import { api } from '$lib/api/client';
	import { MAX_IMAGE_BYTES } from '$lib/attachments';
	import Input from '$lib/components/Input.svelte';
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
	let input = $state<HTMLInputElement | null>(null);

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

	async function choose(event: Event) {
		const target = event.currentTarget as HTMLInputElement;
		const file = target.files?.[0];
		target.value = '';
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

	function initials(value: string): string {
		return value
			.split(/\s+/)
			.filter(Boolean)
			.slice(0, 2)
			.map((part) => part[0]?.toUpperCase() ?? '')
			.join('');
	}
</script>

{#if error}
	<p class="error">{error}</p>
{/if}

{#if showProfile}
	<section>
		<h3>{t.account.avatar}</h3>
		<div class="avatar-row">
			{#if account?.avatar_version}
				<img
					class="face"
					src={api.avatarUrl(account.avatar_version)}
					alt=""
					width="64"
					height="64"
				/>
			{:else}
				<span class="face initials" aria-hidden="true">{initials(account?.name ?? '') || '·'}</span>
			{/if}
			<div class="actions">
				<button class="button" type="button" onclick={() => input?.click()}>
					{account?.avatar_version ? t.account.replace : t.account.upload}
				</button>
				{#if account?.avatar_version}
					<button class="button quiet" type="button" onclick={clear}>{t.account.remove}</button>
				{/if}
			</div>
			<input
				bind:this={input}
				class="file"
				type="file"
				accept={TYPES.join(',')}
				tabindex="-1"
				aria-label={t.account.upload}
				onchange={choose}
			/>
		</div>
		<p class="caption">{t.account.avatarNote}</p>
	</section>

	<section>
		<label class="field">
			<span class="heading">{t.account.name}</span>
			<Input
				value={name}
				placeholder={t.account.namePlaceholder}
				ariaLabel={t.account.name}
				onchange={(value) => (name = value)}
			/>
		</label>
		<label class="field">
			<span class="heading">{t.account.email}</span>
			<Input
				value={email}
				placeholder={t.account.emailPlaceholder}
				ariaLabel={t.account.email}
				onchange={(value) => (email = value)}
			/>
		</label>
		{#if emailBad}
			<p class="caption problem">{t.account.emailInvalid}</p>
		{/if}
		<div class="foot">
			<button class="button" type="button" disabled={!dirty || emailBad} onclick={save}>
				{t.settings.save}
			</button>
			{#if saved}<span class="caption saved">{t.account.saved}</span>{/if}
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
					<button type="button" disabled>
						<span>{label}</span>
						<span class="caption">{t.account.later}</span>
					</button>
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

	.face {
		display: grid;
		place-items: center;
		width: 64px;
		height: 64px;
		flex: none;
		border-radius: 50%;
		object-fit: cover;
		background: var(--surface-raised);
		border: 1px solid var(--line);
	}

	.initials {
		font-size: 20px;
		letter-spacing: 0.04em;
		color: var(--text-muted);
	}

	.actions {
		display: flex;
		gap: 8px;
	}

	.file {
		display: none;
	}

	.button {
		padding: 5px 12px;
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 13px;
		color: var(--text-muted);
	}

	.button:not(:disabled):hover {
		border-color: var(--brass);
		color: var(--brass);
	}

	.button:disabled {
		opacity: 0.4;
		cursor: default;
	}

	.quiet {
		border-color: transparent;
	}

	.field {
		display: block;
		max-width: 360px;
		margin-bottom: 12px;
	}

	.heading {
		display: block;
		margin-bottom: 4px;
		font-size: 12.5px;
		color: var(--text-muted);
	}

	.foot {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.saved {
		margin: 0;
		color: var(--laurel);
	}

	.later {
		margin: 10px 0 0;
		padding: 0;
		list-style: none;
	}

	.later button {
		display: flex;
		width: 100%;
		align-items: baseline;
		justify-content: space-between;
		max-width: 420px;
		padding: 8px 0;
		border-top: 1px solid var(--line);
		font-size: 13.5px;
		color: var(--text-faint);
		cursor: not-allowed;
		text-align: left;
	}

	.later li {
		max-width: 420px;
	}

	.problem,
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
