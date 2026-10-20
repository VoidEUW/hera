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
	import Button from '$lib/components/ui/Button.svelte';
	import { untrack } from 'svelte';
	import { api, type Skill } from '$lib/api/client';
	import FileEditor from '$lib/components/ui/FileEditor.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Modal from '$lib/components/ui/Modal.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';
	import Spinner from '$lib/components/ui/Spinner.svelte';
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
	/** The Edit switch: a skill opens read-only and is changed on purpose; a new one is nothing
	 * but an edit, so it opens with the switch on. */
	let writing = $state(untrack(() => skill === null));

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

<!-- The theme's file editor as a dialog (`hera/file-editor`, kind skill): the SKILL.md with its
     Edit switch, and a footer that says what state it is in — read only, unsaved, saved — beside
     its trust mark, Delete, Cancel and Save. -->
<Modal
	label={isNew ? t.settings.newSkill : t.settings.editSkill(name)}
	placement="centre"
	width="min(900px, 94vw)"
	sheetclass="skill-editor"
	closeButton={false}
	{onclose}
>
	<div class="body">
		{#if isNew}
			<Input
				mono
				label={t.settings.skillIdLabel}
				placeholder={t.settings.skillId}
				help={t.settings.skillIdRule}
				value={id}
				onchange={typed}
			/>
		{/if}

		{#if original === null && !error}
			<div class="loading"><Spinner size={16} label={t.settings.loadingSource} /></div>
		{:else}
			<FileEditor
				kind="skill"
				name={isNew ? t.settings.newSkill : `${name}/SKILL.md`}
				meta={isNew ? t.settings.newSkillBlurb : t.settings.editSkillBlurb}
				text={draft}
				bind:editing={writing}
				onchange={(value) => (draft = value)}
				{onclose}
			>
				{#snippet footer()}
					<span>
						{#if !writing}{t.settings.readOnly}{:else if changed}{t.settings.unsaved}{:else}{t
								.settings.editingNow}{/if}
					</span>
					{#if current && current.trust !== 'unknown'}
						<Pill tone={current.trust === 'verified' ? 'authority' : 'danger'}>
							{current.trust === 'verified' ? t.settings.verified : t.settings.modified}
						</Pill>
					{/if}
				{/snippet}
			</FileEditor>
		{/if}

		{#if error}
			<p class="problem">{error}</p>
		{/if}
		{#each problems as problem (problem)}
			<p class="problem">{problem}</p>
		{/each}
	</div>

	{#snippet footer()}
		{#if confirming}
			<p class="sure">{t.settings.deleteSure(name)}</p>
			<Button variant="ghost" onclick={() => (confirming = false)}>
				{t.settings.deleteKeep}
			</Button>
			<Button variant="danger" icon="trash" disabled={saving} onclick={remove}>
				{t.settings.deleteYes}
			</Button>
		{:else}
			{#if !isNew}
				<Button variant="danger-soft" icon="trash" onclick={() => (confirming = true)}>
					{t.settings.deleteSkill}
				</Button>
			{/if}
			<span class="spacer"></span>
			<Button variant="ghost" onclick={onclose}>{t.settings.cancel}</Button>
			<Button variant="highlighted" busy={saving} disabled={!changed} onclick={save}>
				{isNew ? t.settings.create : t.settings.save}
			</Button>
		{/if}
	{/snippet}
</Modal>

<style>
	:global(.sheet.skill-editor) {
		height: min(84vh, 720px);
	}

	.body {
		display: flex;
		flex: 1;
		flex-direction: column;
		gap: 12px;
		min-height: 0;
		padding: 20px 22px 14px;
	}

	.body > :global(.fe) {
		flex: 1;
	}

	.loading {
		display: grid;
		flex: 1;
		place-items: center;
	}

	.spacer {
		flex: 1;
	}

	.sure {
		flex: 1;
		margin: 0;
		color: var(--danger);
		font-size: 13px;
	}

	.problem {
		margin: 0;
		color: var(--danger);
		font-size: 12px;
	}
</style>
