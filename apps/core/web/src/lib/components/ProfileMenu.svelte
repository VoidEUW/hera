<script lang="ts">
	/**
	 * The other half of settings: **you and this machine**.
	 *
	 * Appearance, which of her is answering, and where your data lives. None of it changes how
	 * she behaves — that is what the Settings modal is for — and mixing the two is how a person
	 * ends up scrolling past six model fields to find a light-mode toggle.
	 *
	 * A popover above the profile card rather than a second modal. It is four controls; opening
	 * a sheet over the conversation to change the theme would be a heavier gesture than the
	 * thing deserves.
	 */
	import { api, type Health, type Profile } from '$lib/api/client';
	import { t } from '$lib/i18n';
	import { theme, type Appearance } from '$lib/theme.svelte';

	interface Props {
		profiles: Profile[];
		onclose?: () => void;
		onprofiles?: (profiles: Profile[]) => void;
	}

	let { profiles, onclose, onprofiles }: Props = $props();

	const APPEARANCES: Array<{ id: Appearance; label: string }> = [
		{ id: 'system', label: t.settings.system },
		{ id: 'light', label: t.settings.light },
		{ id: 'dark', label: t.settings.dark }
	];

	let health = $state<Health | null>(null);

	$effect(() => {
		void api
			.health()
			.then((found) => (health = found))
			.catch(() => undefined);
	});

	async function makeDefault(profile: Profile) {
		try {
			await api.makeDefaultProfile(profile.id);
			onprofiles?.(await api.profiles());
		} catch {
			/* the menu is not the place to explain a failed write; Settings is */
		}
	}

	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') onclose?.();
	}
</script>

<svelte:window {onkeydown} />

<div
	class="scrim"
	role="button"
	tabindex="-1"
	aria-label={t.settings.close}
	onclick={() => onclose?.()}
	onkeydown={(event) => event.key === 'Enter' && onclose?.()}
></div>

<div class="menu" role="dialog" aria-modal="true" aria-label={t.profileMenu.open}>
	<section>
		<p class="heading">{t.profileMenu.appearance}</p>
		<div class="segments">
			{#each APPEARANCES as option (option.id)}
				<button
					class="segment"
					class:active={theme.appearance === option.id}
					type="button"
					onclick={() => theme.set(option.id)}
				>
					{option.label}
				</button>
			{/each}
		</div>
	</section>

	{#if profiles.length}
		<section>
			<p class="heading">{t.profileMenu.profiles}</p>
			{#each profiles as profile (profile.id)}
				<button
					class="row"
					type="button"
					disabled={profile.is_default}
					onclick={() => makeDefault(profile)}
				>
					<span class="name">{profile.name}</span>
					<span class="trail">
						{profile.is_default ? t.models.active : t.profileMenu.makeDefault}
					</span>
				</button>
			{/each}
		</section>
	{/if}

	<section>
		<p class="heading">{t.profileMenu.language}</p>
		<p class="note">{t.profileMenu.languageOnly}</p>
	</section>

	<!-- The heading is here before the answer is. `health` is one round trip away, and hiding
	     the whole section until it lands made the menu grow under the pointer — and made a test
	     that reads it fail whenever the request was slower than the click. -->
	<section class="about">
		<p class="heading">{t.profileMenu.about}</p>
		{#if health}
			<p class="note">{t.profileMenu.version(health.version)}</p>
			<p class="note mono path">{t.profileMenu.dataIn} {health.home}</p>
			<p class="note">{health.model}</p>
		{:else}
			<p class="note">{t.profileMenu.checking}</p>
		{/if}
	</section>
</div>

<style>
	.scrim {
		position: fixed;
		inset: 0;
		border: 0;
		background: none;
		z-index: 10;
	}

	.menu {
		position: fixed;
		left: 12px;
		bottom: 76px;
		width: 288px;
		max-height: 70vh;
		overflow-y: auto;
		padding: 6px;
		background: var(--surface-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow);
		z-index: 11;
		animation: rise var(--fade) var(--ease);
	}

	@keyframes rise {
		from {
			opacity: 0;
			transform: translateY(4px);
		}
	}

	section {
		padding: 8px 8px 10px;
		border-bottom: 1px solid var(--line);
	}

	section:last-child {
		border-bottom: 0;
	}

	.heading {
		margin: 0 0 6px;
		font-size: 11px;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: var(--text-faint);
	}

	.segments {
		display: flex;
		gap: 2px;
		padding: 3px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}

	.segment {
		flex: 1;
		padding: 5px 0;
		border-radius: 6px;
		font-size: 12.5px;
		color: var(--text-muted);
	}

	.segment.active {
		background: var(--surface-raised);
		color: var(--text);
	}

	.row {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 10px;
		width: 100%;
		padding: 5px 6px;
		border-radius: var(--radius);
		font-size: 13.5px;
		color: var(--text-muted);
	}

	.row:not(:disabled):hover {
		background: var(--surface);
		color: var(--text);
	}

	.row:disabled {
		cursor: default;
	}

	.row:disabled .trail {
		color: var(--pomegranate);
	}

	.trail {
		font-size: 11.5px;
		color: var(--text-faint);
	}

	.note {
		margin: 0 0 2px;
		font-size: 12.5px;
		color: var(--text-muted);
	}

	.path {
		font-size: 11.5px;
		overflow-wrap: anywhere;
		color: var(--text-faint);
	}
</style>
