<script lang="ts">
	/**
	 * Where an invitation or a reset link lands: choose a password, and be signed in (ADR 27).
	 *
	 * The token is the part after `#`, so no server ever logs it. It is read — not spent — to say
	 * who the link is for, and spent only by choosing the password, so a link opened in a mail
	 * client's preview still works afterwards. Signing in reloads at `/`, as signing in does
	 * everywhere else.
	 */
	import { api, type LinkInfo } from '$lib/api/client';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Ocellus from '$lib/components/ui/Ocellus.svelte';
	import { t } from '$lib/i18n';

	const token = window.location.hash.slice(1);

	let info = $state<LinkInfo | null>(null);
	let dead = $state(false);
	let password = $state('');
	let error = $state<string | null>(null);
	let busy = $state(false);

	void (async () => {
		if (!token) return void (dead = true);
		try {
			info = await api.openLink(token);
		} catch {
			dead = true;
		}
	})();

	async function choose() {
		busy = true;
		error = null;
		try {
			await api.useLink(token, password);
			window.location.assign('/');
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
			busy = false;
		}
	}
</script>

<svelte:head><title>{info ? info.instance_name : t.link.resetTitle}</title></svelte:head>

<main class="page">
	{#if dead}
		<div class="card">
			<div class="head">
				<Ocellus size={30} />
				<h3>{t.link.deadTitle}</h3>
				<p>{t.link.deadBlurb}</p>
			</div>
			<Button variant="ghost" onclick={() => window.location.assign('/login')}>
				{t.auth.backToSignIn}
			</Button>
		</div>
	{:else if info}
		<form
			class="card"
			onsubmit={(event) => {
				event.preventDefault();
				void choose();
			}}
		>
			<div class="head">
				<Ocellus size={30} />
				<h3>
					{info.purpose === 'invite' ? t.link.inviteTitle(info.instance_name) : t.link.resetTitle}
				</h3>
				<p>
					{info.purpose === 'invite'
						? t.link.inviteBlurb(info.email)
						: t.link.resetBlurb(info.email)}
				</p>
			</div>
			<Input
				kind="password"
				label={t.auth.password}
				placeholder={t.auth.passwordPlaceholder}
				value={password}
				autofocus
				onchange={(value) => (password = value)}
			/>
			{#if error}<p class="error" role="alert">{error}</p>{/if}
			<Button type="submit" variant="highlighted" size="lg" block {busy} disabled={!password}>
				{t.link.choose}
			</Button>
		</form>
	{/if}
</main>

<style>
	.page {
		display: grid;
		place-items: center;
		min-height: 100vh;
		min-height: 100dvh;
		padding: 24px;
		background: var(--ground);
	}

	.card {
		display: flex;
		flex-direction: column;
		gap: 14px;
		width: min(360px, 100%);
		padding: 22px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-lg);
		background: var(--surface);
	}

	.head {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8px;
		text-align: center;
	}

	h3 {
		margin: 0;
		font-family: var(--font-display);
		font-size: 22px;
		font-weight: var(--display-weight);
	}

	p {
		margin: 0;
		color: var(--text-muted);
		font-size: 12.5px;
	}

	.error {
		color: var(--danger);
		font-size: 13px;
	}
</style>
