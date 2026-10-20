<script lang="ts">
	/**
	 * Which model she answers with (the theme's composer model selector): a chip with the cube and
	 * the model's name, opening upward into the shared menu — one heading per endpoint, each model
	 * with its id and host under its name, the brass check on the one in use.
	 *
	 * Global, not per chat: it is the active endpoint and model, the same thing Settings → Models
	 * activates. With nothing registered it says so where the model belongs, one click from the
	 * screen that fixes it.
	 *
	 * `${provider}::${model}` is safe to split on the first `::`: a provider name is restricted to
	 * [a-z0-9_-] (`validate_provider_name`), so it can never contain `::`, while a model id could.
	 */
	import type { Provider } from '$lib/api/client';
	import { t } from '$lib/i18n';
	import Button from './ui/Button.svelte';
	import Selector, { type Choice } from './ui/Selector.svelte';

	interface Props {
		providers: Provider[];
		activeProvider: string;
		onmodel: (providerName: string, modelId: string) => void;
		onsettings: () => void;
	}

	let { providers, activeProvider, onmodel, onsettings }: Props = $props();

	function host(url: string): string {
		try {
			return new URL(url).host;
		} catch {
			return url;
		}
	}

	const choices = $derived<Choice[]>(
		providers.flatMap((entry) =>
			entry.models.map((model) => ({
				value: `${entry.name}::${model.id}`,
				label: model.name,
				description: `${model.id} · ${host(entry.base_url)}`,
				group: entry.name,
				icon: 'cube' as const
			}))
		)
	);

	const active = $derived.by(() => {
		const entry = providers.find((provider) => provider.name === activeProvider);
		return entry?.active_model ? `${entry.name}::${entry.active_model}` : '';
	});

	function choose(value: string) {
		const at = value.indexOf('::');
		onmodel(value.slice(0, at), value.slice(at + 2));
	}
</script>

{#if choices.length}
	<Selector
		look="chip"
		icon="cube"
		{choices}
		value={active}
		label={t.composer.model}
		placement="above"
		align="end"
		onchange={choose}
	/>
{:else}
	<Button variant="ghost" size="sm" icon="cube" onclick={onsettings}>{t.composer.noModel}</Button>
{/if}
