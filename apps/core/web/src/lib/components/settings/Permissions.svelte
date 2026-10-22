<script lang="ts">
	/**
	 * What she may do without asking (#109): the rules, what happens to anything they do not cover,
	 * and a way to make, change and remove them.
	 *
	 * One row per rule, in words first: the name a person gave it (or, for one nobody named, what
	 * its pattern says — *Every tool from fs*), the pattern in mono beside it, the tools it covers
	 * today, and where it came from — built in, answered on a card, or made here. What happens is a
	 * three-way switch on the row, because the whole screen exists to be flipped. Rules that ship
	 * with Hera can be changed and not deleted; the ones from a profile are shown and not touched.
	 *
	 * Counted load, as in `Servers.svelte`.
	 */
	import { api, ApiError, type Decision, type Rule } from '$lib/api/client';
	import Button from '$lib/components/ui/Button.svelte';
	import Confirm from '$lib/components/ui/Confirm.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import Pill from '$lib/components/ui/Pill.svelte';
	import Segmented from '$lib/components/ui/Segmented.svelte';
	import { t } from '$lib/i18n';
	import { Placeholder } from '$lib/loading.svelte';
	import { describePattern } from '$lib/permissions';
	import Rows from './Rows.svelte';
	import RuleEditor from './RuleEditor.svelte';

	interface Props {
		filter?: string;
	}

	let { filter = '' }: Props = $props();

	let rules = $state<Rule[]>([]);
	let fallback = $state<Decision>('ask');
	let error = $state<string | null>(null);
	/** The editor: a rule being changed, `'new'`, or closed. */
	let editing = $state<Rule | 'new' | null>(null);
	let deleting = $state<Rule | null>(null);

	const choices = (['allow', 'ask', 'deny'] as const).map((value) => ({
		value,
		label: t.permissions.decisions[value].label
	}));

	/** What a rule is called on its row: the name a person gave it, else what its pattern says. */
	function title(rule: Rule): string {
		if (rule.name) return rule.name;
		const said = describePattern(rule.pattern);
		switch (said.kind) {
			case 'everything':
				return t.permissions.everything;
			case 'server':
				return t.permissions.fromServer(said.server);
			case 'tool':
				return t.permissions.oneTool(said.server, said.tool);
			default:
				return t.permissions.matching(said.pattern);
		}
	}

	const visible = $derived(
		rules.filter(
			(rule) =>
				!filter ||
				`${title(rule)} ${rule.pattern} ${rule.reason} ${rule.name}`.toLowerCase().includes(filter)
		)
	);

	const settling = new Placeholder(true);
	$effect(() => () => settling.stop());

	let generation = 0;

	$effect(() => {
		void load();
	});

	async function load() {
		const token = ++generation;
		error = null;
		settling.set(true);
		try {
			const found = await api.permissions();
			if (token !== generation) return;
			rules = found.rules;
			fallback = found.fallback;
		} catch (cause) {
			if (token !== generation) return;
			error = cause instanceof Error ? cause.message : String(cause);
		} finally {
			if (token === generation) settling.set(false);
		}
	}

	/** Say what went wrong where a person is looking; the list is then the server's again. */
	async function attempt(change: () => Promise<unknown>) {
		error = null;
		try {
			await change();
		} catch (cause) {
			error = cause instanceof ApiError || cause instanceof Error ? cause.message : String(cause);
		}
		await load();
	}

	const decide = (rule: Rule, decision: Decision) =>
		attempt(() => api.updateRule(rule.pattern, { decision }));

	const setFallback = (decision: Decision) => attempt(() => api.setFallback(decision));

	function remove() {
		const rule = deleting;
		deleting = null;
		if (rule) void attempt(() => api.deleteRule(rule.pattern));
	}

	function saved() {
		editing = null;
		void load();
	}

	const SHOWN = 3;
	const editable = (rule: Rule) => rule.source !== 'profile';
	const deletable = (rule: Rule) => rule.source === 'you' || rule.source === 'card';
</script>

{#if error}
	<p class="error" role="alert">{error}</p>
{/if}

{#if settling.shown}
	<Rows label={t.settings.loading} />
{:else}
	<section class="fallback">
		<div class="what">
			<h3>{t.permissions.fallbackTitle}</h3>
			<p class="caption">
				{t.permissions.fallbackHelp}
				{t.permissions.decisions[fallback].help}
			</p>
		</div>
		<Segmented
			size="sm"
			options={choices}
			value={fallback}
			label={t.permissions.fallbackTitle}
			onchange={setFallback}
		/>
	</section>

	<div class="bar">
		<h3>{t.permissions.rulesHeading}</h3>
		<Button variant="highlighted" size="sm" icon="plus" onclick={() => (editing = 'new')}>
			{t.permissions.newRule}
		</Button>
	</div>

	{#each visible as rule (rule.pattern + (rule.profile ?? ''))}
		<section class="row">
			<div class="main">
				<div class="head">
					<h3>{title(rule)}</h3>
					{#if rule.source === 'default'}
						<Pill>{t.permissions.sources.default}</Pill>
					{:else if rule.source === 'card'}
						<Pill tone="authority" dot={false}>{t.permissions.sources.card}</Pill>
					{:else if rule.source === 'profile'}
						<Pill>{t.permissions.sources.profile(rule.profile ?? '')}</Pill>
					{/if}
				</div>
				<p class="pattern mono">{rule.pattern}</p>
				<p class="caption covers">
					{#if rule.covers.length === 0}
						{t.permissions.coversNone}
					{:else}
						{t.permissions.covers(rule.covers.length)}:
						<span class="mono">{rule.covers.slice(0, SHOWN).join(', ')}</span
						>{#if rule.covers.length > SHOWN}
							<span> +{rule.covers.length - SHOWN}</span>
						{/if}
					{/if}
				</p>
				{#if rule.reason}
					<p class="caption">{rule.reason}</p>
				{/if}
			</div>
			<div class="side">
				{#if editable(rule)}
					<Segmented
						size="sm"
						options={choices}
						value={rule.decision}
						label={title(rule)}
						onchange={(next) => decide(rule, next)}
					/>
					<IconButton
						icon="edit"
						size="sm"
						label={t.permissions.edit}
						onclick={() => (editing = rule)}
					/>
					{#if deletable(rule)}
						<IconButton
							icon="trash"
							size="sm"
							label={t.permissions.delete}
							onclick={() => (deleting = rule)}
						/>
					{/if}
				{:else}
					<Pill
						tone={rule.decision === 'allow'
							? 'live'
							: rule.decision === 'deny'
								? 'danger'
								: 'neutral'}>{t.permissions.decisions[rule.decision].label}</Pill
					>
				{/if}
			</div>
		</section>
	{:else}
		<p class="empty">{filter ? t.settings.noMatch : t.settings.noPermissions}</p>
	{/each}
	<p class="caption note">{t.permissions.builtInNote}</p>
{/if}

{#if editing}
	<RuleEditor
		rule={editing === 'new' ? undefined : editing}
		onsaved={saved}
		onclose={() => (editing = null)}
	/>
{/if}

{#if deleting}
	<Confirm
		title={t.permissions.deleteTitle}
		body={t.permissions.deleteBody(title(deleting))}
		confirm={t.permissions.deleteYes}
		cancel={t.permissions.deleteKeep}
		onconfirm={remove}
		oncancel={() => (deleting = null)}
	/>
{/if}

<style>
	h3 {
		margin: 0;
		font-size: 14px;
		font-weight: 500;
	}

	.fallback {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		padding: 14px 0 6px;
	}

	.bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		padding: 22px 0 12px;
		border-bottom: 1px solid var(--line);
	}

	.row {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 16px;
		padding: 14px 0;
		border-bottom: 1px solid var(--line);
	}

	.main {
		min-width: 0;
	}

	.head {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.side {
		display: flex;
		flex: none;
		align-items: center;
		gap: 6px;
	}

	.pattern {
		margin: 2px 0 0;
		color: var(--text-muted);
		font-size: 12px;
	}

	.caption {
		margin: 4px 0 0;
	}

	.covers {
		overflow-wrap: anywhere;
	}

	.covers .mono {
		font-size: 12px;
	}

	.note {
		margin: 14px 0 0;
	}

	@media (max-width: 600px) {
		.row,
		.fallback {
			flex-direction: column;
			align-items: stretch;
		}
	}

	.empty {
		margin: 18px 0;
		max-width: 60ch;
		font-family: var(--font-body);
		font-size: 15px;
		line-height: 1.6;
		color: var(--text-muted);
	}

	.error {
		margin: 0 0 14px;
		color: var(--danger);
		font-size: 13px;
	}
</style>
