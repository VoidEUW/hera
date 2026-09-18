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
	import Modal from './Modal.svelte';

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
</script>

<Modal
	label={t.skills.title}
	title={t.skills.title}
	caption={t.skills.blurb}
	placement="docked"
	width="min(520px, 92vw)"
	{onclose}
>
	<label class="search">
		<span class="sr-only">{t.skills.search}</span>
		<input type="search" bind:value={query} placeholder={t.skills.search} />
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
</Modal>

<style>
	/* The Modal draws the frame and the header; this sheet owns the padding of its own body. */
	:global(.sheet.docked) {
		padding: 0 18px 16px;
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

	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip-path: inset(50%);
		white-space: nowrap;
		border: 0;
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
