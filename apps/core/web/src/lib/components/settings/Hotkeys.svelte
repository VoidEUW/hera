<script lang="ts">
	/**
	 * Every chord and the control it mirrors (#112), read straight from the keymap so the list
	 * cannot drift from what is bound. Read only for now: the data is already `{ id, default,
	 * current }`, which is the shape rebinding needs, so a person's own choices are a control on
	 * this screen later rather than a rewrite.
	 */
	import Kbd from '$lib/components/ui/Kbd.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';
	import { t } from '$lib/i18n';
	import { BINDINGS, keys } from '$lib/keys';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	const GROUPS = [
		{ id: 'global', label: t.hotkeys.global },
		{ id: 'chat', label: t.hotkeys.chat }
	] as const;

	const rows = (group: string) =>
		BINDINGS.filter(
			(binding) =>
				binding.group === group &&
				(!filter ||
					`${binding.label} ${binding.control} ${keys.label(binding.id)}`
						.toLowerCase()
						.includes(filter))
		);

	const none = $derived(GROUPS.every((group) => rows(group.id).length === 0));
</script>

<p class="caption intro">{t.hotkeys.intro}</p>

{#each GROUPS as group (group.id)}
	{#if rows(group.id).length}
		<section>
			<h3>{group.label}</h3>
			<ul>
				{#each rows(group.id) as binding (binding.id)}
					<li>
						<div class="what">
							<span>{binding.label}</span>
							<span class="caption">{t.hotkeys.mirrors(binding.control)}</span>
						</div>
						{#if binding.planned}<Pill>{t.hotkeys.planned}</Pill>{/if}
						<Kbd>{keys.label(binding.id)}</Kbd>
					</li>
				{/each}
			</ul>
		</section>
	{/if}
{/each}

{#if none}
	<p class="empty">{t.settings.noMatch}</p>
{/if}

<style>
	.intro {
		margin: 14px 0 0;
	}

	section {
		padding: 14px 0;
		border-bottom: 1px solid var(--line);
	}

	h3 {
		margin: 0 0 6px;
		font-size: 14px;
		font-weight: 500;
	}

	ul {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	li {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 8px 0;
	}

	.what {
		display: flex;
		flex: 1;
		flex-direction: column;
		gap: 1px;
		min-width: 0;
		font-size: 13.5px;
	}

	.caption {
		margin: 0;
	}

	.empty {
		margin: 18px 0;
		font-family: var(--font-body);
		font-size: 15px;
		color: var(--text-muted);
	}
</style>
