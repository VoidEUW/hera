<script lang="ts">
	/**
	 * Signing in, or registering where this Hera takes registrations (ADR 27).
	 *
	 * Drawn without the rail. Arriving here already signed in goes straight on; arriving at an
	 * instance nobody has claimed goes to the wizard instead. On success the page is **reloaded**
	 * at where you were going rather than navigated to: every store in the shell was built for
	 * nobody, and a reload is the one way to be sure none of them still is.
	 *
	 * *Forgot your password?* turns the card into a request for a link when this Hera can mail
	 * one, and into a sentence about asking an admin when it cannot. Sent or not, the answer is
	 * the same for every address — the server's, and so this page's.
	 */
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { api, type Registration } from '$lib/api/client';
	import Auth from '$lib/components/ui/Auth.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Ocellus from '$lib/components/ui/Ocellus.svelte';
	import { safeNext } from '$lib/errors';
	import { t } from '$lib/i18n';

	const next = safeNext(page.url.searchParams.get('next'));

	let mode = $state<'in' | 'up'>('in');
	let forgetting = $state(false);
	let resetByMail = $state(false);
	let resetEmail = $state('');
	let resetSent = $state(false);
	let registration = $state<Registration>('closed');
	let instance = $state('Hera');
	let error = $state<string | null>(null);
	let busy = $state(false);
	let ready = $state(false);

	void (async () => {
		try {
			const state = await api.authState();
			if (state.setup_required) return void (await goto(resolve('/setup')));
			if (state.user) return window.location.assign(next);
			registration = state.registration;
			instance = state.instance_name;
			resetByMail = state.reset_by_mail;
			if (registration !== 'open') mode = 'in';
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		}
		ready = true;
	})();

	async function askForReset() {
		busy = true;
		error = null;
		try {
			await api.requestReset(resetEmail.trim());
			resetSent = true;
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		} finally {
			busy = false;
		}
	}

	async function submit(details: {
		mode: 'in' | 'up';
		name: string;
		email: string;
		password: string;
	}) {
		busy = true;
		error = null;
		try {
			if (details.mode === 'in') await api.signIn(details.email, details.password);
			else
				await api.register({
					name: details.name,
					email: details.email,
					password: details.password
				});
			window.location.assign(next);
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
			busy = false;
		}
	}
</script>

<svelte:head><title>{t.auth.signIn} — {instance}</title></svelte:head>

<main class="login">
	{#if ready && forgetting}
		<form
			class="card"
			onsubmit={(event) => {
				event.preventDefault();
				void askForReset();
			}}
		>
			<div class="head">
				<Ocellus size={30} />
				<h3>{t.auth.resetTitle}</h3>
				{#if resetByMail && !resetSent}<p>{t.auth.resetBlurb}</p>{/if}
			</div>
			{#if !resetByMail}
				<p role="status">{t.auth.resetAskAdmin}</p>
			{:else if resetSent}
				<p role="status">{t.auth.resetSent}</p>
			{:else}
				<Input
					kind="email"
					label={t.auth.email}
					placeholder="you@example.com"
					value={resetEmail}
					autofocus
					onchange={(value) => (resetEmail = value)}
				/>
				{#if error}<p class="error" role="alert">{error}</p>{/if}
				<Button type="submit" variant="highlighted" size="lg" block {busy}>
					{t.auth.sendReset}
				</Button>
			{/if}
			<Button variant="ghost" size="sm" onclick={() => (forgetting = false)}>
				{t.auth.backToSignIn}
			</Button>
		</form>
	{:else if ready}
		<Auth
			bind:mode
			{registration}
			{instance}
			{error}
			{busy}
			onsubmit={submit}
			onforgot={() => {
				error = null;
				resetSent = false;
				forgetting = true;
			}}
		/>
	{/if}
</main>

<style>
	.card {
		display: flex;
		flex-direction: column;
		gap: 14px;
		width: min(360px, 100%);
		margin: 0 auto;
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

	.login {
		display: grid;
		place-items: center;
		min-height: 100vh;
		min-height: 100dvh;
		padding: 24px;
		background: var(--ground);
	}
</style>
