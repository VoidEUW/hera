<script lang="ts">
	/**
	 * The sign-in surface (the theme's `hera/auth`, soft look): a centred rounded card with the
	 * mark, a switch between signing in and registering, the fields, the highlighted primary
	 * action — and a passkey as the other way in, where one can work at all (M4). Signing in
	 * only: an account is made with a password, and a passkey is added to it afterwards.
	 *
	 * Drawn on `/login`. The switch appears only when anybody may register; a card offering a tab
	 * that answers *registration is closed* is a door painted on a wall. By invitation, the link
	 * somebody was sent is the way in, and the card says so.
	 */
	import { t } from '$lib/i18n';
	import Button from './Button.svelte';
	import Input from './Input.svelte';
	import Ocellus from './Ocellus.svelte';
	import Segmented from './Segmented.svelte';

	interface Props {
		mode?: 'in' | 'up';
		/** Whether the *register* tab is offered at all. */
		registration?: 'open' | 'invite' | 'closed';
		/** What this Hera calls itself, for the title. */
		instance?: string;
		/** Said under the fields when the last attempt failed — the server's own sentence. */
		error?: string | null;
		busy?: boolean;
		onsubmit?: (details: {
			mode: 'in' | 'up';
			name: string;
			email: string;
			password: string;
		}) => void;
		/** Draws the passkey button under the sign-in form. Absent where WebAuthn cannot work. */
		onpasskey?: () => void;
		/** Draws *forgot your password?* under the sign-in form. */
		onforgot?: () => void;
	}

	let {
		mode = $bindable('in'),
		registration = 'closed',
		instance = 'Hera',
		error = null,
		busy = false,
		onsubmit,
		onpasskey,
		onforgot
	}: Props = $props();

	let name = $state('');
	let email = $state('');
	let password = $state('');
	const registering = $derived(mode === 'up' && registration === 'open');
	const blurb = $derived(registering ? t.auth.registerBlurb : t.auth.signInBlurb);
</script>

<form
	class="auth"
	onsubmit={(event) => {
		event.preventDefault();
		if (!busy) onsubmit?.({ mode, name, email, password });
	}}
>
	<div class="head">
		<Ocellus size={30} />
		<h3>{registering ? t.auth.registerTitle : t.auth.signInTitle(instance)}</h3>
		<p>{blurb}</p>
	</div>
	{#if registration === 'open'}
		<Segmented
			size="sm"
			label={t.auth.mode}
			bind:value={mode}
			options={[
				{ value: 'in', label: t.auth.signIn },
				{ value: 'up', label: t.auth.register }
			]}
		/>
	{/if}
	{#if registering}
		<Input label={t.auth.name} value={name} onchange={(value) => (name = value)} />
	{/if}
	<Input
		kind="email"
		label={t.auth.email}
		placeholder="you@example.com"
		value={email}
		autofocus
		onchange={(value) => (email = value)}
	/>
	<Input
		kind="password"
		label={t.auth.password}
		placeholder={registering ? t.auth.passwordPlaceholder : ''}
		value={password}
		onchange={(value) => (password = value)}
	/>
	{#if error}
		<p class="error" role="alert">{error}</p>
	{/if}
	<Button type="submit" variant="highlighted" size="lg" block {busy}>
		{registering ? t.auth.create : t.auth.continue}
	</Button>
	{#if onpasskey && !registering}
		<div class="or">{t.auth.or}</div>
		<Button size="lg" block icon="key" disabled={busy} onclick={() => onpasskey?.()}>
			{t.auth.signInPasskey}
		</Button>
	{/if}
	{#if onforgot && !registering}
		<Button variant="ghost" size="sm" onclick={onforgot}>{t.auth.forgot}</Button>
	{/if}
	{#if registration === 'closed'}
		<p class="note">{t.auth.closedNote}</p>
	{:else if registration === 'invite'}
		<p class="note">{t.auth.inviteNote}</p>
	{/if}
</form>

<style>
	.auth {
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

	.auth > :global(.segmented) {
		width: 100%;
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

	.note {
		color: var(--text-faint);
		text-align: center;
	}

	.or {
		display: flex;
		align-items: center;
		gap: 10px;
		color: var(--text-faint);
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}

	.or::before,
	.or::after {
		content: '';
		flex: 1;
		height: var(--border-width);
		background: var(--line);
	}
</style>
