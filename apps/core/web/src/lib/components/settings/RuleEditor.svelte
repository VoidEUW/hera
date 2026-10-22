<script lang="ts">
	/**
	 * Make a rule, or change one (#109): a name for people, the pattern, what happens, and why.
	 *
	 * The pattern is the rule's identity, so it is typed once and read-only afterwards — a
	 * different pattern is a different rule. As it is typed, the server says which of her tools it
	 * would cover (`GET /permissions/matches`), which is what turns `fs__*` from a string into a
	 * set of things a person can look at before pressing Add. The matcher is the policy's own; the
	 * browser holds no copy.
	 */
	import { untrack } from 'svelte';
	import { api, ApiError, type Decision, type Rule } from '$lib/api/client';
	import Button from '$lib/components/ui/Button.svelte';
	import Input from '$lib/components/ui/Input.svelte';
	import Modal from '$lib/components/ui/Modal.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import Textarea from '$lib/components/ui/Textarea.svelte';
	import { t } from '$lib/i18n';

	interface Props {
		/** The rule being changed. Left out, this makes a new one. */
		rule?: Rule;
		onsaved: () => void;
		onclose: () => void;
	}

	let { rule, onsaved, onclose }: Props = $props();

	/** Read once: the form is seeded from the rule and then belongs to the person typing in it, so
	 * a refresh of the list behind must not rewrite what they have half typed. */
	const seed = untrack(() => rule);
	const isNew = seed === undefined;

	let name = $state(seed?.name ?? '');
	let pattern = $state(seed?.pattern ?? '');
	let decision = $state<Decision>(seed?.decision ?? 'ask');
	let reason = $state(seed?.reason ?? '');
	let saving = $state(false);
	let error = $state<string | null>(null);

	/** Which tools the pattern covers, or `null` while there is nothing to ask about. */
	let preview = $state<string[] | null>(null);
	let searching = $state(false);
	let asked = 0;

	$effect(() => {
		const typed = pattern.trim();
		if (!typed) {
			preview = null;
			searching = false;
			return;
		}
		const token = ++asked;
		searching = true;
		// A beat after the last keystroke: every character is a new question otherwise.
		const timer = setTimeout(() => {
			api
				.ruleMatches(typed)
				.then((found) => {
					if (token !== asked) return;
					preview = found.tools;
				})
				.catch(() => {
					if (token === asked) preview = null;
				})
				.finally(() => {
					if (token === asked) searching = false;
				});
		}, 250);
		return () => clearTimeout(timer);
	});

	const SHOWN = 8;
	const choices = (['allow', 'ask', 'deny'] as const).map((value) => ({
		value,
		label: t.permissions.decisions[value].label
	}));

	async function save() {
		const typed = pattern.trim();
		if (!typed) {
			error = t.permissions.patternRequired;
			return;
		}
		saving = true;
		error = null;
		try {
			if (seed) await api.updateRule(seed.pattern, { name, decision, reason });
			else await api.createRule({ pattern: typed, decision, name, reason });
			onsaved();
		} catch (cause) {
			error = cause instanceof ApiError || cause instanceof Error ? cause.message : String(cause);
		} finally {
			saving = false;
		}
	}
</script>

<Modal
	label={isNew ? t.permissions.newRule : t.permissions.editRule}
	title={isNew ? t.permissions.newRule : t.permissions.editRule}
	placement="top"
	width="min(560px, 94vw)"
	{onclose}
>
	<div class="body">
		<Input
			label={t.permissions.name}
			help={t.permissions.nameHelp}
			placeholder={t.permissions.namePlaceholder}
			value={name}
			autofocus={!isNew}
			onchange={(value) => (name = value)}
		/>

		<div class="pattern">
			<Input
				mono
				label={t.permissions.pattern}
				help={isNew ? t.permissions.patternHelp : t.permissions.patternLocked}
				placeholder={t.permissions.patternPlaceholder}
				value={pattern}
				disabled={!isNew}
				autofocus={isNew}
				onchange={(value) => (pattern = value)}
			/>
			{#if preview !== null || searching}
				<div class="preview" aria-live="polite">
					{#if preview === null}
						<p class="caption">{t.permissions.previewSearching}</p>
					{:else if preview.length === 0}
						<p class="caption">{t.permissions.previewNone}</p>
					{:else}
						<p class="caption">{t.permissions.previewMatches(preview.length)}</p>
						<p class="tools">
							{#each preview.slice(0, SHOWN) as tool (tool)}
								<span class="tool">{tool}</span>
							{/each}
							{#if preview.length > SHOWN}
								<span class="more">+{preview.length - SHOWN}</span>
							{/if}
						</p>
					{/if}
				</div>
			{/if}
		</div>

		<div class="decision">
			<span class="label">{t.permissions.decisionLabel}</span>
			<Segmented
				options={choices}
				value={decision}
				label={t.permissions.decisionLabel}
				onchange={(next) => (decision = next)}
			/>
			<p class="caption">{t.permissions.decisions[decision].help}</p>
		</div>

		<Textarea
			label={t.permissions.reason}
			help={t.permissions.reasonHelp}
			placeholder={t.permissions.reasonPlaceholder}
			rows={2}
			value={reason}
			onchange={(value) => (reason = value)}
		/>

		{#if error}<p class="error" role="alert">{error}</p>{/if}
	</div>

	{#snippet footer()}
		<Button variant="ghost" onclick={onclose}>{t.permissions.cancel}</Button>
		<Button variant="highlighted" busy={saving} disabled={!pattern.trim()} onclick={save}>
			{isNew ? t.permissions.create : t.permissions.save}
		</Button>
	{/snippet}
</Modal>

<style>
	.body {
		display: flex;
		flex-direction: column;
		gap: 16px;
		padding: 8px 22px 18px;
		overflow-y: auto;
	}

	.label {
		display: block;
		margin-bottom: 6px;
		font-size: 13px;
	}

	.caption {
		margin: 6px 0 0;
	}

	.preview {
		margin-top: 8px;
	}

	.tools {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin: 6px 0 0;
	}

	.tool,
	.more {
		padding: 2px 8px;
		border-radius: var(--chip-radius);
		background: var(--hover);
		color: var(--text-muted);
		font-family: var(--font-mono);
		font-size: 11.5px;
	}

	.error {
		margin: 0;
		color: var(--danger);
		font-size: 13px;
	}
</style>
