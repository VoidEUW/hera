<script lang="ts">
	/**
	 * A small editor for one skill's `SKILL.md` — and the way to add and delete one.
	 *
	 * Only what editing needs: the file as it is on disk in a text area, Save, Cancel. The
	 * frontmatter and the instructions are one document because that is what the file is, and a
	 * second form beside it would be a second description of the same thing. Saving writes the
	 * file and reads it back through the loader, so a typo comes back as the skill's `problems`
	 * — shown here, with the editor left open to fix it — instead of the skill going missing.
	 *
	 * With no `skill` it is the *new* skill form: the same text area, preloaded with a template,
	 * and an id field above it, because the id is the folder and the `/command`. Once created it
	 * carries on as an editor for the skill it just made.
	 *
	 * Delete lives here and nowhere else, one step behind Edit and in red, and asks again before
	 * it removes the folder: of everything on this screen it is the one thing that cannot be
	 * switched back on.
	 *
	 * Opened over Settings. `Modal` makes only the topmost sheet answer Escape and outside
	 * clicks, so closing this does not also close the screen under it.
	 */
	import { untrack } from 'svelte';
	import { api, type Skill } from '$lib/api/client';
	import Input from '$lib/components/Input.svelte';
	import Modal from '$lib/components/Modal.svelte';
	import { t } from '$lib/i18n';

	interface Props {
		/** The skill to edit, or `null` to write a new one. */
		skill: Skill | null;
		onclose: () => void;
		/** Called with what the loader made of the file, after every successful save. */
		onsaved: (skill: Skill) => void;
		onremoved: (id: string) => void;
	}

	let { skill, onclose, onsaved, onremoved }: Props = $props();

	/** The skill being edited. Starts as the prop and becomes the new skill once it exists, so
	 * a second Save after a create with problems is an edit and not a second create. */
	let current = $state<Skill | null>(untrack(() => skill));

	/** A starting point that is already a valid file: the name follows the id typed above it
	 * for as long as the text is still the template. */
	const template = (id: string) =>
		`---\nname: ${id}\ndescription: Use when…\n---\n\nWrite the instructions here.\n`;

	let id = $state('');
	let original = $state<string | null>(untrack(() => (skill ? null : template(''))));
	let draft = $state(untrack(() => (skill ? '' : template(''))));
	let problems = $state<string[]>([]);
	let error = $state<string | null>(null);
	let saving = $state(false);
	let confirming = $state(false);

	const isNew = $derived(current === null);
	const changed = $derived(isNew ? id.trim() !== '' : original !== null && draft !== original);
	const name = $derived(current?.id ?? id);

	$effect(() => {
		if (skill) void load(skill.id);
	});

	async function load(skillId: string) {
		try {
			const { content } = await api.skillSource(skillId);
			original = content;
			draft = content;
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		}
	}

	function typed(value: string) {
		const before = template(id.trim().toLowerCase());
		id = value;
		if (draft === before) draft = template(value.trim().toLowerCase());
	}

	async function save() {
		saving = true;
		try {
			let saved: Skill;
			if (current) {
				saved = await api.saveSkillSource(current.id, draft);
			} else {
				saved = await api.createSkill({ id: id.trim().toLowerCase(), content: draft });
				current = saved;
			}
			original = draft;
			onsaved(saved);
			problems = saved.problems;
			error = null;
			if (!problems.length) onclose();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		} finally {
			saving = false;
		}
	}

	async function remove() {
		if (!current) return;
		saving = true;
		try {
			await api.deleteSkill(current.id);
			onremoved(current.id);
			onclose();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
			confirming = false;
		} finally {
			saving = false;
		}
	}
</script>

<Modal
	label={isNew ? t.settings.newSkill : t.settings.editSkill(name)}
	title={isNew ? t.settings.newSkill : t.settings.editSkill(name)}
	caption={isNew ? t.settings.newSkillBlurb : t.settings.editSkillBlurb}
	placement="centre"
	width="min(760px, 94vw)"
	sheetclass="skill-editor"
	{onclose}
>
	<div class="body">
		{#if isNew}
			<Input
				mono
				value={id}
				placeholder={t.settings.skillId}
				ariaLabel={t.settings.skillId}
				onchange={typed}
			/>
			<p class="caption rule">{t.settings.skillIdRule}</p>
		{/if}

		{#if original === null && !error}
			<p class="caption">{t.settings.loadingSource}</p>
		{:else}
			<textarea
				bind:value={draft}
				aria-label={t.settings.skillSource}
				spellcheck="false"
				disabled={original === null}></textarea>
		{/if}

		{#if error}
			<p class="problem caption">{error}</p>
		{/if}
		{#each problems as problem (problem)}
			<p class="problem caption">{problem}</p>
		{/each}
	</div>

	<footer>
		{#if confirming}
			<p class="sure caption">{t.settings.deleteSure(name)}</p>
			<button class="ghost" type="button" onclick={() => (confirming = false)}>
				{t.settings.deleteKeep}
			</button>
			<button class="danger solid" type="button" disabled={saving} onclick={remove}>
				{t.settings.deleteYes}
			</button>
		{:else}
			{#if !isNew}
				<button class="danger" type="button" onclick={() => (confirming = true)}>
					{t.settings.deleteSkill}
				</button>
			{/if}
			<span class="spacer"></span>
			<button class="ghost" type="button" onclick={onclose}>{t.settings.cancel}</button>
			<button class="primary" type="button" disabled={!changed || saving} onclick={save}>
				{isNew ? t.settings.create : t.settings.save}
			</button>
		{/if}
	</footer>
</Modal>

<style>
	:global(.sheet.skill-editor) {
		height: min(80vh, 680px);
	}

	.body {
		display: flex;
		flex: 1;
		flex-direction: column;
		gap: 8px;
		min-height: 0;
		padding: 16px 20px 0;
	}

	textarea {
		flex: 1;
		min-height: 0;
		width: 100%;
		padding: 10px 12px;
		resize: none;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		color: var(--text);
		font-family: var(--font-mono);
		font-size: 13px;
		line-height: 1.55;
		tab-size: 2;
	}

	textarea:focus-visible {
		outline: none;
		border-color: var(--brass);
	}

	footer {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 14px 20px;
	}

	.spacer {
		flex: 1;
	}

	.sure {
		flex: 1;
		margin: 0;
		color: var(--danger);
	}

	footer button {
		padding: 6px 14px;
		border-radius: var(--radius);
		font-size: 13px;
	}

	.ghost {
		border: 1px solid var(--line);
		color: var(--text-muted);
	}

	.primary {
		background: var(--pomegranate);
		color: var(--ground);
	}

	.primary:disabled {
		opacity: 0.45;
	}

	/* Red, and a different shape from Save, so the one irreversible button cannot be mistaken
	   for the one beside it. */
	.danger {
		border: 1px solid var(--danger);
		color: var(--danger);
	}

	.danger.solid {
		background: var(--danger);
		color: var(--ground);
	}

	.rule {
		margin: 0;
		color: var(--text-faint);
	}

	.problem {
		margin: 0;
		color: var(--danger);
	}
</style>
