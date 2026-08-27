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
	import { api, type BrokenSkill, type Skill } from '$lib/api/client';
	import { t } from '$lib/i18n';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	let skills = $state<Skill[]>([]);
	let broken = $state<BrokenSkill[]>([]);
	let trustProblem = $state('');
	let error = $state<string | null>(null);
	let adding = $state(false);
	let fresh = $state({ id: '', description: '' });

	const shown = $derived(
		skills.filter(
			(skill) =>
				!filter ||
				`${skill.id} ${skill.name} ${skill.description} ${skill.author} ${skill.license}`
					.toLowerCase()
					.includes(filter)
		)
	);

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

	async function add() {
		const id = fresh.id.trim().toLowerCase();
		if (!id) return;
		try {
			await api.createSkill({ id, description: fresh.description });
			fresh = { id: '', description: '' };
			adding = false;
			await load();
		} catch (cause) {
			error = cause instanceof Error ? cause.message : String(cause);
		}
	}
</script>

{#if error}
	<p class="problem caption">{error}</p>
{/if}

{#if trustProblem}
	<p class="problem caption">{trustProblem}</p>
{/if}

{#each shown as skill (skill.id)}
	<section class="row">
		<span class="icon" class:emoji={!!skill.icon} aria-hidden="true">{mark(skill)}</span>

		<div class="detail">
			<div class="head">
				<h3>{skill.id}</h3>
				{#if skill.trust !== 'unknown'}
					<span class="trust" data-trust={skill.trust} title={skill.digest}>
						<span aria-hidden="true">{skill.trust === 'verified' ? '✓' : '⚠'}</span>
						{skill.trust === 'verified' ? t.settings.verified : t.settings.modified}
					</span>
				{/if}
				<span class="right">
					{#if skill.version}
						<span class="version mono">{t.settings.version(skill.version)}</span>
					{/if}
					<span class="caption used">
						{skill.hits ? t.settings.usedTimes(skill.hits) : t.settings.never}
					</span>
				</span>
			</div>

			<p class="caption">{skill.description}</p>

			{#if facts(skill).length}
				<p class="facts caption">
					<span class="author">{facts(skill)[0]}</span>
					{#if facts(skill).length > 1}<span class="license">{facts(skill)[1]}</span>{/if}
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
		<span class="icon bad" aria-hidden="true">!</span>
		<div class="detail">
			<div class="head">
				<h3>{item.id}</h3>
				<span class="caption problem">{t.settings.broken}</span>
			</div>
			<p class="caption problem">{item.reason}</p>
		</div>
	</section>
{/each}

{#if adding}
	<section class="row new">
		<span class="icon" aria-hidden="true">＋</span>
		<div class="detail">
			<input
				class="id mono"
				bind:value={fresh.id}
				placeholder={t.settings.skillId}
				aria-label={t.settings.skillId}
			/>
			<input
				class="what"
				bind:value={fresh.description}
				placeholder={t.settings.skillDescription}
				aria-label={t.settings.skillDescription}
			/>
			<p class="caption rule">{t.settings.skillIdRule}</p>
			<div class="buttons">
				<button class="ghost" type="button" onclick={() => (adding = false)}>
					{t.settings.cancel}
				</button>
				<button class="primary" type="button" onclick={add}>{t.settings.create}</button>
			</div>
		</div>
	</section>
{:else}
	<button class="add" type="button" onclick={() => (adding = true)}>
		<span aria-hidden="true">＋</span>
		{t.settings.addSkill}
	</button>
{/if}

{#if skills.length || broken.length}
	<p class="note caption">{t.settings.trustNote}</p>
{/if}

<style>
	.row {
		display: flex;
		align-items: flex-start;
		gap: 12px;
		padding: 14px 0;
		border-bottom: 1px solid var(--line);
	}

	.detail {
		flex: 1;
		min-width: 0;
	}

	.icon {
		display: grid;
		place-items: center;
		width: 30px;
		height: 30px;
		flex: none;
		margin-top: 1px;
		border: 1px solid var(--line);
		border-radius: 8px;
		background: var(--surface);
		color: var(--brass);
		font-family: var(--font-display);
		font-size: 14px;
	}

	/* An emoji is already a picture and should not be set in the display face. */
	.icon.emoji {
		font-family: var(--font-ui);
		font-size: 15px;
	}

	.icon.bad {
		color: var(--danger);
	}

	.head {
		display: flex;
		align-items: baseline;
		gap: 10px;
	}

	h3 {
		margin: 0;
		font-size: 14px;
		font-weight: 500;
	}

	.right {
		display: flex;
		align-items: baseline;
		gap: 10px;
		margin-left: auto;
		flex: none;
	}

	.used {
		color: var(--text-faint);
	}

	/* On the right, in one column, so a row of skills can be compared with whatever a
	   repository says is current. */
	.version {
		font-size: 12px;
		color: var(--text-muted);
	}

	.trust {
		display: inline-flex;
		align-items: baseline;
		gap: 4px;
		font-size: 12px;
	}

	.trust[data-trust='verified'] {
		color: var(--brass);
	}

	.trust[data-trust='modified'] {
		color: var(--danger);
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

	.license {
		padding: 0 5px;
		border: 1px solid var(--line);
		border-radius: 4px;
		font-size: 11px;
		color: var(--text-faint);
	}

	.add {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-top: 14px;
		padding: 8px 12px;
		border: 1px dashed var(--line);
		border-radius: var(--radius);
		font-size: 13px;
		color: var(--text-muted);
		width: 100%;
		transition:
			border-color var(--fade) var(--ease),
			color var(--fade) var(--ease);
	}

	.add:hover {
		border-color: var(--brass);
		color: var(--brass);
	}

	.new .detail {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.new input {
		width: 100%;
		padding: 6px 9px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		font-size: 13px;
	}

	.rule {
		color: var(--text-faint);
	}

	.buttons {
		display: flex;
		justify-content: flex-end;
		gap: 8px;
	}

	.buttons button {
		padding: 5px 12px;
		border-radius: var(--radius);
		font-size: 12.5px;
	}

	.ghost {
		border: 1px solid var(--line);
		color: var(--text-muted);
	}

	.primary {
		background: var(--pomegranate);
		color: var(--ground);
	}

	.problem {
		color: var(--danger);
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
