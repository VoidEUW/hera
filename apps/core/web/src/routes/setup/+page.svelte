<script lang="ts">
	/**
	 * The first start: claiming an instance nobody can sign in to yet (ADR 27).
	 *
	 * Four steps, and only the first is special. It makes the admin — with the setup code from the
	 * server's log, unless this browser is on the machine Hera runs on — and signs this browser in
	 * as them. From then on the wizard is an admin using the ordinary screens: the instance's own
	 * route, then the Models screen itself, probe and all. So the model step is skippable and so
	 * is everything after it; Settings has the same controls.
	 *
	 * Mail is not here yet (M3).
	 */
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { api, type Registration, type SetupState } from '$lib/api/client';
	import Models from '$lib/components/settings/Models.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Ocellus from '$lib/components/ui/Ocellus.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import { t } from '$lib/i18n';

	type Step = 'admin' | 'instance' | 'model' | 'done';
	const STEPS: Step[] = ['admin', 'instance', 'model', 'done'];

	/** Handed over by the desktop app that started this server, in place of a setup code. */
	const launchToken = page.url.searchParams.get('launch') ?? '';

	let step = $state<Step>('admin');
	let known = $state<SetupState | null>(null);
	let error = $state<string | null>(null);
	let busy = $state(false);

	let name = $state('');
	let email = $state('');
	let password = $state('');
	let code = $state('');

	let instanceName = $state('Hera');
	let publicUrl = $state(window.location.origin);
	let registration = $state<Registration>('closed');

	void (async () => {
		try {
			known = await api.setupState();
			if (!known.required) await goto(resolve('/login'));
		} catch (cause) {
			error = message(cause);
		}
	})();

	function message(cause: unknown): string {
		return cause instanceof Error ? cause.message : String(cause);
	}

	async function run(work: () => Promise<void>) {
		busy = true;
		error = null;
		try {
			await work();
		} catch (cause) {
			error = message(cause);
		} finally {
			busy = false;
		}
	}

	const claim = () =>
		run(async () => {
			await api.setup({ name, email, password, code, launch_token: launchToken });
			const instance = await api.instance();
			instanceName = instance.name;
			if (instance.public_url) publicUrl = instance.public_url;
			registration = instance.registration;
			step = 'instance';
		});

	const describe = () =>
		run(async () => {
			await api.updateInstance({
				name: instanceName.trim() || 'Hera',
				public_url: publicUrl.trim(),
				registration
			});
			step = 'model';
		});
</script>

<svelte:head><title>{t.setup.title}</title></svelte:head>

<main class="setup">
	<div class="card">
		<div class="head">
			<Ocellus size={30} />
			<h2>{t.setup.title}</h2>
			<ol class="steps" aria-label={t.setup.title}>
				{#each STEPS as each (each)}
					<li class:current={each === step} aria-current={each === step ? 'step' : undefined}>
						{t.setup.steps[each]}
					</li>
				{/each}
			</ol>
		</div>

		{#if step === 'admin'}
			<form
				onsubmit={(event) => {
					event.preventDefault();
					void claim();
				}}
			>
				<h3>{t.setup.adminTitle}</h3>
				<p>{t.setup.adminBlurb}</p>
				{#if known && known.chats > 0}<p class="note">{t.setup.adopted(known.chats)}</p>{/if}
				<Input label={t.auth.name} value={name} autofocus onchange={(value) => (name = value)} />
				<Input
					kind="email"
					label={t.auth.email}
					placeholder="you@example.com"
					value={email}
					onchange={(value) => (email = value)}
				/>
				<Input
					kind="password"
					label={t.auth.password}
					placeholder={t.auth.passwordPlaceholder}
					value={password}
					onchange={(value) => (password = value)}
				/>
				{#if known?.code_required && !launchToken}
					<Input
						label={t.setup.code}
						help={t.setup.codeHelp}
						mono
						placeholder="XXXX-XXXX-XXXX"
						value={code}
						onchange={(value) => (code = value)}
					/>
				{/if}
				{#if error}<p class="error" role="alert">{error}</p>{/if}
				<Button type="submit" variant="highlighted" size="lg" block {busy}>{t.setup.next}</Button>
			</form>
		{:else if step === 'instance'}
			<form
				onsubmit={(event) => {
					event.preventDefault();
					void describe();
				}}
			>
				<h3>{t.setup.instanceTitle}</h3>
				<Input
					label={t.setup.instanceName}
					value={instanceName}
					onchange={(value) => (instanceName = value)}
				/>
				<Input
					kind="url"
					mono
					label={t.setup.publicUrl}
					help={t.setup.publicUrlHelp}
					value={publicUrl}
					onchange={(value) => (publicUrl = value)}
				/>
				<div class="group">
					<span class="label">{t.setup.registration}</span>
					<Segmented
						size="sm"
						label={t.setup.registration}
						bind:value={registration}
						options={[
							{ value: 'closed', label: t.setup.registrationClosed },
							{ value: 'invite', label: t.setup.registrationInvite },
							{ value: 'open', label: t.setup.registrationOpen }
						]}
					/>
					<p>{t.setup.registrationHelp}</p>
				</div>
				{#if error}<p class="error" role="alert">{error}</p>{/if}
				<Button type="submit" variant="highlighted" size="lg" block {busy}>{t.setup.next}</Button>
			</form>
		{:else if step === 'model'}
			<h3>{t.setup.modelTitle}</h3>
			<p>{t.setup.modelBlurb}</p>
			<div class="models"><Models /></div>
			<div class="row">
				<Button variant="ghost" onclick={() => (step = 'done')}>{t.setup.skip}</Button>
				<Button variant="highlighted" onclick={() => (step = 'done')}>{t.setup.next}</Button>
			</div>
		{:else}
			<h3>{t.setup.doneTitle}</h3>
			<p>{t.setup.doneBlurb}</p>
			<Button variant="highlighted" size="lg" block onclick={() => window.location.assign('/')}>
				{t.setup.open}
			</Button>
		{/if}
	</div>
</main>

<style>
	.setup {
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
		width: min(560px, 100%);
		padding: 24px;
		border: var(--border-width) solid var(--line);
		border-radius: var(--radius-lg);
		background: var(--surface);
	}

	.head {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 8px;
	}

	h2 {
		margin: 0;
		font-family: var(--font-display);
		font-size: 22px;
		font-weight: var(--display-weight);
	}

	h3 {
		margin: 0;
		font-size: 15px;
		font-weight: 500;
	}

	form {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	p {
		margin: 0;
		color: var(--text-muted);
		font-size: 12.5px;
	}

	.note {
		color: var(--text);
	}

	.error {
		color: var(--danger);
		font-size: 13px;
	}

	.steps {
		display: flex;
		gap: 14px;
		margin: 0;
		padding: 0;
		list-style: none;
		color: var(--text-faint);
		font-size: 12px;
	}

	.steps .current {
		color: var(--text);
	}

	.group {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.label {
		font-size: 12.5px;
		color: var(--text-muted);
	}

	.models {
		max-height: 50vh;
		overflow: auto;
	}

	.row {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
	}
</style>
