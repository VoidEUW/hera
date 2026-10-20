<script lang="ts">
	/**
	 * What she knows how to do.
	 *
	 * A skill is a folder somebody wrote — often somebody else — and it goes into her prompt.
	 * So the row answers the three questions that actually get asked about one: *what is it for*
	 * (the description retrieval matches on), *whose is it* (author, licence, version), and *is
	 * it the one I accepted* (the verified mark).
	 *
	 * The mark is not self-declared. It comes from `trusted.json`, which lists a skill id and
	 * the digest you accepted; a skill claiming its own trustworthiness would have claimed
	 * nothing. **Changed** is a state of its own for the same reason it exists in the API: a
	 * skill you signed and somebody then edited is not the same thing as one you never signed.
	 *
	 * Broken skills keep their rows. A skill that vanished silently is indistinguishable from
	 * one that was never installed, and "why is my skill not being used" is what this screen is
	 * for.
	 */
	import Avatar from '$lib/components/ui/Avatar.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';
	import { api, type BrokenSkill, type Skill } from '$lib/api/client';
	import Checkbox from '$lib/components/ui/Checkbox.svelte';
	import SkillEditor from './SkillEditor.svelte';
	import { t } from '$lib/i18n';
	import { Placeholder } from '$lib/loading.svelte';
	import Rows from './Rows.svelte';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	let skills = $state<Skill[]>([]);
	let broken = $state<BrokenSkill[]>([]);
	let trustProblem = $state('');
	/** `undefined` is closed, `null` is a new skill, a skill is that skill. */
	let editing = $state<Skill | null | undefined>(undefined);
	let error = $state<string | null>(null);

	const shown = $derived(
		skills.filter(
			(skill) =>
				!filter ||
				`${skill.id} ${skill.name} ${skill.description} ${skill.author} ${skill.license}`
					.toLowerCase()
					.includes(filter)
		)
	);

	/** The same placeholder and the same beat as every other settings screen (`Rows`).
	 *
	 * Set where the load begins and ends rather than through an `$effect` over a flag: both
	 * halves of a fast local fetch can happen before effects next flush, and an effect that
	 * only ever sees the `false` draws nothing. It is never set back to `true` — a refresh
	 * after a change made here has a list on screen already, and replacing that with grey
	 * would say the screen is arriving when it is only catching up. */
	const settling = new Placeholder(true);
	$effect(() => () => settling.stop());
	const waiting = $derived(settling.shown);

	$effect(() => {
		void load();
	});

	async function load() {
		try {
			const found = await api.skills();
			skills = found.skills;
			broken = found.broken;
			trustProblem = found.trust_problem;
			error = null;
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		} finally {
			settling.set(false);
		}
	}

	/** The frontmatter's emoji, or the first letter of the name it is invoked by. Every row
	 * gets a mark; no skill has to carry one. */
	function mark(skill: Skill): string {
		return skill.icon || (skill.id[0] ?? '?').toUpperCase();
	}

	/** Author first and licence after it, because "whose is this" is the question a person
	 * asks and a licence is a footnote to the answer. The version is not in here at all: it
	 * belongs on the right, where you can run your eye down a column and compare it with what
	 * a repository says is current. */
	function facts(skill: Skill): string[] {
		return [skill.author && t.settings.by(skill.author), skill.license].filter(
			(fact): fact is string => Boolean(fact)
		);
	}

	/** Optimistic, and put back if the write fails. Off keeps the folder: the skill is not
	 * routed, not offered to `/slash` and not pinnable, and switching it on again is the same
	 * click. */
	async function toggle(skill: Skill) {
		const previous = skills;
		skills = skills.map((entry) =>
			entry.id === skill.id ? { ...entry, enabled: !entry.enabled } : entry
		);
		try {
			await api.setSkillEnabled(skill.id, !skill.enabled);
			error = null;
		} catch (cause) {
			skills = previous;
			error = cause instanceof Error ? cause.message : String(cause);
		}
	}
</script>

{#if waiting}
	<Rows label={t.settings.loadingSkills} />
{:else}
	{#if error}
		<p class="problem caption">{error}</p>
	{/if}

	{#if trustProblem}
		<p class="problem caption">{trustProblem}</p>
	{/if}

	{#each shown as skill (skill.id)}
		<section class="row" class:off={!skill.enabled}>
			<span class="icon"><Avatar name={mark(skill)} size={30} /></span>

			<div class="detail">
				<div class="head">
					<h3>{skill.id}</h3>
					{#if skill.trust !== 'unknown'}
						<Pill tone={skill.trust === 'verified' ? 'authority' : 'danger'} dot>
							{skill.trust === 'verified' ? t.settings.verified : t.settings.modified}
						</Pill>
					{/if}
					<span class="right">
						{#if skill.version}
							<span class="version mono">{t.settings.version(skill.version)}</span>
						{/if}
						<Button
							size="sm"
							icon="edit"
							aria-label={t.settings.editSkill(skill.id)}
							onclick={() => (editing = skill)}
						>
							{t.message.edit}
						</Button>
						<Checkbox
							variant="switch"
							checked={skill.enabled}
							ariaLabel={t.settings.useSkill(skill.id)}
							onchange={() => toggle(skill)}
						/>
					</span>
				</div>

				<p class="caption">{skill.description}</p>

				{#if facts(skill).length}
					<p class="facts caption">
						<span class="author">{facts(skill)[0]}</span>
						{#if facts(skill).length > 1}<Pill>{facts(skill)[1]}</Pill>{/if}
					</p>
				{/if}

				{#each skill.problems as problem (problem)}
					<p class="caption problem">{problem}</p>
				{/each}
			</div>
		</section>
	{:else}
		<p class="empty">{filter ? t.settings.noMatch : t.settings.noSkills}</p>
	{/each}

	{#each broken as item (item.id)}
		<section class="row">
			<span class="icon"><Avatar icon="alert" size={30} /></span>
			<div class="detail">
				<div class="head">
					<h3>{item.id}</h3>
					<Pill tone="danger">{t.settings.broken}</Pill>
				</div>
				<p class="caption problem">{item.reason}</p>
			</div>
		</section>
	{/each}

	{#if skills.length || broken.length}
		<p class="note caption">{t.settings.trustNote}</p>
	{/if}

	<div class="add">
		<Button icon="plus" onclick={() => (editing = null)}>{t.settings.addSkill}</Button>
	</div>

	<p class="note caption">
		{t.settings.skillsFolder}
		<a href="https://github.com/VoidEUW/hera-skills" target="_blank" rel="noreferrer"
			>{t.settings.skillsRepo}</a
		>.
	</p>
{/if}

{#if editing !== undefined}
	<SkillEditor
		skill={editing}
		onclose={() => (editing = undefined)}
		onsaved={(saved) => {
			if (skills.some((entry) => entry.id === saved.id)) {
				skills = skills.map((entry) => (entry.id === saved.id ? saved : entry));
			} else {
				void load();
			}
		}}
		onremoved={(id) => (skills = skills.filter((entry) => entry.id !== id))}
	/>
{/if}

<style>
	.row {
		display: flex;
		align-items: flex-start;
		gap: 12px;
		padding: 14px 0;
		border-bottom: 1px solid var(--line);
	}

	.row.off .detail,
	.row.off .icon {
		opacity: 0.55;
	}

	.detail {
		flex: 1;
		min-width: 0;
	}

	.icon {
		flex: none;
		margin-top: 1px;
	}

	.head {
		display: flex;
		align-items: center;
		gap: 10px;
	}

	h3 {
		margin: 0;
		font-size: 14px;
		font-weight: 500;
	}

	.right {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-left: auto;
		flex: none;
	}

	.add {
		margin-top: 14px;
	}

	.version {
		font-size: 12px;
		color: var(--text-muted);
	}

	.facts {
		display: flex;
		align-items: baseline;
		gap: 10px;
		margin: 4px 0 0;
	}

	.author {
		color: var(--text-muted);
	}

	.problem {
		color: var(--danger);
	}

	.note a {
		color: var(--text-muted);
		text-decoration: underline;
	}

	.note {
		margin: 14px 0 0;
		max-width: 62ch;
		color: var(--text-faint);
	}

	.empty {
		margin: 18px 0;
		max-width: 60ch;
		font-family: var(--font-body);
		font-size: 15px;
		line-height: 1.6;
		color: var(--text-muted);
	}
</style>
