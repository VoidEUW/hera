<script lang="ts">
	/**
	 * Settings → Admin → Instance: the name this Hera greets people with, the address it is
	 * reached at, and who may join — the wizard's second step, kept here for afterwards. All three
	 * live in `[instance]` in `config.toml`.
	 */
	import { api, type Registration } from '$lib/api/client';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import { t } from '$lib/i18n';
	import { Placeholder } from '$lib/loading.svelte';
	import LoadFailed from './LoadFailed.svelte';
	import Rows from './Rows.svelte';

	let name = $state('');
	let publicUrl = $state('');
	let registration = $state<Registration>('closed');
	let suggested = $state('');
	let failed = $state<unknown>(null);
	let error = $state<string | null>(null);
	let saved = $state(false);

	const settling = new Placeholder(true);
	$effect(() => () => settling.stop());

	async function load() {
		failed = null;
		settling.set(true);
		try {
			const instance = await api.instance();
			name = instance.name;
			publicUrl = instance.public_url;
			registration = instance.registration;
			suggested = instance.suggested_url;
		} catch (cause) {
			failed = cause;
		} finally {
			settling.set(false);
		}
	}
	void load();

	async function save() {
		error = null;
		try {
			await api.updateInstance({
				name: name.trim() || 'Hera',
				public_url: publicUrl.trim(),
				registration
			});
			saved = true;
			setTimeout(() => (saved = false), 1600);
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		}
	}
</script>

{#if settling.shown}
	<Rows label={t.settings.loading} rows={3} />
{:else if failed !== null}
	<LoadFailed cause={failed} what={t.loadFailed.what.instance} onretry={load} />
{:else}
	<form
		onsubmit={(event) => {
			event.preventDefault();
			void save();
		}}
	>
		<Input label={t.setup.instanceName} value={name} onchange={(value) => (name = value)} />
		<Input
			kind="url"
			mono
			label={t.setup.publicUrl}
			help={t.setup.publicUrlHelp}
			placeholder={suggested || 'https://hera.example.com'}
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
			<p class="caption">{t.setup.registrationHelp}</p>
		</div>
		{#if error}<p class="error" role="alert">{error}</p>{/if}
		<div class="foot">
			<Button type="submit" variant="highlighted">{t.settings.save}</Button>
			{#if saved}<Pill tone="live">{t.account.saved}</Pill>{/if}
		</div>
	</form>
{/if}

<style>
	form {
		display: flex;
		flex-direction: column;
		gap: 14px;
		max-width: 480px;
		padding: 14px 0;
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

	.foot {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	.error {
		margin: 0;
		color: var(--danger);
		font-size: 13px;
	}
</style>
