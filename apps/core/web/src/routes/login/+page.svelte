<script lang="ts">
	/**
	 * Signing in, or registering where this Hera takes registrations (ADR 27).
	 *
	 * Drawn without the rail. Arriving here already signed in goes straight on; arriving at an
	 * instance nobody has claimed goes to the wizard instead. On success the page is **reloaded**
	 * at where you were going rather than navigated to: every store in the shell was built for
	 * nobody, and a reload is the one way to be sure none of them still is.
	 */
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { api, type Registration } from '$lib/api/client';
	import Auth from '$lib/components/ui/Auth.svelte';
	import { safeNext } from '$lib/errors';
	import { t } from '$lib/i18n';

	const invite = page.url.searchParams.get('invite') ?? '';
	const next = safeNext(page.url.searchParams.get('next'));

	let mode = $state<'in' | 'up'>(invite ? 'up' : 'in');
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
			if (registration === 'closed') mode = 'in';
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		}
		ready = true;
	})();

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
					password: details.password,
					invite
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
	{#if ready}
		<Auth bind:mode {registration} {instance} {error} {busy} onsubmit={submit} />
	{/if}
</main>

<style>
	.login {
		display: grid;
		place-items: center;
		min-height: 100vh;
		min-height: 100dvh;
		padding: 24px;
		background: var(--ground);
	}
</style>
