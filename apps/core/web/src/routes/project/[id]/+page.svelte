<script lang="ts">
	/**
	 * One project: what we are working on, and what every chat inside it carries.
	 *
	 * **Not a Settings tab.** Settings is *how she works* — what she runs on, who she is, what she
	 * may do. A project is the work, and it changes whenever the work does. `docs/frontend.md`
	 * § *Project or profile?* holds that line, and it is the same line that decides what belongs
	 * in the instructions box below: if a sentence would still be true in a project about
	 * something else, it is a mind region instead.
	 *
	 * Everything here saves one field at a time. A whole-project PUT would let this screen,
	 * left open in a second tab, overwrite a pin somebody added in the first on its way past.
	 */
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { untrack } from 'svelte';
	import type { Project } from '$lib/api/client';
	import Select from '$lib/components/Select.svelte';
	import SkillPicker from '$lib/components/SkillPicker.svelte';
	import { t } from '$lib/i18n';
	import { PROJECT_COLOURS, colourOf } from '$lib/projects';
	import { workspace } from '$lib/stores/workspace.svelte';

	const project = $derived(workspace.projects.find((one) => one.id === page.params.id) ?? null);
	const chats = $derived(workspace.chats.filter((chat) => chat.project_id === page.params.id));

	/** The instructions being edited. Seeded from the project and owned here afterwards, the same
	 * arrangement `SkillPicker` uses: following the prop while somebody is typing into it would
	 * discard the sentence they are halfway through the moment anything else refreshed the rail. */
	let draft = $state('');
	let seeded = $state<string | null>(null);
	let saved = $state(false);
	let picking = $state(false);

	// Not an $effect: this both reads and writes state the derived value above depends on, which
	// is the shape that ends in effect_update_depth_exceeded — a blank page with nothing on it to
	// say why. Reseeding on the id changing is what `seeded` tracks instead.
	$effect(() => {
		const current = project;
		if (!current || untrack(() => seeded) === current.id) return;
		untrack(() => {
			seeded = current.id;
			draft = current.instructions;
			saved = false;
		});
	});

	const dirty = $derived(project !== null && draft !== project.instructions);

	async function saveInstructions(current: Project) {
		const updated = await workspace.patchProject(current.id, { instructions: draft });
		if (!updated) return;
		saved = true;
		setTimeout(() => (saved = false), 1600);
	}

	async function pickSkills(current: Project, names: string[]) {
		picking = false;
		await workspace.patchProject(current.id, { pinned_skills: names });
	}

	async function chooseProfile(current: Project, value: string) {
		// `''` is the empty option and means *no default*, which has to travel as an explicit
		// `null` — the server distinguishes a field left out from one sent as null on exactly
		// this field, and a patch that omits it would quietly keep the old profile.
		await workspace.patchProject(current.id, { default_profile_id: value || null });
	}
</script>

{#if !project}
	<div class="missing">
		<p>{t.project.notFound}</p>
		<button class="save" type="button" onclick={() => goto('/')}>{t.rail.newChat}</button>
	</div>
{:else}
	{@const accent = colourOf(project.color)}
	<div class="screen">
		<header>
			<span class="dot" style:background={accent ?? 'var(--text-faint)'} aria-hidden="true"></span>
			<h1 class="display">{project.name}</h1>
		</header>

		<section>
			<h2>{t.project.instructions}</h2>
			<p class="caption">{t.project.instructionsHint}</p>
			<!-- No placeholder. The hint above already says what belongs here, and repeating it
			     inside the field means the empty state says the same sentence twice. -->
			<textarea bind:value={draft} rows="8"></textarea>
			<div class="foot">
				<button
					class="save"
					type="button"
					disabled={!dirty}
					onclick={() => saveInstructions(project)}
				>
					{t.project.save}
				</button>
				{#if saved}<span class="caption saved">{t.project.saved}</span>{/if}
			</div>
		</section>

		<section>
			<h2>{t.project.skills}</h2>
			<p class="caption">{t.project.skillsHint}</p>
			<div class="chips">
				{#each project.pinned_skills as name (name)}
					<span class="chip">{name}</span>
				{:else}
					<span class="caption">—</span>
				{/each}
				<button class="link" type="button" onclick={() => (picking = true)}>
					{t.project.chooseSkills}
				</button>
			</div>
		</section>

		<section class="pair">
			<div>
				<h2>{t.project.defaultProfile}</h2>
				<p class="caption">{t.project.defaultProfileHint}</p>
				<Select
					choices={[
						{ value: '', label: t.project.noDefaultProfile },
						...workspace.profiles.map((profile) => ({
							value: profile.id,
							label: profile.name,
							hint: profile.description
						}))
					]}
					value={project.default_profile_id ?? ''}
					label={t.project.defaultProfile}
					onchange={(id) => chooseProfile(project, id)}
				/>
			</div>

			<div>
				<h2>{t.project.defaultAgent}</h2>
				<!-- Listed and disabled rather than hidden, the same call Settings → Dreaming
				     makes: a feature you can see coming is a promise, one you cannot is a
				     surprise. Nothing reads this column in v0.2. -->
				<p class="caption">{t.project.defaultAgentSoon}</p>
				<Select choices={[]} value="" label={t.project.defaultAgent} disabled />
			</div>
		</section>

		<section>
			<h2>{t.project.colour}</h2>
			<div class="colours">
				{#each PROJECT_COLOURS as name (name)}
					<button
						class="swatch"
						class:chosen={project.color === name}
						type="button"
						style:background={colourOf(name) ?? 'var(--text-faint)'}
						aria-label={name || t.project.colour}
						aria-pressed={project.color === name}
						onclick={() => workspace.patchProject(project.id, { color: name })}
					></button>
				{/each}
			</div>
		</section>

		<section>
			<h2>{t.project.chats}</h2>
			<ul class="chats">
				{#each chats as chat (chat.id)}
					<li><a href="/chat/{chat.id}">{chat.title || t.empty.title}</a></li>
				{:else}
					<li class="caption">{t.project.noChats}</li>
				{/each}
			</ul>
			<button class="link" type="button" onclick={() => goto('/')}>{t.rail.newChat}</button>
		</section>
	</div>
{/if}

{#if picking && project}
	<SkillPicker
		pinned={project.pinned_skills}
		onclose={() => (picking = false)}
		onpick={(names) => pickSkills(project, names)}
	/>
{/if}

<style>
	.screen {
		flex: 1;
		overflow-y: auto;
		width: 100%;
		max-width: var(--column);
		margin: 0 auto;
		padding: 40px 24px 64px;
	}

	.missing {
		display: grid;
		place-content: center;
		gap: 12px;
		flex: 1;
		color: var(--text-muted);
	}

	header {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-bottom: 28px;
	}

	h1 {
		font-size: 26px;
		margin: 0;
	}

	.dot {
		width: 8px;
		height: 8px;
		flex: none;
		border-radius: 50%;
	}

	section {
		margin-bottom: 30px;
	}

	h2 {
		margin: 0 0 2px;
		font-size: 13px;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		color: var(--text-muted);
	}

	.caption {
		display: block;
		margin: 0 0 8px;
		color: var(--text-faint);
	}

	textarea {
		width: 100%;
		padding: 10px 12px;
		background: var(--surface);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		color: var(--text);
		font: inherit;
		resize: vertical;
	}

	textarea:focus {
		outline: none;
		border-color: var(--brass);
	}

	.foot {
		display: flex;
		align-items: center;
		gap: 10px;
		margin-top: 8px;
	}

	.save {
		padding: 6px 14px;
		background: var(--surface-raised);
		border: 1px solid var(--line);
		border-radius: var(--radius);
		color: var(--text);
		font-size: 13px;
	}

	.save:disabled {
		color: var(--text-faint);
	}

	.saved {
		margin: 0;
		color: var(--laurel);
	}

	.pair {
		display: flex;
		gap: 28px;
		flex-wrap: wrap;
	}

	.chips {
		display: flex;
		align-items: center;
		gap: 6px;
		flex-wrap: wrap;
	}

	.chip {
		padding: 3px 9px;
		background: var(--surface-raised);
		border-radius: 999px;
		font-size: 12.5px;
		color: var(--text-muted);
	}

	.link {
		color: var(--brass);
		font-size: 13px;
	}

	.link:hover {
		text-decoration: underline;
	}

	.colours {
		display: flex;
		gap: 8px;
	}

	.swatch {
		width: 20px;
		height: 20px;
		border-radius: 50%;
		border: 2px solid transparent;
		box-shadow: 0 0 0 1px var(--line);
	}

	.swatch.chosen {
		border-color: var(--ground);
		box-shadow: 0 0 0 2px var(--brass);
	}

	.chats {
		list-style: none;
		margin: 0 0 8px;
		padding: 0;
	}

	.chats li {
		padding: 4px 0;
	}

	.chats a {
		color: var(--text-muted);
		text-decoration: none;
	}

	.chats a:hover {
		color: var(--text);
	}
</style>
