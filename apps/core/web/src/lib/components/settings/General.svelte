<script lang="ts">
	/**
	 * This browser and this machine: appearance, language, time zone, notifications, and where
	 * Hera lives. None of it changes how she behaves — that is what the rest of Settings is for.
	 *
	 * Every row here is a fact about *you*, so the search field filters by section rather than
	 * by content: a section is shown when its heading, or the words that describe it, match.
	 */
	import { api, type Health, type Preferences } from '$lib/api/client';
	import Checkbox from '$lib/components/Checkbox.svelte';
	import Select from '$lib/components/Select.svelte';
	import { t } from '$lib/i18n';
	import { notifications } from '$lib/notifications.svelte';
	import { theme, type Appearance } from '$lib/theme.svelte';
	import { zoneChoices } from '$lib/timezones';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	const APPEARANCES: Array<{ id: Appearance; label: string }> = [
		{ id: 'system', label: t.settings.system },
		{ id: 'light', label: t.settings.light },
		{ id: 'dark', label: t.settings.dark }
	];

	const LANGUAGES = [{ value: 'en', label: t.general.english }];

	let health = $state<Health | null>(null);
	let preferences = $state<Preferences | null>(null);

	$effect(() => {
		void api
			.health()
			.then((found) => (health = found))
			.catch(() => undefined);
		void api
			.preferences()
			.then((found) => (preferences = found))
			.catch(() => undefined);
	});

	async function setZone(timezone: string) {
		try {
			preferences = await api.setTimezone(timezone);
		} catch {
			/* the note under the control still shows what is actually stored */
		}
	}

	const shows = (...words: string[]) =>
		!filter || words.some((word) => word.toLowerCase().includes(filter));

	const showAppearance = $derived(
		shows(t.profileMenu.appearance, t.settings.system, t.settings.light, t.settings.dark)
	);
	const showLanguage = $derived(shows(t.general.language, t.general.languageNote));
	const showZone = $derived(shows(t.profileMenu.timezone, t.general.timezoneNote));
	const showNotify = $derived(shows(t.notifications.heading, t.notifications.toggle));
	const showAbout = $derived(
		shows(t.general.aboutHeading, t.general.version, t.general.dataFolder)
	);
</script>

{#if showAppearance}
	<section>
		<h3>{t.profileMenu.appearance}</h3>
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
{/if}

{#if showLanguage}
	<section>
		<h3>{t.general.language}</h3>
		<div class="control">
			<Select choices={LANGUAGES} value="en" label={t.general.language} />
		</div>
		<p class="caption">{t.general.languageNote}</p>
	</section>
{/if}

{#if showZone}
	<section>
		<h3>{t.profileMenu.timezone}</h3>
		<div class="control">
			<Select
				choices={zoneChoices}
				value={preferences?.timezone ?? ''}
				label={t.profileMenu.timezone}
				onchange={setZone}
			/>
		</div>
		<p class="caption">{t.general.timezoneNote}</p>
		<p class="caption">{preferences ? preferences.now : t.profileMenu.checking}</p>
	</section>
{/if}

{#if showNotify}
	<section>
		<h3>{t.notifications.heading}</h3>
		<Checkbox
			checked={notifications.enabled}
			label={t.notifications.toggle}
			disabled={notifications.permission === 'denied' || notifications.permission === 'unsupported'}
			onchange={(on) => notifications.set(on)}
		/>
		{#if notifications.permission === 'denied'}
			<p class="caption problem">{t.notifications.denied}</p>
		{:else if notifications.permission === 'unsupported'}
			<p class="caption problem">{t.notifications.unsupported}</p>
		{/if}
	</section>
{/if}

{#if showAbout}
	<section>
		<h3>{t.general.aboutHeading}</h3>
		{#if health}
			<dl>
				<dt>{t.general.version}</dt>
				<dd>{t.settings.version(health.version)}</dd>
				<dt>{t.general.dataFolder}</dt>
				<dd class="mono">{health.home}</dd>
				<dt>{t.general.model}</dt>
				<dd>{health.model}</dd>
			</dl>
		{:else}
			<p class="caption">{t.profileMenu.checking}</p>
		{/if}
	</section>
{/if}

{#if !(showAppearance || showLanguage || showZone || showNotify || showAbout)}
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

	.control {
		max-width: 320px;
	}

	.segments {
		display: inline-flex;
		gap: 2px;
		padding: 3px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
	}

	.segment {
		min-width: 84px;
		padding: 5px 12px;
		border-radius: 6px;
		font-size: 13px;
		color: var(--text-muted);
	}

	.segment.active {
		background: var(--surface-raised);
		color: var(--text);
	}

	dl {
		display: grid;
		grid-template-columns: max-content 1fr;
		gap: 6px 18px;
		margin: 0;
		font-size: 13.5px;
	}

	dt {
		color: var(--text-muted);
	}

	dd {
		margin: 0;
		overflow-wrap: anywhere;
	}

	.problem {
		color: var(--danger);
	}

	.empty {
		margin: 18px 0;
		font-family: var(--font-body);
		font-size: 15px;
		color: var(--text-muted);
	}
</style>
