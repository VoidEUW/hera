<script lang="ts">
	/**
	 * Which skills are switched on for this conversation.
	 *
	 * ADR 5 says the *model* is never asked which skill applies — selection is code. This is the
	 * other half of that sentence: when code guesses wrong, a person needs somewhere to say
	 * *use this one*, and until now the only answers were a `/slash` on every message or editing
	 * a profile two screens away.
	 *
	 * A pin here outranks the profile's and the project's, because it is the most specific and
	 * the most recent thing anybody said about this conversation. It is not a filter: retrieval
	 * still runs and can still add more.
	 */
	import { untrack } from 'svelte';
	import { api, type Skill } from '$lib/api/client';
	import { t } from '$lib/i18n';

	interface Props {
		/** The names currently pinned to this chat. */
		pinned: string[];
		onclose: () => void;
		onpick: (names: string[]) => void;
	}

	let { pinned, onclose, onpick }: Props = $props();

	let skills = $state<Skill[]>([]);
	let query = $state('');
	let error = $state<string | null>(null);
	// Seeded from the prop and then owned here: the dialog is short-lived and the chat's list
	// is being written from inside it, so following the prop afterwards would fight the
	// optimistic update it just caused.
	let chosen = $state<string[]>(untrack(() => [...pinned]));

	const filter = $derived(query.trim().toLowerCase());
	const shown = $derived(
		skills.filter(
			(skill) => !filter || `${skill.id} ${skill.description}`.toLowerCase().includes(filter)
		)
	);

	$effect(() => {
		void load();
	});

	async function load() {
		try {
			skills = (await api.skills()).skills;
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		}
	}

	function toggle(id: string) {
		chosen = chosen.includes(id) ? chosen.filter((name) => name !== id) : [...chosen, id];
		// Applied as it is clicked rather than behind a Save: this is a set of switches, and a
		// switch that needs confirming is a switch you have to remember you flipped.
		onpick(chosen);
	}

	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') onclose();
	}

	/** The dialog exists to be typed into, so the cursor starts in the field. */
	function takeover(node: HTMLInputElement) {
		node.focus();
	}
</script>

<svelte:window {onkeydown} />

<div
	class="scrim"
	role="button"
	tabindex="-1"
	aria-label={t.skills.close}
	onclick={onclose}
	onkeydown={(event) => event.key === 'Enter' && onclose()}
></div>

<div class="sheet" role="dialog" aria-modal="true" aria-label={t.skills.title}>
	<header>
		<div>
			<h2 class="display">{t.skills.title}</h2>
			<p class="caption">{t.skills.blurb}</p>
		</div>
		<button class="close" type="button" onclick={onclose}>
			<span class="sr-only">{t.skills.close}</span>
			<span aria-hidden="true">✕</span>
		</button>
	</header>

	<label class="search">
		<span class="sr-only">{t.skills.search}</span>
		<input type="search" use:takeover bind:value={query} placeholder={t.skills.search} />
	</label>

	{#if error}<p class="problem caption">{error}</p>{/if}

	<ul class="list">
		{#each shown as skill (skill.id)}
			{@const on = chosen.includes(skill.id)}
			<li>
				<button
					class="entry"
					class:on
					type="button"
					aria-pressed={on}
					onclick={() => toggle(skill.id)}
				>
					<span class="mark" aria-hidden="true">{on ? '✓' : ''}</span>
					<span class="what">
						<span class="id">{skill.id}</span>
						<span class="caption about">{skill.description || t.skills.nothing}</span>
					</span>
				</button>
			</li>
		{:else}
			<li class="empty caption">{filter ? t.settings.noMatch : t.settings.noSkills}</li>
		{/each}
	</ul>
</div>

<style>
	.scrim {
		position: fixed;
		inset: 0;
		background: rgb(0 0 0 / 0.45);
		border: 0;
		animation: fade var(--fade) var(--ease);
		z-index: 10;
	}

	.sheet {
		position: fixed;
		inset: auto 50% 96px auto;
		transform: translateX(50%);
		width: min(520px, 92vw);
		max-height: 60vh;
		display: flex;
		flex-direction: column;
		padding: 16px 18px;
		background: var(--surface-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow);
		z-index: 11;
		animation: fade var(--fade) var(--ease);
	}

	@keyframes fade {
		from {
			opacity: 0;
		}
	}

	header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 16px;
	}

	h2 {
		margin: 0;
		font-size: 18px;
	}

	header .caption {
		margin: 2px 0 0;
		max-width: 46ch;
	}

	.close {
		color: var(--text-muted);
	}

	.search input {
		width: 100%;
		margin: 12px 0 8px;
		padding: 7px 10px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 13px;
	}

	.list {
		list-style: none;
		margin: 0;
		padding: 0;
		overflow-y: auto;
	}

	.entry {
		display: flex;
		align-items: flex-start;
		gap: 10px;
		width: 100%;
		padding: 8px;
		border-radius: var(--radius);
		text-align: left;
		transition: background var(--fade) var(--ease);
	}

	.entry:hover {
		background: var(--surface);
	}

	.mark {
		width: 16px;
		flex: none;
		padding-top: 1px;
		color: var(--brass);
		font-size: 12px;
	}

	.what {
		min-width: 0;
	}

	.id {
		display: block;
		font-size: 13.5px;
		color: var(--text-muted);
	}

	.on .id {
		color: var(--brass);
	}

	.about {
		display: block;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.problem {
		color: var(--danger);
	}

	.empty {
		padding: 12px 8px;
		color: var(--text-muted);
	}
</style>
