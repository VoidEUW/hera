<script lang="ts">
	/**
	 * The sign-in surface Settings › Account is waiting for (the theme's `hera/auth`, soft look):
	 * a centred rounded card with the mark, a switch between signing in and registering, an email
	 * field, the highlighted primary action, and a passkey as the other way in.
	 *
	 * Built and on `/design`; Hera has no accounts to sign in to yet.
	 */
	import { t } from '$lib/i18n';
	import Button from './Button.svelte';
	import Input from './Input.svelte';
	import Ocellus from './Ocellus.svelte';
	import Segmented from './Segmented.svelte';

	interface Props {
		mode?: 'in' | 'up';
		onsubmit?: (details: {
			mode: 'in' | 'up';
			name: string;
			email: string;
			password: string;
		}) => void;
		onpasskey?: (mode: 'in' | 'up') => void;
	}

	let { mode = $bindable('in'), onsubmit, onpasskey }: Props = $props();

	let name = $state('');
	let email = $state('');
	let password = $state('');
	const registering = $derived(mode === 'up');
</script>

<form
	class="auth"
	onsubmit={(event) => {
		event.preventDefault();
		onsubmit?.({ mode, name, email, password });
	}}
>
	<div class="head">
		<Ocellus size={30} />
		<h3>{registering ? t.auth.registerTitle : t.auth.signInTitle}</h3>
		<p>{registering ? t.auth.registerBlurb : t.auth.signInBlurb}</p>
	</div>
	<Segmented
		size="sm"
		label={t.auth.mode}
		bind:value={mode}
		options={[
			{ value: 'in', label: t.auth.signIn },
			{ value: 'up', label: t.auth.register }
		]}
	/>
	{#if registering}
		<Input label={t.auth.name} value={name} onchange={(value) => (name = value)} />
	{/if}
	<Input
		kind="email"
		label={t.auth.email}
		placeholder="you@example.com"
		value={email}
		onchange={(value) => (email = value)}
	/>
	{#if registering}
		<Input
			kind="password"
			label={t.auth.password}
			placeholder={t.auth.passwordPlaceholder}
			help={t.auth.passwordHelp}
			value={password}
			onchange={(value) => (password = value)}
		/>
	{/if}
	<Button type="submit" variant="highlighted" size="lg" block>
		{registering ? t.auth.create : t.auth.continue}
	</Button>
	<div class="or">{t.auth.or}</div>
	<Button size="lg" block icon="key" onclick={() => onpasskey?.(mode)}>
		{registering ? t.auth.registerPasskey : t.auth.signInPasskey}
	</Button>
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
